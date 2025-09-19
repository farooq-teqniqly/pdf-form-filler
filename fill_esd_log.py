from __future__ import annotations
from pypdf import PdfReader, PdfWriter
from pypdf.errors import PdfReadError
from pypdf.generic import NameObject, BooleanObject, DictionaryObject
import argparse, yaml, sys
from typing import Any, Dict, List

# ----------------------------------------------------------
# Helpers
# ----------------------------------------------------------


def clone_form(reader: PdfReader, writer: PdfWriter) -> None:
    """
    Copy the AcroForm (/Fields) tree into the writer
    so update_page_form_field_values works.
    """
    try:
        writer.clone_document_from_reader(reader)  # pypdf >= 4.0
    except Exception:
        writer.append_pages_from_reader(reader)
        acro = reader.trailer["/Root"].get("/AcroForm")
        if acro is not None:
            writer._root_object[NameObject("/AcroForm")] = writer._add_object(acro)


def set_need_appearances(writer: PdfWriter) -> None:
    if "/AcroForm" not in writer._root_object:
        writer._root_object.update(
            {NameObject("/AcroForm"): writer._add_object(DictionaryObject())}
        )
    writer._root_object["/AcroForm"].update(
        {NameObject("/NeedAppearances"): BooleanObject(True)}
    )


def set_text(
    page, writer: PdfWriter, fields: Dict[str, Any], field_name: str, value: Any
) -> None:
    if not field_name or field_name not in fields:
        return
    writer.update_page_form_field_values(
        page, {field_name: "" if value is None else str(value)}
    )


def _collect_on_states(obj) -> List[str]:
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
    on_states: List[str] = []
    try:
        fobj = fields[field_name]
        try:
            fobj = fobj.get_object()
        except Exception:
            pass
        on_states.extend(_collect_on_states(fobj))
        if "/Kids" in fobj:
            for kid in fobj["/Kids"]:
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
    if not field_name or field_name not in fields:
        return
    on_value = detect_on_state(fields, field_name)
    writer.update_page_form_field_values(
        page, {field_name: (f"/{on_value}" if on else "/Off")}
    )


def _radio_on_values(fields: dict, group_name: str) -> list[str]:
    vals = []
    try:
        fobj = fields[group_name]
        try:
            fobj = fobj.get_object()
        except Exception:
            pass
        if "/Kids" in fobj:
            for kid in fobj["/Kids"]:
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
    page, writer: PdfWriter, fields: dict, group_name: str, desired: str | None
) -> None:
    if not desired or group_name not in fields:
        return
    opts = _radio_on_values(fields, group_name)
    dl = desired.strip().lower()
    # exact match
    for o in opts:
        if o.lower() == dl:
            writer.update_page_form_field_values(page, {group_name: f"/{o}"})
            return
    # contains match
    for o in opts:
        if dl in o.lower():
            writer.update_page_form_field_values(page, {group_name: f"/{o}"})
            return
    # fallback
    if opts:
        writer.update_page_form_field_values(page, {group_name: f"/{opts[0]}"})


def first_page(writer: PdfWriter):
    return writer.pages[0]


# ----------------------------------------------------------
# Contact filling
# ----------------------------------------------------------

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
        set_checkbox(
            page,
            writer,
            fields,
            field_name,
            any(label.lower() in (m or "").lower() for m in methods),
        )

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


# ----------------------------------------------------------
# Main
# ----------------------------------------------------------


def main() -> None:
    parser = argparse.ArgumentParser(description="Fill WA ESD PDF (clean field names).")
    parser.add_argument("pdf_in", help="Renamed/cleaned WA ESD PDF")
    parser.add_argument("yaml_in", help="Weekly YAML data file")
    parser.add_argument("pdf_out", help="Output filled PDF")
    args = parser.parse_args()

    with open(args.yaml_in, "r", encoding="utf-8") as f:
        data = yaml.safe_load(f) or {}

    contacts: List[Dict[str, Any]] = data.get("contacts", [])
    if len(contacts) < 3:
        print(
            "Warning: fewer than 3 contacts in data; the form expects at least 3.",
            file=sys.stderr,
        )

    reader = PdfReader(args.pdf_in)
    writer = PdfWriter()
    clone_form(reader, writer)
    set_need_appearances(writer)

    fields = reader.get_fields() or {}
    page = first_page(writer)

    # Header
    set_text(page, writer, fields, "name", data.get("name"))
    set_text(page, writer, fields, "ssn", data.get("ssn"))
    set_text(
        page,
        writer,
        fields,
        "week-ending",
        data.get("week_ending") or data.get("week-ending"),
    )

    # Contacts
    for idx in (1, 2, 3):
        c = contacts[idx - 1] if len(contacts) >= idx else {}
        fill_contact_block(idx, c, page, writer, fields)

    with open(args.pdf_out, "wb") as out_f:
        writer.write(out_f)


if __name__ == "__main__":
    try:
        main()
    except PdfReadError as e:
        print(f"PDF read error: {e}", file=sys.stderr)
        sys.exit(2)
