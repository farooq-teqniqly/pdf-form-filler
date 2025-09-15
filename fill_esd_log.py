"""Command-line interface for filling a weekly job-search log PDF form."""

import argparse
import yaml
from pypdf import PdfReader, PdfWriter
from pypdf.generic import NameObject, BooleanObject, DictionaryObject


def load_mapping(path: str):
    """Load field aliases and checkbox mappings from a YAML file.

    Args:
        path (str): Path to the YAML mapping file.

    Returns:
        tuple: (aliases dict, checkboxes dict)
    """
    with open(path, "r", encoding="utf-8") as f:
        config = yaml.safe_load(f)
    return config.get("aliases", {}), config.get("checkboxes", {})


def _set_need_appearances(writer: PdfWriter):
    """Ensure the PDF writer sets the /NeedAppearances flag for AcroForm
    fields.

    Args:
        writer (PdfWriter): The PDF writer object.
    """
    if "/AcroForm" not in writer._root_object:
        writer._root_object.update(
            {NameObject("/AcroForm"): writer._add_object(DictionaryObject())}
        )
    writer._root_object["/AcroForm"].update(
        {NameObject("/NeedAppearances"): BooleanObject(True)}
    )


def _find_field(form_fields: dict, candidates: list[str]) -> str | None:
    """Find the first matching field name from candidates in the form fields.

    Args:
        form_fields (dict): Dictionary of form fields.
        candidates (list[str]): List of candidate field names.

    Returns:
        str | None: The first matching field name, or None if not found.
    """
    for c in candidates:
        if c in form_fields:
            return c
    return None


def _set_text(page, writer, form_fields, aliases, key, value):
    """Set a text field value in the PDF form.

    Args:
        page: The PDF page object.
        writer: The PDF writer object.
        form_fields (dict): Dictionary of form fields.
        aliases (dict): Aliases mapping for field names.
        key (str): Logical field key.
        value: Value to set.
    """
    name = _find_field(form_fields, aliases.get(key, []))
    if name and value is not None:
        writer.update_page_form_field_values(page, {name: str(value)})


def _set_checkbox(page, writer, field_name, on: bool):
    """Set a checkbox field value in the PDF form.

    Args:
        page: The PDF page object.
        writer: The PDF writer object.
        field_name (str): Name of the checkbox field.
        on (bool): Whether to check (True) or uncheck (False) the box.
    """
    if field_name:
        writer.update_page_form_field_values(page, {field_name: "Yes" if on else "Off"})


def fill(pdf_in: str, yaml_in: str, pdf_out: str, map_in: str):
    """Fill a PDF form using data from a YAML file and field mappings.

    Args:
        pdf_in (str): Path to the blank PDF form.
        yaml_in (str): Path to the YAML data file.
        pdf_out (str): Path to output the filled PDF.
        map_in (str): Path to the YAML mapping file.
    """
    aliases, checkboxes = load_mapping(map_in)
    with open(yaml_in, "r", encoding="utf-8") as f:
        data = yaml.safe_load(f)

    contacts = data.get("contacts", [])
    if len(contacts) < 3:
        raise SystemExit("Need at least 3 contacts/activities for the week.")

    reader = PdfReader(pdf_in)
    writer = PdfWriter()
    writer.clone_document_from_reader(reader)
    _set_need_appearances(writer)

    fields = reader.get_fields() or {}
    page = writer.pages[0]

    # header
    _set_text(page, writer, fields, aliases, "week_ending", data.get("week_ending"))
    _set_text(page, writer, fields, aliases, "name", data.get("name"))
    _set_text(page, writer, fields, aliases, "id_or_ssn", data.get("id_or_ssn"))

    # contacts 1..3
    for idx in (1, 2, 3):
        c = contacts[idx - 1]
        p = f"c{idx}"

        _set_text(page, writer, fields, aliases, f"{p}.date", c.get("date"))
        _set_text(
            page,
            writer,
            fields,
            aliases,
            f"{p}.job_title_or_ref",
            c.get("job_title_or_ref"),
        )
        _set_text(page, writer, fields, aliases, f"{p}.employer", c.get("employer"))
        _set_text(page, writer, fields, aliases, f"{p}.address", c.get("address"))
        _set_text(page, writer, fields, aliases, f"{p}.city", c.get("city"))
        _set_text(page, writer, fields, aliases, f"{p}.state", c.get("state"))
        _set_text(
            page,
            writer,
            fields,
            aliases,
            f"{p}.website_or_email",
            c.get("website_or_email"),
        )
        _set_text(page, writer, fields, aliases, f"{p}.phone", c.get("phone"))
        _set_text(
            page, writer, fields, aliases, f"{p}.what_activity", c.get("what_activity")
        )
        _set_text(
            page, writer, fields, aliases, f"{p}.documentation", c.get("documentation")
        )
        _set_text(
            page, writer, fields, aliases, f"{p}.office_name", c.get("office_name")
        )

        # kind
        kind = (c.get("kind") or "").strip().lower()
        if f"{p}.kind" in checkboxes:
            for label, field in checkboxes[f"{p}.kind"].items():
                _set_checkbox(page, writer, field, label.lower() in kind)

        # method
        method = (c.get("contact_method") or "").strip().lower()
        if f"{p}.method" in checkboxes:
            for label, field in checkboxes[f"{p}.method"].items():
                _set_checkbox(page, writer, field, label.lower() in method)

        # type
        ctype = (c.get("contact_type") or "").strip().lower()
        if f"{p}.type" in checkboxes:
            for label, field in checkboxes[f"{p}.type"].items():
                _set_checkbox(page, writer, field, label.lower() in ctype)

    with open(pdf_out, "wb") as f:
        writer.write(f)


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description="Fill a weekly job-search log PDF")
    parser.add_argument("pdf_in", help="Blank PDF file")
    parser.add_argument("yaml_in", help="Weekly YAML data file")
    parser.add_argument("pdf_out", help="Output filled PDF")
    parser.add_argument(
        "--map", required=True, help="YAML mapping file with aliases + checkboxes"
    )

    args = parser.parse_args()
    fill(args.pdf_in, args.yaml_in, args.pdf_out, args.map)
