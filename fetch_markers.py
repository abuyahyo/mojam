"""Fetch shamela book 1687 HTML and extract c5 root-marker candidates per page.

Saves data/lisan/markers.json: {page_number: [first_c5_text_per_paragraph, ...]}
Only the FIRST c5 of each paragraph is captured — that's where Lisan places real
root markers; inline c5 spans (وَقِيلَ:, قَالَ:, etc.) are skipped.
"""
import io
import json
import re
import sys
import time
from pathlib import Path

import requests
from bs4 import BeautifulSoup

sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding="utf-8", errors="replace")

BOOK = 1687
OUT = Path(r"C:\mojam\data\lisan")
OUT.mkdir(parents=True, exist_ok=True)
PROGRESS = OUT / "markers_progress.json"

HEADERS = {
    "User-Agent": (
        "Mozilla/5.0 (Windows NT 10.0; Win64; x64) "
        "AppleWebKit/537.36 (KHTML, like Gecko) "
        "Chrome/126.0.0.0 Safari/537.36"
    ),
    "Accept-Language": "ar,en;q=0.8",
}
SESSION = requests.Session()
SESSION.headers.update(HEADERS)


def fetch(page, retries=4):
    url = f"https://shamela.ws/book/{BOOK}/{page}"
    for attempt in range(retries):
        try:
            r = SESSION.get(url, timeout=30)
            if r.status_code == 200:
                return r.text
            if r.status_code == 404:
                return ""
        except requests.RequestException:
            pass
        time.sleep(2 ** attempt)
    raise RuntimeError(f"failed page {page}")


def extract_first_c5_per_paragraph(html):
    """Return list of (paragraph_idx, c5_text) for the FIRST c5 span in each <p>."""
    soup = BeautifulSoup(html, "html.parser")
    nass = soup.select_one("div.nass")
    if not nass:
        return []
    out = []
    for i, p in enumerate(nass.find_all("p")):
        # First c5 child span — but skip if it appears after non-whitespace text
        first_c5 = None
        for el in p.descendants:
            if hasattr(el, "name") and el.name == "span" and "c5" in (el.get("class") or []):
                first_c5 = el
                break
            # if we hit a text node with substantial content before any c5, stop
            if not hasattr(el, "name"):
                txt = str(el).strip()
                if txt and len(txt) > 1:
                    break
        if first_c5 is None:
            continue
        # also check: the c5 must be at paragraph start (immediately after anchor span)
        prev_text = "".join(
            str(s).strip() for s in first_c5.previous_siblings
            if not (hasattr(s, "name") and s.name == "span"
                    and "anchor" in (s.get("class") or []))
        ).strip()
        if prev_text:
            continue
        text = first_c5.get_text(strip=True)
        if text:
            out.append([i, text])
    return out


def load_progress():
    if PROGRESS.exists():
        return json.loads(PROGRESS.read_text(encoding="utf-8"))
    return {}


def save_progress(state):
    PROGRESS.write_text(json.dumps(state, ensure_ascii=False), encoding="utf-8")


def main():
    state = load_progress()
    total = 8101
    delay = 0.3
    for p in range(1, total + 1):
        key = str(p)
        if key in state:
            continue
        html = fetch(p)
        markers = extract_first_c5_per_paragraph(html) if html else []
        state[key] = markers
        if p % 50 == 0 or p == total:
            save_progress(state)
            print(f"  saved through page {p}/{total}, recent: {markers[:3]}")
        time.sleep(delay)
    save_progress(state)


if __name__ == "__main__":
    main()
