"""
split_by_sector.py

Reads `companies.csv` (created by the scraper), parses the `raw` JSON column to
extract company fields, and writes one CSV per value in
`EntrepriseSecteurActivite`. If a company lists multiple sectors separated by
`;` it will be written to each sector CSV. The Id field is discarded.

Usage:
    python split_by_sector.py

Output: files named like `sector_<sanitized_sector>.csv` in the same folder.
"""
import csv
import json
import os
import re
from collections import defaultdict

INPUT = "companies.csv"
OUT_DIR = "by_sector"


def sanitize_filename(s: str) -> str:
    s = s.strip().lower()
    s = re.sub(r"\s+", "_", s)
    s = re.sub(r"[^a-z0-9_\-]", "", s)
    return s[:120] or "unknown"


def parse_raw(raw: str) -> dict:
    if not raw:
        return {}
    try:
        # raw should already be a JSON text; load it
        return json.loads(raw)
    except Exception:
        # sometimes raw might be double-encoded (string containing JSON string)
        try:
            return json.loads(raw.strip('"'))
        except Exception:
            return {}


def important_fields(obj: dict) -> dict:
    # Pick a compact set of useful fields (drop Id)
    return {
        "EntrepriseName": obj.get("EntrepriseName") or obj.get("EntrepriseNom") or "",
        "EntrepriseVille": obj.get("EntrepriseVille") or "",
        "EntrepriseTechnologie": obj.get("EntrepriseTechnologie") or "",
        "EntrepriseSecteurActivite": obj.get("EntrepriseSecteurActivite") or "",
        "EntrepriseContactSiteWeb": obj.get("EntrepriseContactSiteWeb") or "",
        "EntrepriseContactPhone": obj.get("EntrepriseContactPhone") or "",
        "EntrepriseContactName": obj.get("EntrepriseContactName") or "",
        "EntrepriseContactEmail": obj.get("EntrepriseContactEmail") or "",
        "EntrepriseLogo": obj.get("EntrepriseLogo") or "",
        "Activite": obj.get("Activite") or "",
    }


def main():
    if not os.path.exists(INPUT):
        print(f"{INPUT} not found in current folder.")
        return

    os.makedirs(OUT_DIR, exist_ok=True)

    sectors = defaultdict(list)

    with open(INPUT, newline='', encoding='utf-8') as f:
        reader = csv.DictReader(f)
        for row in reader:
            raw = row.get('raw')
            parsed = parse_raw(raw) if raw else {}
            rec = important_fields(parsed)

            sector_field = rec.get('EntrepriseSecteurActivite') or ''
            if not sector_field:
                sectors['NO_SECTEUR'].append(rec)
                continue

            # sector_field may contain multiple sectors separated by ';'
            parts = [p.strip() for p in re.split(r"[;,]", sector_field) if p.strip()]
            if not parts:
                sectors['NO_SECTEUR'].append(rec)
            else:
                for s in parts:
                    sectors[s].append(rec)

    # Write per-sector CSVs
    for sector, rows in sectors.items():
        safe = sanitize_filename(sector)
        out_path = os.path.join(OUT_DIR, f"sector_{safe}.csv")
        fieldnames = [
            'EntrepriseName', 'EntrepriseVille', 'EntrepriseTechnologie',
            'EntrepriseContactSiteWeb', 'EntrepriseContactPhone', 'EntrepriseContactName',
            'EntrepriseContactEmail', 'EntrepriseLogo', 'Activite', 'EntrepriseSecteurActivite'
        ]
        with open(out_path, 'w', encoding='utf-8', newline='') as outf:
            writer = csv.DictWriter(outf, fieldnames=fieldnames)
            writer.writeheader()
            for r in rows:
                writer.writerow({k: r.get(k, '') for k in fieldnames})
        print(f"Wrote {len(rows)} rows to {out_path}")


if __name__ == '__main__':
    main()
