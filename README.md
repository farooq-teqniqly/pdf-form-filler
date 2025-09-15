# PDF Form Filler

PDF Form Filler is a command-line tool for automatically filling out weekly job-search log PDF forms using structured YAML data. It is designed to help users quickly generate completed forms for submission, and to make onboarding and contribution easy for developers.

## Features

- Fill out job-search log PDFs using YAML data
- Supports field aliases and checkbox mapping for flexible PDF templates
- Simple command-line interface
- Easily extensible and customizable

## Getting Started

### Prerequisites

- Python 3.12 or later
- [pip](https://pip.pypa.io/en/stable/)

### Installation

1. Clone the repository:

   ```sh
   git clone https://github.com/farooq-teqniqly/pdf-form-filler.git
   cd pdf-form-filler
   ```

2. (Recommended) Create and activate a virtual environment:

   ```sh
   python -m venv venv
   # On Windows:
   .\venv\Scripts\activate
   # On macOS/Linux:
   source venv/bin/activate
   ```

3. Install dependencies:
   ```sh
   pip install -r requirements.txt
   ```

## Usage

### Prepare Your Files

- **Blank PDF**: The original, unfilled job-search log PDF form.
- **YAML Data File**: Contains the weekly job-search data (see `week.yaml` for an example).
- **Mapping File**: YAML file mapping logical field names to PDF field names and checkboxes (see `esd_log_mapping.yaml`).

### Example Command

```sh
python fill_esd_log.py <blank.pdf> <week.yaml> <output.pdf> --map esd_log_mapping.yaml
```

#### Example:

```sh
python fill_esd_log.py blank_log.pdf week.yaml filled_log.pdf --map esd_log_mapping.yaml
```

### YAML Data Example

See `week.yaml` for a sample structure:

```yaml
week_ending: "09/13/2025"
name: "John Doe"
id_or_ssn: "999-99-9999"
contacts:
  - date: "09/08/2025"
	 kind: "Employer contact"
	 contact_method: "Online"
	 contact_type: "Application/resume"
	 job_title_or_ref: "Senior Software Engineer"
	 employer: "Evergreen Tech Solutions"
	 address: "4250 Innovation Way"
	 city: "Bellevue"
	 state: "WA"
	 website_or_email: "https://www.evergreentechsolutions.com"
	 phone: "(425) 555-1212"
  # ... add at least 3 contacts
```

### Mapping File Example

See `esd_log_mapping.yaml` for a sample structure. This file maps logical field names to the actual PDF field names and checkboxes.

## Development & Contribution

1. Fork this repository and clone your fork.
2. Create a new branch for your feature or bugfix.
3. Make your changes and add tests if applicable.
4. Submit a pull request with a clear description of your changes.

### Code Style

- This project uses [black](https://black.readthedocs.io/) and [docformatter](https://github.com/PyCQA/docformatter) for code formatting.
- Run `black .` and `docformatter .` before submitting a PR.

## License

This project is licensed under the MIT License. See the [LICENSE](LICENSE) file for details.

## Support

For questions, issues, or feature requests, please open an issue on GitHub.
