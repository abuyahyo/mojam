# المعاجم · mojam

A fast, offline-capable web app for searching classical Arabic dictionaries in
one place. Type a root or a word and get matching entries from four lexicons
side by side.

**Live:** <https://abuyahyo.github.io>

## Dictionaries

| Key        | Book              | Author                         | Direction      |
|------------|-------------------|--------------------------------|----------------|
| `lisan`    | لسان العرب        | Ibn Manẓūr                     | Arabic         |
| `maqayis`  | مقاييس اللغة      | Ibn Fāris                      | Arabic         |
| `mufradat` | المفردات          | al-Rāghib al-Iṣfahānī          | Arabic         |
| `bushro`   | أوزبكي (بشرى)     | —                              | Arabic ↔ Uzbek |

## Features

- **Unified search** across all four books, grouped by source.
- **Arabic-aware matching** — diacritics (tashkīl), hamza/alif and tā'-marbūṭa
  variants are ignored; an inflected word is mapped to its root.
- **Arabic ↔ Uzbek** — typing Latin or Cyrillic Uzbek searches the Bushro
  dictionary in reverse (Cyrillic is transliterated to Latin first).
- **Readable typesetting** — Qur'ānic āyāt are coloured green, poetry (أبيات)
  is centred and italic, editor footnotes are collected at the foot of the
  entry, and the terse Bushro/Uzbek abbreviations are expanded in full.
- **Installable PWA** — works fully offline; Lisan is pre-fetched in the
  background after first load.

## How it works

The app is a single static `index.html` (inline CSS + JS) plus a service
worker and JSON data — **no build step and no framework**. It is served as-is
from GitHub Pages.

```
index.html              the whole SPA (search + rendering)
sw.js                   service worker (offline cache)
manifest.webmanifest    PWA manifest
icon*.png · icon.svg    app icons
data/
  maqayis.json          [{root, text}, …]
  mufradat.json         [{root, text}, …]
  bushro.json           [{root, text}, …]   Arabic → Uzbek
  bushro_uz.json        [{root, text}, …]   Uzbek (Latin) → Arabic
  lisan/
    roots.json          [[root_norm, chunkIdx, entryIdx], …]  search index
    chunks.json         [{idx, file, start, count, size_kb}, …]
    chunks/chunk_NNN.json   [{root, text}, …]  (lazy-loaded, ~950 KB each)
```

Maqayis, Mufradat and Bushro are loaded whole. Lisan (~47 MB) is indexed by
`roots.json` and its chunks are fetched lazily on demand, then pre-warmed in
the background for offline use.

## Running locally

Any static file server works (a service worker needs `http://`, not `file://`):

```sh
python3 -m http.server 8000
# open http://localhost:8000
```

## Regenerating the data

The Python scripts rebuild the JSON from their original sources (run manually,
not part of the deploy):

- `build_lisan.py` / `rebuild_lisan_entries.py` — build the Lisan chunks +
  `roots.json` index.
- `build_bushro.py` — convert the Bushro source into `bushro.json` /
  `bushro_uz.json`.
- `fetch_markers.py`, `fix_mufradat_splits.py` — scraping / data-repair helpers.

After changing anything under `data/`, bump `DATA_VERSION` in `sw.js` so clients
fetch the new files (see `CLAUDE.md`).

## Service worker / updates

A pre-commit hook bumps the shell cache version on every commit so installed
PWAs auto-update. Enable it once per clone:

```sh
git config core.hooksPath .githooks
```

## Notes

- The Bushro source artifacts are kept local (git-ignored); only the converted
  `data/bushro.json` / `data/bushro_uz.json` are published.
- The dictionary texts are scraped from public digital editions and may contain
  occasional extraction artifacts; the renderer cleans up many of them.
