import re
import pandas as pd
import requests
from bs4 import BeautifulSoup

from scoring import score_grad_suitability

CFC_POSTINGS_URL = "https://cfc.pinpointhq.com/postings.json"  # Pinpoint job feed :contentReference[oaicite:1]{index=1}

HEADERS = {
    "User-Agent": "grad-job-scraper (personal project; respectful rate-limited)"
}

UK_LOCATION_HINTS = {
    "gb", "uk", "united kingdom",
    "london", "manchester", "leeds", "bristol", "birmingham", "glasgow", "edinburgh", "belfast"
}

def html_to_text(html: str) -> str:
    if not html:
        return ""
    soup = BeautifulSoup(html, "html.parser")
    text = soup.get_text(" ", strip=True)
    return re.sub(r"\s+", " ", text).strip()

def is_uk_role(location_name: str) -> bool:
    """
    CFC Pinpoint locations often look like 'GB - London' :contentReference[oaicite:2]{index=2}
    We'll keep anything that looks UK-ish.
    """
    loc = (location_name or "").strip().lower()
    if loc.startswith("gb") or "united kingdom" in loc:
        return True
    return any(hint in loc for hint in UK_LOCATION_HINTS)

def fetch_cfc_postings() -> list[dict]:
    r = requests.get(CFC_POSTINGS_URL, headers=HEADERS, timeout=30)
    r.raise_for_status()
    payload = r.json()
    return payload.get("data", [])

def main():
    postings = fetch_cfc_postings()

    rows = []
    for p in postings:
        title = p.get("title", "")
        url = p.get("url", "")
        department = (p.get("department") or {}).get("name", "")
        location_name = (p.get("location") or {}).get("name", "")
        employment_type = p.get("employment_type_text", "") or p.get("employment_type", "")

        # UK-only filter
        if not is_uk_role(location_name):
            continue

        # Combine key sections so the scorer has
