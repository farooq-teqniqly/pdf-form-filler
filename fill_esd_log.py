"""Fill a weekly job-search activity PDF form from a YAML data file.

This script reads:
- An input PDF with AcroForm fields (pdf_in)
- A YAML file describing the claimant data and up to three contacts (yaml_in)

It writes a filled PDF (pdf_out) and attempts to render appearances so values
are visible in most PDF viewers.
"""

from __future__ import annotations
from pypdf import PdfReader, PdfWriter
from pypdf.errors import PdfReadError
from pypdf.generic import NameObject, BooleanObject, DictionaryObject
import argparse, yaml, sys, os
from typing import Any, Dict, List
from dotenv import load_dotenv
from contact_info_service import ContactInfoService
from openai import OpenAI
from telemetry import (
    tracer,
    shutdown_telemetry,
    pdf_processed_counter,
    contact_enriched_counter,
    contact_enrichment_failed_counter,
    pdf_processing_duration,
    contact_enrichment_duration,
)
from opentelemetry.trace import Status, StatusCode
import time

load_dotenv()

VERBOSE: bool = False
ACRO_FORM: str = "/AcroForm"
KIDS: str = "/Kids"

try:
    open_api_client = OpenAI()
    contact_info_service = ContactInfoService(open_api_client)
except Exception as e:
    print(
        "Error: Failed to initialize OpenAI client. Ensure OPENAI_API_KEY is set in .env file.",
        file=sys.stderr,
    )

    sys.exit(1)


def _is_truthy_env(value: str | None) -> bool:
    if value is None:
        return False
    v = value.strip().lower()
    return v not in ("", "0", "false", "no", "off")


def _debug(msg: str) -> None:
    if VERBOSE:
        print(f"DEBUG: {msg}", file=sys.stderr)


def clone_form(reader: PdfReader, writer: PdfWriter) -> None:
    """Copy the AcroForm structure from the reader into the writer.

    This ensures form fields exist in the writer so
    update_page_form_field_values can target them. Uses
    clone_document_from_reader when available, and falls back to
    appending pages and copying /AcroForm manually for compatibility.
    """
    try:
        writer.clone_document_from_reader(reader)  # pypdf >= 4.0
    except (AttributeError, NotImplementedError, TypeError):
        writer.append_pages_from_reader(reader)
        acro = reader.trailer["/Root"].get(ACRO_FORM)
        if acro is not None:
            writer._root_object[NameObject(ACRO_FORM)] = writer._add_object(acro)


def set_need_appearances(writer: PdfWriter) -> None:
    """Set the /NeedAppearances flag to True on the writer's AcroForm.

    Many viewers rely on this flag to render updated field values
    without regenerating field appearances manually.
    """
    if ACRO_FORM not in writer._root_object:
        writer._root_object.update(
            {NameObject(ACRO_FORM): writer._add_object(DictionaryObject())}
        )
    writer._root_object[ACRO_FORM].update(
        {NameObject("/NeedAppearances"): BooleanObject(True)}
    )


def set_text(
    page, writer: PdfWriter, fields: Dict[str, Any], field_name: str, value: Any
) -> None:
    """Set a text field's value if the field exists.

    Parameters:
    - page: The page object containing the field.
    - writer: Target PdfWriter to receive the updated value.
    - fields: Mapping of field names to field objects from the source PDF.
    - field_name: Name of the text field to update.
    - value: Value to write; converted to string, None becomes an empty string.
    """
    if not field_name:
        return
    if field_name not in fields:
        _debug(f"Requested text field absent: '{field_name}'")
        return

    for p in writer.pages:
        writer.update_page_form_field_values(
            p, {field_name: "" if value is None else str(value)}
        )


def _collect_on_states(obj) -> List[str]:
    """Collect non-Off appearance states from a widget or field object.

    Returns:
    - A list of possible "on" state strings (e.g., ['Yes']).
    """
    states = []
    if obj is None or "/AP" not in obj:
        return states
    ap = obj["/AP"]
    n = ap.get("/N")
    if hasattr(n, "keys"):
        for k in n.keys():
            ks = str(k)
            if ks not in ("/Off", "Off"):
                states.append(ks.lstrip("/"))
    return states


def detect_on_state(fields: Dict[str, Any], field_name: str) -> str:
    """Determine an appropriate "on" value for a checkbox-like field.

    Tries to read appearance states from the field and its kids. Falls back to
    'Yes' if nothing else is found.

    Returns:
    - The first available on-state or 'Yes'.
    """
    on_states: List[str] = []
    try:
        fobj = fields[field_name]
        try:
            fobj = fobj.get_object()
        except Exception:
            pass
        on_states.extend(_collect_on_states(fobj))
        if KIDS in fobj:
            for kid in fobj[KIDS]:
                try:
                    on_states.extend(_collect_on_states(kid.get_object()))
                except Exception:
                    pass
    except Exception:
        pass
    return on_states[0] if on_states else "Yes"


def set_checkbox(
    page, writer: PdfWriter, fields: Dict[str, Any], field_name: str, on: bool
) -> None:
    """Toggle a checkbox field on or off.

    Uses detect_on_state to choose a valid "on" appearance state and '/Off' for off.

    Parameters:
    - page: The page object containing the field.
    - writer: Target PdfWriter to receive the updated value.
    - fields: Mapping of field names to field objects from the source PDF.
    - field_name: Name of the checkbox field to update.
    - on: True to check, False to uncheck.
    """
    if not field_name:
        return
    if field_name not in fields:
        _debug(f"Requested checkbox field absent: '{field_name}'")
        return
    on_value = detect_on_state(fields, field_name)
    target = NameObject(f"/{on_value}") if on else NameObject("/Off")

    for p in writer.pages:
        writer.update_page_form_field_values(p, {field_name: target})


def _radio_on_values(fields: dict[str, Any], group_name: str) -> list[str]:
    """Enumerate valid appearance states for the radio button group.

    Returns:
    - A de-duplicated list of available non-off option names.
    """
    vals = []
    try:
        fobj = fields[group_name]
        try:
            fobj = fobj.get_object()
        except Exception:
            pass
        if KIDS in fobj:
            for kid in fobj[KIDS]:
                try:
                    ko = kid.get_object()
                    n = ko.get("/AP", {}).get("/N")
                    if hasattr(n, "keys"):
                        for k in n.keys():
                            s = str(k).lstrip("/")
                            if s and s.lower() != "off":
                                vals.append(s)
                except Exception:
                    pass
    except Exception:
        pass
    seen, out = set(), []
    for v in vals:
        if v not in seen:
            seen.add(v)
            out.append(v)
    return out


def set_radio_group(
    page,
    writer: PdfWriter,
    fields: dict[str, Any],
    group_name: str,
    desired: str | None,
) -> None:
    """Set a radio button group to a desired option if possible.

    Matching behavior:
    - Exact, case-insensitive match first.
    - Then case-insensitive substring match.
    - Falls back to the first available option if none match.

    Parameters mirror those of set_checkbox for page, writer, and fields.
    """
    if not desired:
        return
    if group_name not in fields:
        _debug(f"Requested radio group absent: '{group_name}'")
        return
    opts = _radio_on_values(fields, group_name)
    dl = desired.strip().lower()
    # exact match
    for o in opts:
        if o.lower() == dl:
            for p in writer.pages:
                writer.update_page_form_field_values(
                    p, {group_name: NameObject(f"/{o}")}
                )
            return
    # contains match
    for o in opts:
        if dl in o.lower():
            for p in writer.pages:
                writer.update_page_form_field_values(p, {group_name: f"/{o}"})
            return
    # fallback
    if opts:
        for p in writer.pages:
            writer.update_page_form_field_values(p, {group_name: f"/{opts[0]}"})


def first_page(writer: PdfWriter):
    """Return the first page object from the writer.

    Returns:
    - The PageObject at index 0.
    """
    return writer.pages[0]


CONTACT_METHOD_FIELDS = [
    ("In-person", "contact-in-person"),
    ("Online", "contact-online"),
    ("By phone", "contact-by-phone"),
    ("By email", "contact-by-email"),
    ("By mail", "contact-by-mail"),
    ("Other", "contact-other"),
]


def fill_contact_block(
    idx: int, contact: Dict[str, Any], page, writer: PdfWriter, fields: Dict[str, Any]
) -> None:
    """Fill one contact block (1..3) on the form with provided data.

    Parameters:
    - idx: 1-based block index used to prefix field names (e.g., 'c1-', 'c2-').
    - contact: Mapping with optional keys:
        date, job_title, business_name, address, city, state, website_or_email, phone,
        contact_method (string or list of strings),
        activity_choice ('employer[-contact]', 'worksource-activity', 'other-activity'),
        contact_type (e.g., 'application-resume', 'other') and contact_type_other,
        worksource_activity_kind, worksource_activity_documentation,
        worksource_activity_office_name, worksource_activity_city, worksource_activity_state,
        other_activity_kind, other_activity_documentation, activity (free text).
    - page: Target page object.
    - writer: PdfWriter receiving updates.
    - fields: Mapping of field names to field objects from the source PDF.

    Behavior:
    - Writes text fields directly when present in the source fields.
    - Checks appropriate contact method checkboxes by fuzzy label match.
    - Sets radio groups by exact or partial match, with a safe fallback.
    """
    px = f"c{idx}-"

    # Text fields
    set_text(page, writer, fields, px + "contact-date", contact.get("date"))
    set_text(page, writer, fields, px + "job-title", contact.get("job_title"))
    set_text(page, writer, fields, px + "business-name", contact.get("business_name"))
    set_text(page, writer, fields, px + "employer-address", contact.get("address"))
    set_text(page, writer, fields, px + "employer-city", contact.get("city"))
    set_text(page, writer, fields, px + "employer-state", contact.get("state"))
    set_text(
        page,
        writer,
        fields,
        px + "employer-website-or-email",
        contact.get("website_or_email"),
    )
    set_text(page, writer, fields, px + "employer-phone", contact.get("phone"))

    # Contact methods (checkboxes)
    method_raw = contact.get("contact_method")
    methods = [method_raw] if isinstance(method_raw, str) else (method_raw or [])
    for label, suffix in CONTACT_METHOD_FIELDS:
        field_name = f"{px}{suffix}"
        on = any(label.lower() == (m or "").strip().lower() for m in methods)
        set_checkbox(page, writer, fields, field_name, on)

    # Activity radio group
    activity = (contact.get("activity_choice") or "").strip().lower()
    if activity in ("employer", "employer contact"):
        activity = "employer-contact"
    if activity in ("worksource", "worksource activity"):
        activity = "worksource-activity"
    if activity in ("other", "other activity"):
        activity = "other-activity"
    set_radio_group(page, writer, fields, px + "activity", activity)

    # Contact type radio group
    ctype = (contact.get("contact_type") or "").strip().lower()
    if ctype in ("application", "application/resume", "application_resume", "resume"):
        ctype = "application-resume"
    set_radio_group(page, writer, fields, px + "contact-type", ctype)
    if ctype == "other" and "contact_type_other" in contact:
        set_text(
            page,
            writer,
            fields,
            px + "contact-type-other",
            contact.get("contact_type_other"),
        )

    # WorkSource activity
    set_text(
        page,
        writer,
        fields,
        px + "worksource-activity-kind",
        contact.get("worksource_activity_kind"),
    )
    set_text(
        page,
        writer,
        fields,
        px + "worksource-activity-documentation",
        contact.get("worksource_activity_documentation"),
    )
    set_text(
        page,
        writer,
        fields,
        px + "worksource-activity-office-name",
        contact.get("worksource_activity_office_name"),
    )
    set_text(
        page,
        writer,
        fields,
        px + "worksource-activity-city",
        contact.get("worksource_activity_city"),
    )
    set_text(
        page,
        writer,
        fields,
        px + "worksource-activity-state",
        contact.get("worksource_activity_state"),
    )

    # Other activity
    set_text(
        page,
        writer,
        fields,
        px + "other-activity-kind",
        contact.get("other_activity_kind"),
    )
    set_text(
        page,
        writer,
        fields,
        px + "other-activity-documentation",
        contact.get("other_activity_documentation"),
    )

    # Generic description
    set_text(page, writer, fields, px + "activity", contact.get("activity"))


def main() -> None:
    """Command-line entry point.

    Arguments (positional):
    - pdf_in: Path to the input PDF with form fields.
    - yaml_in: Path to a YAML file with 'name', 'ssn', 'week_ending' (or 'week-ending'),
               and a 'contacts' list (up to 3 entries).
    - pdf_out: Path to the output filled PDF to write.

    Behavior:
    - Loads YAML data, warns if fewer than 3 contacts are provided,
      clones the form structure into the writer, sets NeedAppearances,
      fills header and contact blocks, and writes the result.
    - Exits with code 2 on PDF read errors.
    """
    with tracer.start_as_current_span("fill_pdf_form") as span:
        start_time = time.time()
        try:
            parser = argparse.ArgumentParser(
                description="Fill WA ESD PDF (clean field names)."
            )
            parser.add_argument("pdf_in", help="Renamed/cleaned WA ESD PDF")
            parser.add_argument("yaml_in", help="Weekly YAML data file")
            parser.add_argument("pdf_out", help="Output filled PDF")
            parser.add_argument(
                "-v",
                "--verbose",
                action="store_true",
                help="Enable debug warnings for missing PDF fields",
            )
            args = parser.parse_args()

            # Add span attributes
            span.set_attribute("pdf.input_path", args.pdf_in)
            span.set_attribute("pdf.output_path", args.pdf_out)
            span.set_attribute("yaml.input_path", args.yaml_in)

            # Enable verbose via flag or ESD_VERBOSE env var
            global VERBOSE
            VERBOSE = bool(args.verbose or _is_truthy_env(os.getenv("ESD_VERBOSE")))

            # Load YAML data
            with tracer.start_as_current_span("load_yaml_data") as yaml_span:
                yaml_span.set_attribute("file.path", args.yaml_in)

                with open(args.yaml_in, "r", encoding="utf-8") as f:
                    data = yaml.safe_load(f) or {}

                contacts: List[Dict[str, Any]] = data.get("contacts", [])
                yaml_span.set_attribute("contacts.count", len(contacts))

            if len(contacts) < 3:
                print(
                    "Warning: fewer than 3 contacts in data; the form expects at least 3.",
                    file=sys.stderr,
                )

            # Read PDF
            with tracer.start_as_current_span("read_pdf") as pdf_span:
                pdf_span.set_attribute("file.path", args.pdf_in)
                reader = PdfReader(args.pdf_in)
                writer = PdfWriter()
                clone_form(reader, writer)
                set_need_appearances(writer)
                fields = reader.get_fields() or {}
                page = first_page(writer)

            # Fill header
            set_text(page, writer, fields, "name", data.get("name"))
            set_text(page, writer, fields, "ssn", data.get("ssn"))

            set_text(
                page,
                writer,
                fields,
                "week-ending",
                data.get("week_ending") or data.get("week-ending"),
            )

            # Enrich and fill contacts
            with tracer.start_as_current_span("enrich_contacts") as enrich_span:
                enrich_span.set_attribute("contacts.total", 3)
                enrich_span.set_attribute("contacts.provided", len(contacts))

                for idx in (1, 2, 3):
                    c = contacts[idx - 1] if len(contacts) >= idx else {}

                    business_name = c.get("business_name")

                    if not business_name:
                        _debug(
                            f"Contact {idx} missing business_name, skipping enrichment"
                        )

                        fill_contact_block(idx, c, page, writer, fields)
                        continue

                    with tracer.start_as_current_span(
                        f"enrich_contact_{idx}"
                    ) as contact_span:
                        enrichment_start = time.time()
                        contact_span.set_attribute("contact.index", idx)

                        contact_span.set_attribute(
                            "contact.business_name", business_name
                        )

                        try:
                            contact_info = contact_info_service.get_contact_info(
                                c["business_name"]
                            )

                            if "error" in contact_info:
                                contact_span.set_attribute("enrichment.success", False)

                                contact_span.set_attribute(
                                    "enrichment.error", contact_info["error"]
                                )

                                # Record failure metric
                                contact_enrichment_failed_counter.add(
                                    1,
                                    {
                                        "error_type": "business_not_found",
                                        "business_name": business_name,
                                    },
                                )

                                print(
                                    f"Warning: Could not enrich contact {idx}: {contact_info['error']}",
                                    file=sys.stderr,
                                )
                            else:
                                contact_span.set_attribute("enrichment.success", True)
                                c["address"] = contact_info["address"]
                                c["city"] = contact_info["city"]
                                c["state"] = contact_info["state"]
                                c["website_or_email"] = contact_info["website_or_email"]
                                c["phone"] = contact_info["phone"]

                                # Record success metric
                                contact_enriched_counter.add(
                                    1, {"business_name": business_name}
                                )
                        except Exception as e:
                            contact_span.set_attribute("enrichment.success", False)
                            contact_span.set_status(Status(StatusCode.ERROR))
                            contact_span.record_exception(e)

                            # Record failure metric
                            contact_enrichment_failed_counter.add(
                                1,
                                {
                                    "error_type": "exception",
                                    "business_name": business_name,
                                },
                            )

                            print(
                                f"Warning: Failed to enrich contact {idx} ({business_name}): {e}",
                                file=sys.stderr,
                            )
                        finally:
                            # Record enrichment duration
                            enrichment_duration_ms = (
                                time.time() - enrichment_start
                            ) * 1000

                            contact_enrichment_duration.record(
                                enrichment_duration_ms,
                                {
                                    "contact_index": str(idx),
                                    "business_name": business_name,
                                },
                            )

                    fill_contact_block(idx, c, page, writer, fields)

            # Write PDF
            with tracer.start_as_current_span("write_pdf") as write_span:
                write_span.set_attribute("file.path", args.pdf_out)

                with open(args.pdf_out, "wb") as out_f:
                    writer.write(out_f)

            span.set_attribute("pdf.processing_complete", True)

            # Record PDF processing metrics
            processing_duration_ms = (time.time() - start_time) * 1000

            pdf_processing_duration.record(
                processing_duration_ms, {"status": "success"}
            )

            pdf_processed_counter.add(1, {"status": "success"})

        except Exception as e:
            span.set_status(Status(StatusCode.ERROR))
            span.record_exception(e)

            # Record failure metrics
            processing_duration_ms = (time.time() - start_time) * 1000

            pdf_processing_duration.record(
                processing_duration_ms, {"status": "failure"}
            )

            pdf_processed_counter.add(1, {"status": "failure"})

            raise
        finally:
            shutdown_telemetry()


if __name__ == "__main__":
    try:
        main()
    except PdfReadError as e:
        print(f"PDF read error: {e}", file=sys.stderr)
        sys.exit(2)
