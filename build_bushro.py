"""Convert a Bushro (Arabic↔Uzbek) source into data/bushro.json for the SPA.

The app expects an array of {root, text} objects (same shape as maqayis /
mufradat), where `root` is the Arabic headword and `text` is the Uzbek
translation/explanation. Search indexes both fields.

The Bushro data ships in third-party form (most likely a SQLite .db from the
Android app, but CSV / TSV / JSON are also supported). This script detects the
source type by extension, lets you inspect its structure, auto-guesses the
Arabic vs Uzbek columns, and writes the converted JSON.

USAGE
  # 1) See what's inside (tables, columns, sample rows) — start here:
  python build_bushro.py path/to/source.db --inspect

  # 2) Convert (auto-guess columns):
  python build_bushro.py path/to/source.db

  # 3) Convert with explicit mapping when auto-guess is wrong:
  python build_bushro.py source.db --table words --ar word --uz meaning
  python build_bushro.py source.csv --ar 0 --uz 1            # CSV by index
  python build_bushro.py source.json --ar arabic --uz uzbek  # JSON by key

  # Output path (default data/bushro.json):
  python build_bushro.py source.db --out data/bushro.json

Notes
  - data/bushro.json is gitignored on purpose (third-party, copyrighted by
    SamAndroidDeveloper); this script never commits it.
  - Only stdlib is used: sqlite3, csv, json.
"""
import argparse
import csv
import json
import re
import sqlite3
import sys
from pathlib import Path

AR_RE = re.compile(r"[؀-ۿݐ-ݿ]")      # Arabic
NON_AR_RE = re.compile(r"[A-Za-zЀ-ӿ]")          # Latin or Cyrillic (Uzbek)


def ar_score(values):
    """Fraction of sample values that look Arabic."""
    vals = [str(v) for v in values if v not in (None, "")][:200]
    if not vals:
        return 0.0
    return sum(1 for v in vals if AR_RE.search(v)) / len(vals)


def uz_score(values):
    vals = [str(v) for v in values if v not in (None, "")][:200]
    if not vals:
        return 0.0
    return sum(1 for v in vals if NON_AR_RE.search(v) and not AR_RE.search(v)) / len(vals)


# ----------------------------------------------------------------------------- SQLite
def sqlite_tables(con):
    cur = con.execute("SELECT name FROM sqlite_master WHERE type='table'")
    return [r[0] for r in cur.fetchall()]


def sqlite_columns(con, table):
    cur = con.execute(f'PRAGMA table_info("{table}")')
    return [r[1] for r in cur.fetchall()]


def sqlite_inspect(con):
    for t in sqlite_tables(con):
        cols = sqlite_columns(con, t)
        try:
            n = con.execute(f'SELECT COUNT(*) FROM "{t}"').fetchone()[0]
        except sqlite3.Error:
            n = "?"
        print(f"\nTABLE {t!r}  ({n} rows)")
        print("  columns:", ", ".join(cols))
        rows = con.execute(f'SELECT * FROM "{t}" LIMIT 3').fetchall()
        for r in rows:
            cells = [(c[:40] + "…" if isinstance(c, str) and len(c) > 40 else c) for c in r]
            print("   ", cells)


def sqlite_extract(con, table, ar_col, uz_col):
    tables = sqlite_tables(con)
    if not table:
        # pick the table whose columns best separate into an Arabic + non-Arabic pair
        best, best_score = None, -1
        for t in tables:
            cols = sqlite_columns(con, t)
            sample = con.execute(f'SELECT * FROM "{t}" LIMIT 200').fetchall()
            by_col = {c: [row[i] for row in sample] for i, c in enumerate(cols)}
            a = max(cols, key=lambda c: ar_score(by_col[c]), default=None)
            u = max((c for c in cols if c != a), key=lambda c: uz_score(by_col[c]), default=None)
            s = (ar_score(by_col[a]) if a else 0) + (uz_score(by_col[u]) if u else 0)
            if s > best_score:
                best, best_score, table = t, s, t
        if best is None:
            sys.exit("No tables found. Run with --inspect.")
    cols = sqlite_columns(con, table)
    sample = con.execute(f'SELECT * FROM "{table}" LIMIT 200').fetchall()
    by_col = {c: [row[i] for row in sample] for i, c in enumerate(cols)}
    if not ar_col:
        ar_col = max(cols, key=lambda c: ar_score(by_col[c]))
    if not uz_col:
        uz_col = max((c for c in cols if c != ar_col), key=lambda c: uz_score(by_col[c]))
    print(f"  table={table!r}  arabic={ar_col!r}  uzbek={uz_col!r}")
    rows = con.execute(f'SELECT "{ar_col}", "{uz_col}" FROM "{table}"').fetchall()
    return [(r[0], r[1]) for r in rows]


# ----------------------------------------------------------------------------- CSV / TSV
def delim_extract(path, ar_col, uz_col, delim):
    with open(path, encoding="utf-8-sig", newline="") as f:
        rows = [r for r in csv.reader(f, delimiter=delim) if r]
    if not rows:
        return []
    header = rows[0]
    # First row is a header when it has no Arabic yet the rows below do
    # (i.e. it holds column labels like "arabic","word","meaning").
    row0_ar = bool(AR_RE.search(" ".join(map(str, header))))
    below_ar = any(AR_RE.search(" ".join(map(str, r))) for r in rows[1:6])
    has_header = (not row0_ar) and below_ar
    body = rows[1:] if has_header else rows

    def resolve(col, fallback):
        if col is None:
            return fallback
        if str(col).lstrip("-").isdigit():
            return int(col)
        if not has_header:
            sys.exit(f"No header row detected; reference columns by index, not name ({col!r}).")
        return header.index(col)

    width = max(len(r) for r in rows)
    cols = list(range(width))
    by_col = {i: [r[i] for r in body[:200] if i < len(r)] for i in cols}
    ai = resolve(ar_col, max(cols, key=lambda i: ar_score(by_col[i])))
    ui = resolve(uz_col, max((i for i in cols if i != ai), key=lambda i: uz_score(by_col[i])))
    print(f"  arabic=col[{ai}]  uzbek=col[{ui}]  header={'yes' if has_header else 'no'}")
    return [(r[ai], r[ui]) for r in body if len(r) > max(ai, ui)]


# ----------------------------------------------------------------------------- JSON
def json_extract(path, ar_key, uz_key):
    data = json.loads(Path(path).read_text(encoding="utf-8"))
    if isinstance(data, dict):  # {arabic: uzbek, ...}
        if not (ar_key or uz_key):
            return list(data.items())
    if not isinstance(data, list) or not data or not isinstance(data[0], dict):
        sys.exit("Unsupported JSON shape; expected array of objects or a flat map.")
    keys = list(data[0].keys())
    by_key = {k: [d.get(k) for d in data[:200]] for k in keys}
    if not ar_key:
        ar_key = max(keys, key=lambda k: ar_score(by_key[k]))
    if not uz_key:
        uz_key = max((k for k in keys if k != ar_key), key=lambda k: uz_score(by_key[k]))
    print(f"  arabic={ar_key!r}  uzbek={uz_key!r}")
    return [(d.get(ar_key), d.get(uz_key)) for d in data]


# ----------------------------------------------------------------------------- main
def build(pairs):
    out, seen = [], set()
    for root, text in pairs:
        root = (str(root).strip() if root is not None else "")
        text = (str(text).strip() if text is not None else "")
        if not root or not text:
            continue
        key = (root, text)
        if key in seen:
            continue
        seen.add(key)
        out.append({"root": root, "text": text})
    return out


def main():
    ap = argparse.ArgumentParser(description="Convert Bushro source → data/bushro.json")
    ap.add_argument("source", help="path to .db/.sqlite, .csv/.tsv, or .json")
    ap.add_argument("--inspect", action="store_true", help="print structure and exit (SQLite)")
    ap.add_argument("--table", help="SQLite table name")
    ap.add_argument("--ar", help="Arabic column/key (name or index)")
    ap.add_argument("--uz", help="Uzbek column/key (name or index)")
    ap.add_argument("--out", default="data/bushro.json", help="output path")
    args = ap.parse_args()

    src = Path(args.source)
    if not src.exists():
        sys.exit(f"Source not found: {src}")
    ext = src.suffix.lower()

    if ext in (".db", ".sqlite", ".sqlite3"):
        con = sqlite3.connect(str(src))
        con.text_factory = lambda b: b.decode("utf-8", "replace")
        if args.inspect:
            sqlite_inspect(con)
            return
        pairs = sqlite_extract(con, args.table, args.ar, args.uz)
    elif ext in (".csv", ".tsv", ".txt"):
        delim = "\t" if ext in (".tsv", ".txt") else ","
        pairs = delim_extract(src, args.ar, args.uz, delim)
    elif ext == ".json":
        pairs = json_extract(src, args.ar, args.uz)
    else:
        sys.exit(f"Unsupported extension {ext!r}. Use .db/.sqlite, .csv/.tsv, or .json.")

    entries = build(pairs)
    if not entries:
        sys.exit("No entries produced — check column mapping with --inspect / --ar / --uz.")
    outp = Path(args.out)
    outp.parent.mkdir(parents=True, exist_ok=True)
    outp.write_text(json.dumps(entries, ensure_ascii=False), encoding="utf-8")
    kb = outp.stat().st_size // 1024
    print(f"\n✓ wrote {outp}  —  {len(entries)} entries, {kb} KB")
    print("  sample:", json.dumps(entries[0], ensure_ascii=False)[:120])


if __name__ == "__main__":
    main()
