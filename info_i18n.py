# -*- coding: utf-8 -*-
"""The Info page, in every language the site speaks.

i18n.py holds the short labels and is shared with the Discord bot, so it is
deliberately left alone by this. This is the other half - the explanatory
prose, which used to stay English in every language because there was one
copy of it to keep true. The user asked on 14 Aug for it to follow the
language picker as well, so each language gets its own module,
info_text_<code>.py, holding TITLE, SUB, CARDS and FOOT.

CARDS is a list of (heading, body). The body is HTML and is rendered with
|safe, so it is written by us and never by a player. Three tokens are
filled in at render time, so no number or handle is written down twice:

    [[ELO]]      the starting rating
    [[K]]        the most one match can move you
    [[MINSCORE]] the minimum score to be rated at all
    [[CONTACT]]  the Discord handle to ask
    [[RANKS]]    the rank ladder, built from ranks.py (raw HTML, ours)

A language file may also set STALE = (2, 7) - the indexes of its own cards
that are known to be out of date. Those fall back to the English card, the
same way a missing card already does. Better a player reads the rule in
English than reads a rule that is no longer true in their own language.

A language whose module is missing or broken falls back to English, one
card at a time - a translation that gets out of step shows English text
rather than an empty page or a 500.
"""
import importlib

from markupsafe import escape

import ranks

TOKENS = (("[[ELO]]", "elo"), ("[[K]]", "k"), ("[[MINSCORE]]", "minscore"),
          ("[[CONTACT]]", "contact"))

_CACHE = {}


def _module(lang):
    """The text module for this language, or the English one."""
    if lang in _CACHE:
        return _CACHE[lang]
    mod = None
    if lang and lang.isalpha() and len(lang) <= 5:
        try:
            mod = importlib.import_module("info_text_" + lang)
        except Exception:
            mod = None
    if mod is None:
        mod = importlib.import_module("info_text_en")
    _CACHE[lang] = mod
    return mod


def _fill(text, values):
    """Put the numbers and the handle in. Escaped: they land inside HTML."""
    for token, key in TOKENS:
        if token in text:
            text = text.replace(token, str(escape(values.get(key, ""))))
    # Ours, not a player's - and it is a table, so it must not be escaped.
    if "[[RANKS]]" in text:
        text = text.replace("[[RANKS]]", ranks.info_table_html())
    return text


def page(lang, **values):
    """Everything the Info template needs, in one dict."""
    mod = _module(lang)
    en = _module("en")
    cards = getattr(mod, "CARDS", None) or en.CARDS
    # A short translation is not a reason to lose the rest of the page.
    if len(cards) < len(en.CARDS):
        cards = list(cards) + list(en.CARDS[len(cards):])
    # ...and a card the translation has outlived shows in English instead.
    stale = getattr(mod, "STALE", ()) if mod is not en else ()
    if stale:
        cards = list(cards)
        for i in stale:
            if 0 <= i < len(en.CARDS):
                cards[i] = en.CARDS[i]
    return {
        "title": _fill(getattr(mod, "TITLE", None) or en.TITLE, values),
        "sub": _fill(getattr(mod, "SUB", None) or en.SUB, values),
        "foot": _fill(getattr(mod, "FOOT", None) or en.FOOT, values),
        "search": getattr(mod, "SEARCH", None) or en.SEARCH,
        "nomatch": getattr(mod, "NOMATCH", None) or en.NOMATCH,
        "cards": [(_fill(h, values), _fill(b, values)) for h, b in cards],
    }
