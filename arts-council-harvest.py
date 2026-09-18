#!/usr/bin/env python3
"""
Harvest and clean selected Arts Council of Ireland funding decisions, 2022–2027.

Source:
    https://artscouncil.ie/funding/funding-decisions/

Included programmes:
    - Arts Centre Partnership Funding
      (including historical Arts Centre(s) Funding naming)
    - Arts Grant Funding
    - Strategic Funding
    - Festivals Investment Scheme
      (all published rounds collapsed to one fund label)

Scope:
    The dataset is restricted to these four funding programmes because they
    focus on organisations as opposed to individuals.

Project context:
    This code was produced as part of Minimal Curation: Minimal Computing for
    Sustainable Digital Sociocultural Heritage, funded by Research Ireland.

The script traverses the site's FacetWP pagination, parses award records,
applies the documented scope/normalisation rules, and writes the final
six-column CSV plus a separate audit JSON.
"""

from __future__ import annotations

import argparse
import csv
import html as html_module
import json
import re
from collections import Counter, defaultdict
from html.parser import HTMLParser
from pathlib import Path
from urllib.parse import urlencode

from playwright.sync_api import TimeoutError as PlaywrightTimeoutError, sync_playwright

BASE_URL = "https://artscouncil.ie/funding/funding-decisions/"
YEARS = list(range(2022, 2028))
FUNDS = [
    "Arts Centre Partnership Funding",
    "Arts Grant Funding",
    "Strategic Funding",
    "Festivals Investment Scheme",
]
OUTPUT_COLUMNS = [
    "year",
    "fund",
    "recipient",
    "location",
    "artform",
    "amount_awarded",
]

EURO_RE = re.compile(r"€\s*([\d,]+(?:\.\d{1,2})?)")
YEAR_RE = re.compile(r"\b(20\d{2})\b")
LABELS = {"round name", "location", "artform", "amount awarded"}
BLOCK_TAGS = {
    "address", "article", "aside", "blockquote", "br", "div", "dl", "dt", "dd",
    "fieldset", "figcaption", "figure", "footer", "form", "h1", "h2", "h3",
    "h4", "h5", "h6", "header", "hr", "li", "main", "nav", "ol", "p",
    "pre", "section", "table", "tbody", "td", "tfoot", "th", "thead", "tr", "ul",
}

ARTS_CENTRE_NAMES = (
    "arts centre partnership funding",
    "arts centres partnership funding",
    "arts centre funding",
    "arts centres funding",
)

ARTFORM_NORMALISATION = {
    "Litearture (English Language)": "Literature (English language)",
    "Multidisciplinary arts": "Multidisciplinary Arts",
    "Trad Arts": "Traditional Arts",
    "Arts Participation": "Participatory Arts",
}

EXCLUDED_ROUNDS = {
    "2022 arts centre funding - touring",
    "2023 arts centre funding - touring",
    "2022 strategic funding - touring",
    "2023 strategic funding - touring",
    "2024 strategic funding - access",
    "2024 strategic funding - touring",
}


def clean(value: str | None) -> str:
    if not value:
        return ""
    value = html_module.unescape(value).replace("\xa0", " ")
    return re.sub(r"\s+", " ", value).strip()


def clean_line(value: str) -> str:
    value = clean(value)
    return "" if value == "^" else value.strip(" ^\t\r\n")


def dash_normalise(value: str) -> str:
    value = clean(value).replace("–", "-").replace("—", "-")
    value = re.sub(r"\s*-\s*", " - ", value)
    return clean(value).casefold()


def amount_to_number(value: str):
    match = EURO_RE.search(value or "")
    if not match:
        return None
    number = float(match.group(1).replace(",", ""))
    return int(number) if number.is_integer() else number


class VisibleTextParser(HTMLParser):
    """Turn rendered HTML into line-oriented visible text."""

    def __init__(self):
        super().__init__(convert_charrefs=True)
        self.parts = []
        self.skip_depth = 0

    def handle_starttag(self, tag, attrs):
        tag = tag.lower()
        if tag in {"script", "style", "noscript", "svg"}:
            self.skip_depth += 1
            return
        if not self.skip_depth and tag in BLOCK_TAGS:
            self.parts.append("\n")

    def handle_endtag(self, tag):
        tag = tag.lower()
        if tag in {"script", "style", "noscript", "svg"}:
            if self.skip_depth:
                self.skip_depth -= 1
            return
        if not self.skip_depth and tag in BLOCK_TAGS:
            self.parts.append("\n")

    def handle_data(self, data):
        if not self.skip_depth and data:
            self.parts.append(data)

    def text(self):
        return "".join(self.parts)


def html_to_lines(markup: str) -> list[str]:
    parser = VisibleTextParser()
    parser.feed(markup)
    return [x for x in (clean_line(v) for v in parser.text().splitlines()) if x]


def find_next_value(lines, start, stop_labels):
    for index in range(start, min(len(lines), start + 20)):
        value = clean_line(lines[index])
        if value and value.casefold().rstrip(":") not in stop_labels:
            return value, index
    return "", start


def previous_recipient(lines, round_label_index):
    noise_prefixes = (
        "panel:", "the arts council received", "please select both", "filter results",
        "year", "fund", "location", "artform", "amount awarded", "round name",
    )
    for index in range(round_label_index - 1, max(-1, round_label_index - 15), -1):
        value = clean_line(lines[index])
        if not value:
            continue
        low = value.casefold().rstrip(":")
        if EURO_RE.search(value):
            break
        if low in LABELS or any(low.startswith(p) for p in noise_prefixes):
            continue
        if low in {"apply now", "read more", "clear", "search", "next", "previous"}:
            continue
        return value
    return ""


def parse_awards(markup: str, selected_year: int) -> list[dict]:
    lines = html_to_lines(markup)
    rows = []
    index = 0

    while index < len(lines):
        if lines[index].casefold().rstrip(":") != "round name":
            index += 1
            continue

        recipient = previous_recipient(lines, index)
        round_name, round_index = find_next_value(lines, index + 1, LABELS)
        if not round_name:
            index += 1
            continue

        location = artform = amount_text = ""
        end = min(len(lines), index + 45)
        cursor = round_index + 1

        while cursor < end:
            low = lines[cursor].casefold().rstrip(":")
            if low == "location":
                location, cursor = find_next_value(lines, cursor + 1, LABELS)
            elif low == "artform":
                artform, cursor = find_next_value(lines, cursor + 1, LABELS)
            elif low == "amount awarded":
                for amount_index in range(cursor + 1, min(end, cursor + 8)):
                    if EURO_RE.search(lines[amount_index]):
                        amount_text = lines[amount_index]
                        cursor = amount_index
                        break
                if amount_text:
                    break
            elif low == "round name" and cursor != index:
                break
            cursor += 1

        amount = amount_to_number(amount_text)
        year_match = YEAR_RE.search(round_name)
        year = int(year_match.group(1)) if year_match else selected_year

        if recipient and amount is not None:
            rows.append({
                "year": year,
                "round_name": round_name,
                "recipient": recipient,
                "location": location,
                "artform": artform,
                "amount_awarded": amount,
            })
        index += 1

    return rows


def normalise_fund(round_name: str):
    low = clean(round_name).casefold()
    if any(name in low for name in ARTS_CENTRE_NAMES):
        return "Arts Centre Partnership Funding"
    if "arts grant funding" in low:
        return "Arts Grant Funding"
    if "strategic funding" in low:
        return "Strategic Funding"
    if "festivals investment scheme" in low:
        return "Festivals Investment Scheme"
    return None


def wait_for_results(page, old_html=None):
    try:
        page.wait_for_function(
            "() => !document.querySelector('.facetwp-loading, .fwp-loading')",
            timeout=15000,
        )
    except PlaywrightTimeoutError:
        pass

    if old_html is not None:
        try:
            page.wait_for_function(
                """old => {
                    const el = document.querySelector('.facetwp-template');
                    return el && el.innerHTML !== old;
                }""",
                arg=old_html,
                timeout=15000,
            )
        except PlaywrightTimeoutError:
            pass
    page.wait_for_timeout(700)


def get_template_html(page):
    template = page.locator(".facetwp-template")
    return template.first.inner_html() if template.count() else page.content()


def current_page_number(page):
    active = page.locator(".facetwp-page.active")
    if active.count():
        data_page = active.first.get_attribute("data-page")
        if data_page and data_page.isdigit():
            return int(data_page)
        text = clean(active.first.inner_text())
        if text.isdigit():
            return int(text)
    return 1


def next_page_locator(page):
    next_link = page.locator(".facetwp-page.next")
    if next_link.count():
        return next_link.first

    current = current_page_number(page)
    pages = page.locator(".facetwp-page[data-page]")
    candidates = []
    for index in range(pages.count()):
        link = pages.nth(index)
        data_page = link.get_attribute("data-page")
        if data_page and data_page.isdigit() and int(data_page) > current:
            candidates.append((int(data_page), link))
    return sorted(candidates, key=lambda x: x[0])[0][1] if candidates else None


def click_next(page):
    next_link = next_page_locator(page)
    if next_link is None:
        return False

    css_class = next_link.get_attribute("class") or ""
    aria_disabled = next_link.get_attribute("aria-disabled") or ""
    if "disabled" in css_class.casefold() or aria_disabled.casefold() == "true":
        return False

    old_html = get_template_html(page)
    try:
        next_link.click(force=True, timeout=10000)
    except Exception:
        data_page = next_link.get_attribute("data-page")
        if not data_page or not data_page.isdigit():
            return False
        try:
            page.evaluate(
                """target => {
                    if (!window.FWP) throw new Error('FacetWP API not available');
                    FWP.paged = target;
                    FWP.soft_refresh = true;
                    FWP.refresh();
                }""",
                int(data_page),
            )
        except Exception:
            return False

    wait_for_results(page, old_html)
    return get_template_html(page) != old_html


def deduplicate_raw(rows):
    seen, output = set(), []
    for row in rows:
        key = (
            row["year"], clean(row["round_name"]).casefold(),
            clean(row["recipient"]).casefold(), clean(row["location"]).casefold(),
            clean(row["artform"]).casefold(), float(row["amount_awarded"]),
        )
        if key not in seen:
            seen.add(key)
            output.append(row)
    return output


def clean_dataset(raw_rows):
    cleaned, excluded = [], []
    for row in raw_rows:
        fund = normalise_fund(row["round_name"])
        if row["year"] not in YEARS or fund is None:
            continue

        if dash_normalise(row["round_name"]) in EXCLUDED_ROUNDS:
            excluded.append(row)
            continue

        cleaned.append({
            "year": row["year"],
            "fund": fund,
            "recipient": clean(row["recipient"]),
            "location": clean(row["location"]),
            "artform": ARTFORM_NORMALISATION.get(clean(row["artform"]), clean(row["artform"])),
            "amount_awarded": row["amount_awarded"],
        })

    seen, final = set(), []
    for row in cleaned:
        key = tuple(row[c] for c in OUTPUT_COLUMNS)
        if key not in seen:
            seen.add(key)
            final.append(row)

    final.sort(key=lambda r: (int(r["year"]), r["fund"].casefold(), r["recipient"].casefold(), float(r["amount_awarded"])))
    return final, excluded


def harvest(headless=True):
    raw_rows, pages_visited = [], []
    with sync_playwright() as p:
        browser = p.chromium.launch(headless=headless)
        page = browser.new_page(
            viewport={"width": 1440, "height": 1200},
            user_agent=(
                "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) "
                "AppleWebKit/537.36 (KHTML, like Gecko) "
                "Chrome/140.0.0.0 Safari/537.36"
            ),
        )
        try:
            for year in YEARS:
                url = BASE_URL + "?" + urlencode({"_funding_decision_year": str(year)})
                print(f"\nYEAR {year}")
                page.goto(url, wait_until="domcontentloaded", timeout=60000)
                wait_for_results(page)

                page_no, seen_templates = 1, set()
                while True:
                    markup = get_template_html(page)
                    fingerprint = hash(markup)
                    if fingerprint in seen_templates:
                        print("  repeated result page detected; stopping pagination")
                        break
                    seen_templates.add(fingerprint)

                    rows = parse_awards(markup, year)
                    raw_rows.extend(rows)
                    pages_visited.append({"year": year, "page": page_no, "parsed_rows": len(rows), "url": page.url})
                    print(f"  page {page_no}: {len(rows)} awards parsed")

                    if not click_next(page):
                        break
                    page_no += 1
                    if page_no > 500:
                        raise RuntimeError(f"Pagination exceeded 500 pages for {year}")
        finally:
            browser.close()

    return deduplicate_raw(raw_rows), pages_visited


def validate(rows):
    duplicate_rows = len(rows) - len({tuple(r[c] for c in OUTPUT_COLUMNS) for r in rows})
    missing = Counter()
    for row in rows:
        for col in OUTPUT_COLUMNS:
            if row[col] is None or str(row[col]).strip() == "":
                missing[col] += 1

    counts = Counter((str(r["year"]), r["fund"]) for r in rows)
    totals = defaultdict(float)
    for row in rows:
        totals[(str(row["year"]), row["fund"])] += float(row["amount_awarded"])

    return {
        "row_count": len(rows),
        "total_amount_awarded": sum(float(r["amount_awarded"]) for r in rows),
        "duplicate_rows": duplicate_rows,
        "missing_values": dict(missing),
        "non_positive_amounts": sum(1 for r in rows if float(r["amount_awarded"]) <= 0),
        "counts_by_year_fund": {f"{y} | {f}": n for (y, f), n in sorted(counts.items())},
        "totals_by_year_fund": {f"{y} | {f}": v for (y, f), v in sorted(totals.items())},
    }


def parse_args():
    parser = argparse.ArgumentParser(description="Harvest the curated Arts Council funding dataset.")
    parser.add_argument("--output", default="arts-council-funding-2022-2027.csv")
    parser.add_argument("--audit", default="arts-council-funding-2022-2027-audit.json")
    parser.add_argument("--headful", action="store_true", help="Show Chromium while harvesting")
    return parser.parse_args()


def main():
    args = parse_args()
    raw_rows, pages_visited = harvest(headless=not args.headful)
    rows, excluded = clean_dataset(raw_rows)
    validation = validate(rows)

    with Path(args.output).open("w", newline="", encoding="utf-8-sig") as handle:
        writer = csv.DictWriter(handle, fieldnames=OUTPUT_COLUMNS)
        writer.writeheader()
        writer.writerows(rows)

    audit = {
        "source": BASE_URL,
        "years_requested": YEARS,
        "funds_included": FUNDS,
        "raw_unique_awards_parsed": len(raw_rows),
        "excluded_touring_access_rows": len(excluded),
        "pages_visited": pages_visited,
        "validation": validation,
        "known_validation_note": (
            "At the September 2026 harvest, the live Funding Decisions database yielded "
            "213 Arts Grant Funding 2026 awards, while the Arts Council's 1 August 2025 "
            "announcement described 218 recipients. No missing awards are fabricated."
        ),
    }
    Path(args.audit).write_text(json.dumps(audit, ensure_ascii=False, indent=2), encoding="utf-8")

    print("\nDONE")
    print(f"Raw unique awards parsed: {len(raw_rows):,}")
    print(f"Excluded Touring/Access records: {len(excluded):,}")
    print(f"Final dataset rows: {len(rows):,}")
    print(f"Total amount awarded: €{validation['total_amount_awarded']:,.2f}")
    print(f"Duplicate rows: {validation['duplicate_rows']}")
    print(f"Wrote CSV: {args.output}")
    print(f"Wrote audit: {args.audit}")

    print("\nCounts by year/fund:")
    for year in YEARS:
        for fund in FUNDS:
            key = f"{year} | {fund}"
            count = validation["counts_by_year_fund"].get(key, 0)
            total = validation["totals_by_year_fund"].get(key, 0.0)
            print(f"  {key}: {count} awards | €{total:,.2f}")


if __name__ == "__main__":
    main()
