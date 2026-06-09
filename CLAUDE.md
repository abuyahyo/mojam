# CLAUDE.md

Guidance for working in this repo. See `README.md` for the user-facing overview.

## What this is

A static, no-build PWA that searches four Arabic dictionaries (Lisan al-Arab,
Maqayis al-Lugha, Mufradat, and Bushro Arabic↔Uzbek). Everything the browser
runs lives in **`index.html`** (inline `<style>` + `<script>`), with `sw.js`
for offline caching and JSON under `data/`. There is **no framework, no
bundler, no build step** — edit `index.html` directly and deploy is just a
push to `main` (GitHub Pages).

## Architecture

- **`index.html`** — one file. Loads data, runs search, renders cards.
- **`sw.js`** — service worker. Navigation = network-first; data = cache-first.
- **`data/`** — see README for the file shapes. Key points:
  - `maqayis.json`, `mufradat.json`, `bushro.json` (AR→UZ), `bushro_uz.json`
    (UZ→AR, Latin) are arrays of `{root, text}` loaded whole at startup.
  - **Lisan is chunked**: `roots.json` = `[[norm_root, chunkIdx, entryIdx], …]`
    in reading order (the search index); `chunks/chunk_NNN.json` =
    `[{root, text}, …]` loaded lazily by `(chunkIdx, entryIdx)`. `roots.json`
    stores **explicit** indices, so you can drop an entry from it without
    shifting the others.

## The rendering pipeline (`cardBody` in index.html)

`cardBody(text, own, src)` turns a raw entry into HTML. The text is split into
paragraphs and each is classified/transformed. Source-specific behaviour:

- **Maqayis sense markers** — `فالأول`, `والأصل الثاني`, `وأمّا الثالث`, bare
  ordinals after a full stop → wrapped in `.sense` (dark-red bold), each on its
  own paragraph. Maqayis only (diacritic-tolerant).
- **Verses (أبيات)** — a whole paragraph that is two hemistichs split by a
  central ellipsis (`…` in Maqayis/Lisan, `...` in Mufradat) → `.verse`
  (centred, italic). Non-Bushro.
- **Qur'ān āyāt → green (`.ayah`, ﴿…﴾):** `{…}` braces; a verse preceding a
  `[sura/N]` citation (incl. a citation on the *next* paragraph, folded back);
  Lisan's `وفي التنزيل[ العزيز]:` intro and its anaphoric `وفيه:` continuations
  (tracked via a Qur'ān-context flag so a `وفيه` pointing at a hadith is left
  alone).
- **Editor footnotes (محقّق)** — two formats: Maqayis `— (N) …` (em-dash) and
  Lisan `(N). …` (bare, dot required). Detected by `FOOTNOTE_HEAD`, collected
  and rendered together at the **foot** of the entry.
- **Lisan reflow** — Lisan's source is split into sub-sentence fragments;
  consecutive plain fragments are merged into one paragraph per sentence
  (break on `. ؟ !`), keeping āyāt/verses/footnotes as their own blocks.
  Lisan only.
- **Bushro (AR→UZ, `.aruz-card` → LTR body):**
  - numbered senses `N)` and homograph headers `N.` → own line, bold
    (`.sense-num`);
  - **morphology tail** (hyphen-joined, e.g. `I-а-بَحْثٌ`, `ko'p.-أبيات`,
    `2-ko'p.-أبيات`) → `formatBushroMorph` → labeled Arabic line
    (`مصدر`/`جمع`/`مثنى`/`مؤنث`/`انظر`, with a `٢)` sense prefix when present);
  - **abbreviation expansion** (`expandBushroAbbr`) — verb rection
    (`n.gadir`→nimagadir, `k.nidir`→kimnidir, `tush.k.`→tushum kelishigi),
    grammar (`shun.`→shuningdek, `majh.`, `gram.`) and field labels
    (`bot.`→botanika, `med.`→tibbiyot …). Word-boundary anchored.

## Search

- `normalize()` strips tashkīl, unifies `أإآٱ→ا`, `ة→ه`, `ى→ي`, `ؤ→و`, `ئ→ي`,
  lowercases, collapses spaces. Used for both the index and the query.
- Title search ranks exact > prefix > substring > lemma-prefix (a root that is
  a prefix of an inflected query with ≤2 trailing letters dropped). Body search
  is the fallback when titles return nothing.
- A Latin/Cyrillic query is treated as Uzbek → searches `bushro_uz` (Cyrillic
  transliterated to Latin first). Bushro lookups prefer an **exact** match when
  one exists (so `حمد` doesn't surface `أحمد`/`حمدل`).

## Caching & versions (`sw.js`)

- `VERSION` (shell cache) is **auto-bumped on every commit** by
  `.githooks/pre-commit`. Don't edit it by hand. Installed PWAs reload once
  when it changes.
- `DATA_VERSION` (data + lisan caches) is bumped **by hand only when files
  under `data/` change**. Routine shell deploys keep the ~15 MB of dictionary
  data cached instead of re-downloading it. **If you edit any `data/` file,
  bump `DATA_VERSION`** (e.g. `v3`→`v4`), or clients keep the stale copy.

## Conventions / gotchas

- **Render-time over data edits.** Prefer fixing presentation in `index.html`
  (reversible, no multi-MB diff, no `DATA_VERSION` bump). Only edit `data/`
  for genuine content fixes (e.g. re-stitching a wrongly-split Lisan entry).
- **Data fixes & the Lisan index.** When you change `data/lisan/chunks/*`,
  keep `roots.json` consistent. Removing a junk entry = drop its `[root, …]`
  row from `roots.json` (indices are explicit, others are unaffected) and blank
  its slot in the chunk to preserve positions; then bump `DATA_VERSION`.
- **Big LTR/RTL detail.** Bushro AR→UZ bodies are Latin Uzbek and must render
  LTR (`.aruz-card .body`), or numbered senses get bidi-reordered.
- **PWA reload.** `index.html` reloads controlled tabs only on a *new* SW
  (controllerchange), never on first install.
- Enable the version-bump hook once per clone: `git config core.hooksPath .githooks`.

## Testing a change

There are no automated tests. To sanity-check rendering/search logic, extract
the relevant pure function(s) and run them under `node` against real
`data/` entries (this is how the parsing rules above were validated). To see
the app, serve the folder over `http://` (`python3 -m http.server`) — a service
worker won't run from `file://`.
