from __future__ import annotations

from pypdf import PdfReader, PdfWriter
from pypdf.errors import PdfReadError
from pypdf.generic import NameObject, BooleanObject, DictionaryObject
import argparse, yaml, sys
from typing import Any, Dict, List


def clone_form(reader: PdfReader, writer: PdfWriter) -> None:
    """
    Ensure the PdfWriter contains the full AcroForm (/Fields tree),
    so update_page_form_field_values works reliably.
    """
    try:
        writer.clone_document_from_reader(reader)  # pypdf >= 4.0
    except Exception:
        # Fallback for older versions
        acro = reader.trailer["/Root"].get("/AcroForm")
        if acro is not None:
            writer.append_pages_from_reader(reader)
            writer._root_object[NameObject("/AcroForm")] = writer._add_object(acro)
        else:
            writer.append_pages_from_reader(reader)


def set_need_appearances(writer: PdfWriter) -> None:
    # Ensure values render in some viewers
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
    if value is None:
        value = ""
    writer.update_page_form_field_values(page, {field_name: str(value)})


def set_checkbox(
    page, writer: PdfWriter, fields: Dict[str, Any], field_name: str, on: bool
) -> None:
    if not field_name or field_name not in fields:
        return
    writer.update_page_form_field_values(page, {field_name: "Yes" if on else "Off"})


def first_page(writer: PdfWriter):
    return writer.pages[0]


# ---------------------------
# Main filler
# ---------------------------

CONTACT_METHOD_FIELDS = [
    ("In-person", "contact-in-person"),
    ("Online", "contact-online"),
    ("By phone", "contact-by-phone"),
    ("By email", "contact-by-email"),
    ("By mail", "contact-by-mail"),
    ("Other", "contact-other"),
]

CONTACT_TYPE_MAP = {
    # For "cX-contact-type" (string). If "Other", fill cX-contact-type-other as well.
    "application/resume": "Application/resume",
    "interview": "Interview",
    "inquiry": "Inquiry",
    "other": "Other",
}


def fill_contact_block(
    idx: int,
    contact: Dict[str, Any],
    page,
    writer: PdfWriter,
    fields: Dict[str, Any],
) -> None:
    """
    Map data -> simplified field names for contact 1..3.
    idx is 1, 2, or 3.
    """
    px = f"c{idx}-"

    # Common text fields for employer contact section
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

    # Contact method checkboxes (zero/one/many)
    method_raw = contact.get("contact_method")
    # Accept single string or list of strings
    if isinstance(method_raw, str):
        methods = [method_raw]
    elif isinstance(method_raw, list):
        methods = method_raw
    else:
        methods = []

    for label, suffix in CONTACT_METHOD_FIELDS:
        field_name = f"{px}{suffix}"
        set_checkbox(
            page,
            writer,
            fields,
            field_name,
            any(label.lower() in (m or "").lower() for m in methods),
        )

    # Contact type (choose one, but we'll be tolerant)
    ctype = (contact.get("contact_type") or "").strip().lower()
    if ctype:
        display = CONTACT_TYPE_MAP.get(ctype, contact.get("contact_type"))
        set_text(page, writer, fields, px + "contact-type", display)
        if "other" in ctype:
            set_text(
                page,
                writer,
                fields,
                px + "contact-type-other",
                contact.get("contact_type_other"),
            )

    # WorkSource activity (if provided)
    # kind (string), documentation (string), office and location
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

    # Other activity (if provided)
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

    # Generic "activity" (if you store a simple description)
    set_text(page, writer, fields, px + "activity", contact.get("activity"))


def main() -> None:
    parser = argparse.ArgumentParser(
        description="Fill WA ESD PDF (simplified field names)."
    )
    parser.add_argument(
        "pdf_in", help="Renamed/cleaned WA ESD PDF (with simplified field names)"
    )
    parser.add_argument("yaml_in", help="Weekly YAML data file")
    parser.add_argument("pdf_out", help="Output filled PDF")
    args = parser.parse_args()

    # Load data
    with open(args.yaml_in, "r", encoding="utf-8") as f:
        data = yaml.safe_load(f) or {}

    contacts: List[Dict[str, Any]] = data.get("contacts", [])
    if len(contacts) < 3:
        print(
            "Warning: fewer than 3 contacts in data; the form expects at least 3.",
            file=sys.stderr,
        )

    # Read + prepare PDF
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

    # Contacts 1..3 (fill only if present)
    for idx in (1, 2, 3):
        c = contacts[idx - 1] if len(contacts) >= idx else {}
        fill_contact_block(idx, c, page, writer, fields)

    # Save
    with open(args.pdf_out, "wb") as out_f:
        writer.write(out_f)


if __name__ == "__main__":
    try:
        main()
    except PdfReadError as e:
        print(f"PDF read error: {e}", file=sys.stderr)
        sys.exit(2)
