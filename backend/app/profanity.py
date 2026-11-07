"""Profanity check for text pilots publish under the alliance's name.

The word list is better-profanity's (about 900 words and spellings). Its own
matcher misses common dodges (``f.u.c.k``, ``fuuuck``, ``b!tch``, ``dicks``,
``fuckwit``) and flags ordinary EVE words ("kill", "slave", "Snuffed"), so
the words are matched here instead:

* text is folded to plain lowercase letters: accents, look-alike letters,
  leetspeak and invisible characters are undone;
* each word is checked as written, with stretched letters squeezed, and
  without a plural or verb ending;
* runs of single letters (``f u c k``, ``f-u-c-k``) are joined up;
* the strongest words are also found inside longer words.

``ALLOWED`` keeps everyday and EVE words in the list (kill, slave, hell,
sniper, drug names) usable. Slurs and sexual words stay blocked.
"""

from __future__ import annotations

import re
import unicodedata
from functools import lru_cache

from better_profanity.utils import (
    get_complete_path_of_file,
    read_wordlist,
)

# Words in better-profanity's list that pilots legitimately write: EVE
# vocabulary, Minmatar lore, mild insults, drugs and names.
ALLOWED = frozenset(
    {
        # EVE and Minmatar
        "kill",
        "howtokill",
        "murder",
        "howtomurdep",
        "slave",
        "sniper",
        "napalm",
        "snuff",
        "uzi",
        "thrust",
        "penetrate",
        "penetration",
        "flange",
        "organ",
        "strip",
        "stroke",
        "snatch",
        "pawn",
        "screw",
        "screwed",
        "screwing",
        "revue",
        "sandbar",
        "seaman",
        "seamen",
        "virgin",
        "vixen",
        "god",
        "hell",
        "reich",
        "pinko",
        "slope",
        # Everyday words
        "fat",
        "drunk",
        "stupid",
        "dummy",
        "ugly",
        "jerk",
        "moron",
        "doofus",
        "nimrod",
        "dopey",
        "weirdo",
        "ninny",
        "prude",
        "prig",
        "trashy",
        "sleazy",
        "steamy",
        "racy",
        "tawdry",
        "vulgar",
        "lust",
        "lusting",
        "lusty",
        "naked",
        "suck",
        "sucked",
        "sucking",
        "tramp",
        "thug",
        "seduce",
        "scantily",
        "enlargement",
        "leper",
        "unwed",
        "playboy",
        "pasty",
        "pastie",
        "nappy",
        "rump",
        "loin",
        "loins",
        "toots",
        "souse",
        "soused",
        "maxi",
        "len",
        "omg",
        "lmao",
        "foobar",
        "vomit",
        "urine",
        "urinal",
        "womb",
        "pms",
        "xx",
        "knob",
        "gay",
        "gays",
        "queer",
        "queers",
        "lesbians",
        # Names
        "arian",
        "willy",
        "woody",
        "wang",
        "dong",
        "dink",
        "dinks",
        "pollock",
        "paddy",
        "guido",
        # Drugs and drink: not profanity
        "pot",
        "weed",
        "toke",
        "stoned",
        "reefer",
        "ganja",
        "hemp",
        "hooch",
        "hootch",
        "meth",
        "pcp",
        "heroin",
        "opium",
        "opiate",
        "peyote",
        "valium",
        "junkie",
        "junky",
        "rum",
        "vodka",
        "extacy",
        "extasy",
        "viagra",
        "hookah",
        # Words the substring check would otherwise catch
        "scunthorpe",
        "shiitake",
    }
)

# Spellings better-profanity's list doesn't have.
EXTRA = frozenset(
    {
        "fck",
        "fcking",
        "fckin",
        "fkn",
        "fking",
        "fuq",
        "fuqing",
        "fucc",
        "phuk",
        "sht",
        "shyt",
        "btch",
        "biatch",
        "beyotch",
        "cnt",
        "kunt",
        "nigguh",
        "niqqa",
        "niqqer",
        "fagg",
        "dik",
        "dck",
        "azz",
        "arsehat",
        "asshat",
        "jackass",
        "dumbass",
        "dipshit",
        "bullshit",
        "horseshit",
        "wanker",
        "wanking",
        "tosser",
        "bollocks",
        "bellend",
        "cocksucker",
        "motherfucking",
        "kys",
    }
)

# Found inside longer words too ("fuckwit", "clusterfuck", "bullshitting").
# "shit" is skipped before a, i, o, u so names like Yoshito still pass.
_EMBEDDED = re.compile(
    r"fuck|phuck|cunt|nigg|bitch|whore|faggot|slut|shit(?![aiou])"
)

# Letters folded to plain a-z before matching. Applied after NFKD, so
# accented letters are already split from their marks.
_LEET = str.maketrans(
    {
        "0": "o",
        "1": "i",
        "!": "i",
        "|": "i",
        "3": "e",
        "4": "a",
        "@": "a",
        "5": "s",
        "$": "s",
        "7": "t",
        "+": "t",
        "8": "b",
        "9": "g",
        "€": "e",
        "£": "l",
    }
)

_LOOKALIKES = str.maketrans(
    {
        # Cyrillic and Greek letters that look Latin
        "а": "a",
        "в": "b",
        "е": "e",
        "ё": "e",
        "к": "k",
        "м": "m",
        "н": "h",
        "о": "o",
        "р": "p",
        "с": "c",
        "т": "t",
        "у": "y",
        "х": "x",
        "і": "i",
        "ј": "j",
        "ѕ": "s",
        "ԁ": "d",
        "ս": "u",
        "α": "a",
        "β": "b",
        "ε": "e",
        "ι": "i",
        "κ": "k",
        "ν": "v",
        "ο": "o",
        "ρ": "p",
        "τ": "t",
        "υ": "u",
        "χ": "x",
    }
)

_WORD = re.compile(r"[a-z]+")
_RUNS_OF_THREE = re.compile(r"(.)\1{2,}")
_RUNS_OF_TWO = re.compile(r"(.)\1+")
_ENDINGS = ("ings", "ing", "ers", "er", "ed", "es", "s", "y", "in", "z")


def _fold(text: str, leet: bool) -> str:
    """Lowercase plain letters; everything else becomes a space. With
    `leet`, digits and symbols that stand in for letters become them."""
    text = unicodedata.normalize("NFKD", text or "")
    kept = []
    for char in text:
        category = unicodedata.category(char)
        # Accents, and zero-width or formatting characters used to split a
        # word without showing a gap.
        if category in ("Mn", "Me", "Cf"):
            continue
        kept.append(char)
    folded = "".join(kept).lower().translate(_LOOKALIKES)
    if leet:
        folded = folded.translate(_LEET)
    return re.sub(r"[^a-z]+", " ", folded)


@lru_cache(maxsize=1)
def _lists() -> tuple[frozenset[str], tuple[str, ...]]:
    """Single words, and phrases as padded strings (" blow job ")."""
    words = set(EXTRA)
    phrases = []
    for entry in read_wordlist(
        get_complete_path_of_file("profanity_wordlist.txt")
    ):
        tokens = _WORD.findall(_fold(entry, leet=True))
        if not tokens:
            continue
        if len(tokens) == 1:
            words.add(tokens[0])
        elif all(len(token) == 1 for token in tokens):
            # "f.u.c.k" and "s-h-i-t": the letter joining below finds these.
            words.add("".join(tokens))
        else:
            phrases.append(f" {' '.join(tokens)} ")
    words -= ALLOWED
    return frozenset(words), tuple(phrases)


def _variants(word: str):
    """The word as written, with stretched letters squeezed, and each of
    those without an ending. Stems shorter than four letters are skipped,
    so "bass" and "assess" never become "ass".

    Ordered most specific first, so "fucking" reports "fucking" rather
    than "fuck" (a set made the answer depend on the hash seed)."""
    forms = dict.fromkeys(
        (
            word,
            _RUNS_OF_THREE.sub(r"\1\1", word),
            _RUNS_OF_TWO.sub(r"\1", word),
        )
    )
    for form in list(forms):
        for ending in _ENDINGS:
            if not form.endswith(ending) or len(form) - len(ending) < 4:
                continue
            # "assess" and "class" end in s without being plurals.
            if ending == "s" and form.endswith("ss"):
                continue
            forms.setdefault(form[: -len(ending)])
    return list(forms)


def _word_hit(word: str, words: frozenset[str]) -> str | None:
    if word in ALLOWED:
        return None
    for form in _variants(word):
        if form in ALLOWED:
            return None
        if form in words:
            return form
    for form in (word, _RUNS_OF_TWO.sub(r"\1", word)):
        match = _EMBEDDED.search(form)
        if match:
            return match.group(0)
    return None


def _candidates(tokens: list[str]):
    """Each word, plus runs of single letters joined ("f u c k")."""
    yield from tokens
    run: list[str] = []
    for token in [*tokens, ""]:
        if len(token) == 1:
            run.append(token)
            continue
        if len(run) >= 3:
            yield "".join(run)
        run = []


def find_profanity(text: str) -> list[str]:
    """The profane words in `text`, folded to plain spelling, in the order
    they appear. Empty when the text is clean."""
    words, phrases = _lists()
    found: list[str] = []
    # Read both ways: "b!tch" needs the leet reading, while "us!" must not
    # become "usi" and hide the word before it.
    for leet in (False, True):
        tokens = _fold(text, leet).split()
        for candidate in _candidates(tokens):
            hit = _word_hit(candidate, words)
            if hit and hit not in found:
                found.append(hit)
        padded = f" {' '.join(tokens)} "
        for phrase in phrases:
            if phrase in padded and phrase.strip() not in found:
                found.append(phrase.strip())
    return found


def contains_profanity(text: str) -> bool:
    return bool(find_profanity(text))
