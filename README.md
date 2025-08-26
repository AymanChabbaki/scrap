# Technopark startups scraper

This small script scrapes the page `https://www.technopark.ma/start-ups-du-mois/`, looks for JSON objects printed with `console.log(...)` inside script tags, extracts company information, and writes `companies.csv` grouped by sector.

Requirements
- Python 3.8+
- Install dependencies:

    pip install -r requirements.txt

Run

    python scrap.py

Output
- `companies.csv` in the current directory with fields: `secteur`, `name`, `description`, `website`, `raw`.

Notes
- If the page requires JS to produce the `console.log` output, you may need a headless browser (e.g., Playwright or Selenium). This script tries to extract JSON printed directly in inline script tags.
