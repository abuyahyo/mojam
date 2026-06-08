"""Rebuild Lisan al-Arab data from page-based chunks into root-entry chunks.

The original build (build_lisan.py) stored Lisan by PAGE because the source was
page-based. That forced the SPA to load a whole page (which may hold several
roots) and slice out the searched entry at runtime. This script removes the
page layer entirely: it concatenates the book in order, splits it into one
entry per root (same marker rules as build_lisan.py), and re-chunks those
entries for lazy loading — so Lisan behaves like maqayis / mufradat.

Reads existing  data/lisan/chunks/chunk_*.json  (page arrays) + chunks.json.
Writes (overwriting):
  - data/lisan/chunks/chunk_NNN.json : [{root, text}, ...]  (~950KB each)
  - data/lisan/chunks.json           : [{idx, file, start, count, size_kb}]
  - data/lisan/roots.json            : [[root_norm, chunkIdx, entryIdx], ...]
                                       (array order == global reading order)
"""
import json
import re
from pathlib import Path

OUT = Path("data/lisan")
CHUNK_DIR = OUT / "chunks"
TARGET_BYTES = 950 * 1024  # per output chunk

NORM_MAP = str.maketrans({
    "أ": "ا", "إ": "ا", "آ": "ا", "ٱ": "ا",
    "ى": "ي", "ئ": "ي", "ؤ": "و", "ة": "ه",
})
TASHKEEL = re.compile(r"[ً-ْٰۖ-ۭـ]")

STOPWORDS = {
    "يقال", "فيقال", "قال", "وقال", "قيل", "وقيل", "قلت", "نعم", "اقول",
    "اي", "ايضا", "والاصل", "والاول", "والثاني", "والثالث", "والمعنى",
    "والمراد", "اعلم", "يعني", "اعني", "وجمعه", "ومنه", "وكذلك",
    "وهكذا", "وزاد", "ومن", "ومنها", "وفيه", "وقد",
    "اللحياني", "الفراء", "الاصمعي", "الجوهري", "ابن", "ابو", "اخبرنا",
    "حدثنا", "روي", "وروي", "روى", "وروى",
}

MARKER_RE = re.compile(r"^([ء-ي]{2,6})\s*:$")


def normalize(s: str) -> str:
    s = TASHKEEL.sub("", s or "")
    s = s.translate(NORM_MAP)
    return re.sub(r"\s+", " ", s).strip()


def is_root_candidate(w: str) -> bool:
    if not (2 <= len(w) <= 4):
        return False
    if w.startswith("ال"):
        return False
    if w in STOPWORDS:
        return False
    return True


def load_pages_in_order():
    meta = json.loads((OUT / "chunks.json").read_text(encoding="utf-8"))
    meta.sort(key=lambda c: c["idx"])
    pages = []
    for c in meta:
        arr = json.loads((OUT / c["file"]).read_text(encoding="utf-8"))
        pages.extend(arr)  # each chunk's pages already in page order
    return pages


def split_entries(pages, blessed):
    """Concatenate the book and split into [(root_norm, text), ...].

    A line is an entry boundary only when it is a bare "root:" marker AND that
    root is in `blessed` (the curated headword set). Single-word-colon glosses
    inside an entry (وتفض:, وهو: ...) are not headwords, so they stay as part
    of the entry text instead of fragmenting it. Each blessed root opens an
    entry the first time it is seen in reading order; later repeats are
    absorbed as text."""
    lines = []
    for p in pages:
        t = p.get("text") or ""
        lines.extend(t.split("\n"))

    entries = []
    used = set()
    cur_root = None
    cur_lines = []

    def flush():
        if cur_root is not None:
            text = "\n".join(cur_lines).strip()
            if text:
                entries.append((cur_root, text))

    for line in lines:
        m = MARKER_RE.match(normalize(line))
        root = m.group(1) if m else None
        if root and root in blessed and root not in used:
            flush()
            used.add(root)
            cur_root = root
            cur_lines = []  # drop the marker line itself; heading shows the root
        elif cur_root is not None:
            cur_lines.append(line)
    flush()
    return entries


def write_chunks(entries):
    for f in CHUNK_DIR.glob("chunk_*.json"):
        f.unlink()

    chunks_meta = []
    roots = []
    idx = 0
    i = 0
    n = len(entries)
    while i < n:
        buf = []
        start = i
        size = 2  # for [ ]
        while i < n and (size < TARGET_BYTES or not buf):
            root, text = entries[i]
            obj = {"root": root, "text": text}
            buf.append(obj)
            size += len(json.dumps(obj, ensure_ascii=False).encode("utf-8")) + 1
            roots.append([root, idx, i - start])
            i += 1
        fname = f"chunk_{idx:03d}.json"
        path = CHUNK_DIR / fname
        path.write_text(json.dumps(buf, ensure_ascii=False), encoding="utf-8")
        chunks_meta.append({
            "idx": idx,
            "file": f"chunks/{fname}",
            "start": start,
            "count": len(buf),
            "size_kb": path.stat().st_size // 1024,
        })
        idx += 1

    (OUT / "chunks.json").write_text(
        json.dumps(chunks_meta, ensure_ascii=False, indent=2), encoding="utf-8")
    (OUT / "roots.json").write_text(
        json.dumps(roots, ensure_ascii=False), encoding="utf-8")
    total_mb = sum(c["size_kb"] for c in chunks_meta) / 1024
    print(f"  {idx} chunks, {len(roots)} entries, total {total_mb:.1f} MB")


def load_blessed():
    """Curated headword set = roots from the shipped page-based roots.json.

    Read from git HEAD so it survives this script overwriting roots.json."""
    import subprocess
    raw = subprocess.check_output(
        ["git", "show", "HEAD:data/lisan/roots.json"], text=True)
    return {r[0] for r in json.loads(raw) if r and r[0]}


def main():
    print("loading curated headword set ...")
    blessed = load_blessed()
    print(f"  {len(blessed)} blessed roots")
    print("loading page chunks ...")
    pages = load_pages_in_order()
    print(f"  {len(pages)} pages")
    print("splitting into root entries ...")
    entries = split_entries(pages, blessed)
    print(f"  {len(entries)} entries")
    print(f"  first 5 roots: {[e[0] for e in entries[:5]]}")
    print(f"  last 5 roots:  {[e[0] for e in entries[-5:]]}")
    print("writing entry chunks ...")
    write_chunks(entries)
    print("done.")


if __name__ == "__main__":
    main()
