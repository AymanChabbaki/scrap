
"""
scrap_playwright.py

Uses Playwright to open the page, capture runtime console messages (including objects),
extract the JSON payload containing company details, and write companies.csv grouped by sector.

Usage:
    python scrap_playwright.py

Note: After installing `playwright`, run `python -m playwright install` to install browser binaries.
"""
from collections import defaultdict
import json
import csv
import time
import argparse

from playwright.async_api import async_playwright


def find_companies_list(obj):
    if isinstance(obj, list) and obj and isinstance(obj[0], dict):
        keys = set(k.lower() for k in obj[0].keys())
        if keys & {"name", "title", "nom", "company"}:
            return obj

    if isinstance(obj, dict):
        for k, v in obj.items():
            found = find_companies_list(v)
            if found:
                return found

    if isinstance(obj, list):
        for item in obj:
            found = find_companies_list(item)
            if found:
                return found

    return None


def normalize_company(rec: dict) -> dict:
    lower = {k.lower(): v for k, v in rec.items()}
    name = lower.get("name") or lower.get("title") or lower.get("nom") or lower.get("company") or ""
    secteur = lower.get("secteur") or lower.get("sector") or lower.get("categorie") or lower.get("category") or ""
    website = lower.get("website") or lower.get("site") or lower.get("url") or ""
    description = lower.get("description") or lower.get("desc") or lower.get("resume") or ""
    return {
        "name": name,
        "secteur": secteur,
        "website": website,
        "description": description,
        "raw": json.dumps(rec, ensure_ascii=False),
    }


def write_csv(companies: list, out_path: str):
    companies_sorted = sorted(companies, key=lambda c: (c.get("secteur") or "", c.get("name") or ""))
    fieldnames = ["secteur", "name", "description", "website", "raw"]
    with open(out_path, "w", encoding="utf-8", newline="") as f:
        writer = csv.DictWriter(f, fieldnames=fieldnames)
        writer.writeheader()
        for c in companies_sorted:
            writer.writerow({k: c.get(k, "") for k in fieldnames})


import asyncio

def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--url", default="https://www.technopark.ma/start-ups-du-mois/")
    parser.add_argument("--output", default="companies.csv")
    args = parser.parse_args()

    asyncio.run(run_playwright(args))


async def run_playwright(args):
    captured = []

    async with async_playwright() as p:
        browser = await p.chromium.launch(headless=True)
        page = await browser.new_page()

        # Inject a wrapper for console.log before any scripts run so we capture
        # the real runtime console.log arguments in a serializable form.
        await page.add_init_script("""
        (() => {
            window.__captured_console = window.__captured_console || [];
            const orig = console.log.bind(console);
            console.log = function(...args) {
                try {
                    const serial = args.map(a => {
                        try { return JSON.parse(JSON.stringify(a)); }
                        catch (e) { try { return String(a); } catch { return null; } }
                    });
                    window.__captured_console.push(serial);
                } catch (e) { }
                orig(...args);
            };
        })();
        """)

        async def on_console(msg):
            # Try to extract JSON-serializable args via json_value
            for arg in msg.args:
                try:
                    val = await arg.json_value()
                    captured.append(val)
                except Exception:
                    # fallback to text
                    try:
                        captured.append(msg.text)
                    except Exception:
                        pass

        page.on("console", on_console)
        print("Opening page...")
        await page.goto(args.url, wait_until="networkidle")

        # give some extra time for scripts that run after load
        await asyncio.sleep(2)

        # after navigation and a short wait, pull captured console messages
        await asyncio.sleep(1)

        # read captured console logs from the page
        try:
            captured_from_page = await page.evaluate("() => window.__captured_console || []")
            # extend our captured list with any new captures
            if isinstance(captured_from_page, list):
                captured.extend(captured_from_page)
        except Exception:
            pass

        await browser.close()

    # look through captured items for a company list
    companies_list = None
    for item in captured:
        if item is None:
            continue
        found = find_companies_list(item)
        if found:
            companies_list = found
            break

    # Diagnostic: print capture summary to help debug when no direct match is found
    if companies_list is None:
        print(f"Captured {len(captured)} console entries. Inspecting for large arrays of dicts...")
        # find the largest list whose elements are dict-like
        best = None
        best_len = 0
        for idx, item in enumerate(captured):
            # item might be a list of args (e.g., ["label", [...objects...]
            # or nested lists/objects. Traverse to find inner lists.
            def walk(o):
                if isinstance(o, list):
                    # if it's a list of dicts
                    if o and all(isinstance(x, dict) for x in o):
                        return o
                    for sub in o:
                        res = walk(sub)
                        if res:
                            return res
                if isinstance(o, dict):
                    for v in o.values():
                        res = walk(v)
                        if res:
                            return res
                return None

            candidate = walk(item)
            if candidate and len(candidate) > best_len:
                best = candidate
                best_len = len(candidate)

        if best:
            print(f"Found candidate list with {best_len} items (using fallback).")
            companies_list = best

    if companies_list is None:
        # also check if any captured item is a JSON string that can be parsed
        for item in captured:
            if isinstance(item, str):
                try:
                    obj = json.loads(item)
                except Exception:
                    continue
                found = find_companies_list(obj)
                if found:
                    companies_list = found
                    break

    if not companies_list:
        print("No company list found in console messages.")
        return

    companies = [normalize_company(c) for c in companies_list if isinstance(c, dict)]
    if not companies:
        print("Found company list but no valid dicts inside.")
        return

    write_csv(companies, args.output)
    print(f"Wrote {len(companies)} companies to {args.output}")


if __name__ == "__main__":
    main()
