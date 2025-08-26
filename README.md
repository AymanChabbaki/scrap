# Technopark startups scraper

This repository contains small tools to:

- scrape the Technopark "start-ups du mois" page and extract company data into `companies.csv` (runtime JS captured when needed),
- split that CSV into one file per sector under `by_sector/`, and
- send application emails (with CV attached) to contacts in a chosen sector using a configurable, env-driven template.

Quick setup
1. Create and activate a Python 3.8+ virtual environment (recommended).
2. Install dependencies:

```powershell
pip install -r requirements.txt
```

Sending applications (env-driven templates)
- The `send_applications.py` script sends emails to contacts listed in a sector CSV. Configuration is read from environment variables (or a `.env` file).

Required keys (put these into a `.env` in the repo root or export them in your shell):

- SMTP_SERVER (e.g. `smtp.gmail.com`)
- SMTP_PORT (e.g. `587`)
- SMTP_USER (SMTP username)
- SMTP_PASS (SMTP password or app-specific password)
- FROM_EMAIL (optional; defaults to SMTP_USER)
- CV_PATH (path to your CV PDF)
- SECTOR_CSV (optional default sector CSV path)
- YOUR_NAME (your full name)
- SUBJECT (optional default subject template)
- BODY_TEMPLATE (optional default body template)

Important: SUBJECT and BODY_TEMPLATE may use template placeholders from the CSV columns. The script injects two helpful variables derived from the CSV filename:

- `{sector_slug}` — the slug from the filename, e.g. `bio_tech` for `sector_bio_tech.csv`.
- `{sector}` — a human-friendly name where underscores are replaced with spaces, e.g. `bio tech`.

Example `.env` lines (use these in `.env` or export in PowerShell):

```powershell
SUBJECT=Candidature pour des opportunités en {sector}
BODY_TEMPLATE=Bonjour {contact_name},

Je me permets de vous contacter concernant les opportunités en {sector} chez {company}. Je joins mon CV.

Cordialement,
{your_name}
```

Run a dry-run preview (no emails sent):

```powershell
python .\send_applications.py --csv .\by_sector\sector_bio_tech.csv --cv .\path\to\CV.pdf --your-name "Prénom Nom" --dry-run
```

List available template variables (includes `{sector}` and `{sector_slug}`):

```powershell
python .\send_applications.py --csv .\by_sector\sector_bio_tech.csv --list-vars
```

When you are ready, run without `--dry-run` to actually send emails. The script logs outcomes to `sent_log.csv`.

Safety notes
- Start with `--dry-run` to preview personalised messages before sending.
- Use app-specific passwords for Gmail/Outlook where possible.
- Do not commit your real credentials — keep a local `.env` and add `.env` to `.gitignore`.

If you want, I can add an example `.env.example` snippet and a short wrapper to send to a limited test list first.
