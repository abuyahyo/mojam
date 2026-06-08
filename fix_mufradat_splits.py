"""Repair mid-word entry splits in data/mufradat.json.

The source extraction sometimes cut an entry in the middle of a word: the tail
of the word was captured as a bogus "root" and the rest of the entry became a
new record. So an entry like كلم shows only "...فال" while its real body hides
under a spurious next root (كلا) starting mid-word ("م: مدرك ...").

Fix: walk entries in order; when the running (previous) entry ends abruptly
(short last token, no terminal punctuation) AND the next entry does NOT
introduce its own root early AND does NOT look like a fresh entry (Quranic
citation start), treat the next entry as a continuation: re-insert its bogus
root word at the seam (it holds the missing letters) and append its text.

Conservative guards keep real short entries (e.g. basmala starting with
"قال تعالى: {...}") from being swallowed.
"""
import json
import re
from pathlib import Path

SRC = Path("data/mufradat.json")
TASHKEEL = re.compile(r"[ً-ْٰـ]")
NORM = str.maketrans({"أ": "ا", "إ": "ا", "آ": "ا", "ٱ": "ا",
                      "ى": "ي", "ئ": "ي", "ؤ": "و", "ة": "ه"})


def norm(s):
    return re.sub(r"\s+", " ", TASHKEEL.sub("", s or "").translate(NORM)).strip()


def ends_abrupt(t):
    t = t.rstrip()
    if not t:
        return True
    if t[-1] in '.؟!»":})':
        return False
    toks = t.split()
    return bool(toks) and len(toks[-1]) <= 4


def introduces_root(e):
    return norm(e["root"]) in norm(e["text"])[:14]


# A fresh entry typically opens with a Quranic citation or a brace, never a
# mid-word continuation — never merge those.
FRESH_START = re.compile(r"^\s*(قال\b|\{|﴿)")


def is_continuation(prev, e):
    return (ends_abrupt(prev["text"])
            and not introduces_root(e)
            and not FRESH_START.match(e["text"]))


def repair(entries):
    out = []
    merged = 0
    for e in entries:
        if out and is_continuation(out[-1], e):
            prev = out[-1]
            # the bogus root holds the letters lost at the cut; re-insert it
            prev["text"] = (prev["text"].rstrip() + e["root"] + e["text"]).strip()
            merged += 1
        else:
            out.append(dict(e))
    return out, merged


def main():
    entries = json.loads(SRC.read_text(encoding="utf-8"))
    before = len(entries)
    out, merged = repair(entries)
    print(f"entries: {before} -> {len(out)}  (merged {merged} fragments)")
    SRC.write_text(json.dumps(out, ensure_ascii=False), encoding="utf-8")
    print("written.")


if __name__ == "__main__":
    main()
