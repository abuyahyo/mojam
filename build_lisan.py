"""Build Lisan al-Arab data files for mojam SPA.

Produces in C:\\mojam\\data\\lisan\\:
  - chunks/chunk_NNN.json  : page texts split into ~160-page chunks (~950KB each)
  - chunks.json            : chunk metadata [{idx, first_page, last_page, size_kb}]
  - roots.json             : flat root index [[root_norm, page, chunkIdx], ...]

Root detection: scan text-only data for short Arabic words at line start
followed by `:`. Apply strict filters to drop discourse markers and false
positives. Not perfect (~85-95% precision), but works without HTML re-fetch.
"""
import io
import json
import re
import sys
import unicodedata
from pathlib import Path

sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding="utf-8")

SRC = Path(r"C:\Users\abu_y\Desktop\lisan-al-arab\lisan.json")
OUT = Path(r"C:\mojam\data\lisan")
CHUNK_DIR = OUT / "chunks"
OUT.mkdir(parents=True, exist_ok=True)
CHUNK_DIR.mkdir(parents=True, exist_ok=True)

CHUNK_SIZE = 162  # pages per chunk → 50 chunks total, ~950KB each

AR_ALPHA = "ابتثجحخدذرزسشصضطظعغفقكلمنهوي"
NORM_MAP = str.maketrans({
    "أ": "ا", "إ": "ا", "آ": "ا",
    "ى": "ي", "ئ": "ي",
    "ؤ": "و", "ة": "ه",
})
TASHKEEL = re.compile(r"[ً-ْٰۖ-ۭـ]")

# Discourse / non-root single-word markers (after normalization)
STOPWORDS = {
    "يقال", "فيقال", "قال", "وقال", "قيل", "وقيل", "قلت", "نعم", "اقول",
    "اي", "ايضا", "والاصل", "والاول", "والثاني", "والثالث", "والمعنى",
    "والمراد", "اعلم", "يعني", "اعني", "وجمعه", "ومنه", "وكذلك",
    "وهكذا", "وزاد", "ومن", "ومنها", "وفيه", "وقد", "وقيل",
    "اللحياني", "الفراء", "الاصمعي", "الجوهري", "ابن", "ابو", "اخبرنا",
    "حدثنا", "روي", "وروي", "روى", "وروى",
}


def normalize(s: str) -> str:
    s = unicodedata.normalize("NFC", s)
    s = TASHKEEL.sub("", s)
    return s.translate(NORM_MAP)


def is_root_candidate(w: str) -> bool:
    """Word w is already normalized."""
    if not (2 <= len(w) <= 4):
        return False
    if w.startswith("ال"):
        return False
    if w in STOPWORDS:
        return False
    if not all(c in AR_ALPHA for c in w):
        return False
    return True


def load_pages():
    print("loading lisan.json ...")
    return json.load(open(SRC, encoding="utf-8"))


# Root candidate: line-start, 2-4 Arabic letters, then ":", then end-of-line
ROOT_RE = re.compile(r"(?:^|\n)([ء-ي]{2,6})\s*:\s*\n", re.MULTILINE)


def extract_roots(pages):
    out = []
    for p in pages:
        page = p["page"]
        text = normalize(p.get("text") or "")
        for m in ROOT_RE.finditer(text):
            w = m.group(1)
            if is_root_candidate(w):
                # dedupe consecutive identical
                if out and out[-1][0] == w and page == out[-1][1]:
                    continue
                out.append([w, page])
    return out


def build_chunks(pages):
    """Split pages into fixed-size chunks. Return [{idx, first, last}, ...]."""
    chunks = []
    total = len(pages)
    by_page = {p["page"]: p for p in pages}
    page_nums = sorted(by_page.keys())

    idx = 0
    for start in range(0, total, CHUNK_SIZE):
        end = min(start + CHUNK_SIZE, total)
        slice_nums = page_nums[start:end]
        first_page = slice_nums[0]
        last_page = slice_nums[-1]
        chunk_pages = [by_page[n] for n in slice_nums]
        fname = f"chunk_{idx:03d}.json"
        path = CHUNK_DIR / fname
        path.write_text(json.dumps(chunk_pages, ensure_ascii=False),
                        encoding="utf-8")
        size_kb = path.stat().st_size // 1024
        chunks.append({
            "idx": idx,
            "first_page": first_page,
            "last_page": last_page,
            "file": f"chunks/{fname}",
            "size_kb": size_kb,
        })
        idx += 1
    return chunks


def chunk_of_page(chunks, page):
    for c in chunks:
        if c["first_page"] <= page <= c["last_page"]:
            return c["idx"]
    return -1


def write_roots(roots, chunks):
    entries = [[r, p, chunk_of_page(chunks, p)] for r, p in roots]
    out = OUT / "roots.json"
    out.write_text(json.dumps(entries, ensure_ascii=False), encoding="utf-8")
    size_kb = out.stat().st_size // 1024
    print(f"  roots.json: {len(entries)} entries, {size_kb}KB")


def write_chunks_meta(chunks):
    (OUT / "chunks.json").write_text(
        json.dumps(chunks, ensure_ascii=False, indent=2), encoding="utf-8"
    )
    total = sum(c["size_kb"] for c in chunks)
    print(f"  chunks.json: {len(chunks)} chunks, total {total/1024:.1f} MB")


def main():
    pages = load_pages()
    print(f"  {len(pages)} pages loaded")

    print("extracting root markers ...")
    roots = extract_roots(pages)
    print(f"  {len(roots)} root candidates found")
    print(f"  first 20: {roots[:20]}")
    print(f"  last 20:  {roots[-20:]}")

    print("building chunks ...")
    chunks = build_chunks(pages)
    write_chunks_meta(chunks)

    print("writing root index ...")
    write_roots(roots, chunks)

    print("done.")


if __name__ == "__main__":
    main()
