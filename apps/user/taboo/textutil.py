# Turkish-aware uppercasing + sanitising of agent/cache text down to the glyphs
# the 5x7 badge font can actually draw.
#
# MicroPython's str.upper() only handles ASCII (and gets Turkish 'i' wrong
# anyway), so we map char-by-char: i -> İ, ı -> I, plus the other five Turkish
# letters, plus a fallback for stray Latin accents (the agent occasionally emits
# things like "Béamél"). Anything still outside the font is dropped.

from font import FONT

# lowercase/accented -> uppercase (Turkish rules + accent fallbacks to base)
_UP = {
    "i": "İ", "ı": "I", "ş": "Ş", "ğ": "Ğ", "ç": "Ç", "ö": "Ö", "ü": "Ü",
    "İ": "İ", "I": "I", "Ş": "Ş", "Ğ": "Ğ", "Ç": "Ç", "Ö": "Ö", "Ü": "Ü",
    # circumflex / accented Latin -> closest renderable base letter
    "â": "A", "ä": "A", "á": "A", "à": "A", "ã": "A",
    "Â": "A", "Ä": "A", "Á": "A", "À": "A", "Ã": "A",
    "é": "E", "è": "E", "ê": "E", "ë": "E",
    "É": "E", "È": "E", "Ê": "E", "Ë": "E",
    "î": "İ", "ì": "İ", "í": "İ", "ï": "İ",
    "Î": "İ", "Ì": "İ", "Í": "İ", "Ï": "İ",
    "ô": "O", "ò": "O", "ó": "O", "õ": "O",
    "Ô": "O", "Ò": "O", "Ó": "O", "Õ": "O",
    "û": "U", "ù": "U", "ú": "U",
    "Û": "U", "Ù": "U", "Ú": "U",
    "ñ": "N", "Ñ": "N", "ý": "Y", "Ý": "Y",
    # typographic punctuation the LLM emits -> ASCII equivalents the font has.
    # The agent overwhelmingly uses U+2019 for the Turkish suffix apostrophe
    # ("İstanbul'un"); without this it would be dropped and the word run together.
    "’": "'", "‘": "'",          # right/left single quote -> '
    "–": "-", "—": "-",          # en/em dash -> -
}


def tr_upper(s):
    out = []
    for ch in s:
        m = _UP.get(ch)
        if m is not None:
            out.append(m)
        elif "a" <= ch <= "z":
            out.append(chr(ord(ch) - 32))
        else:
            out.append(ch)
    return "".join(out)


def to_card_text(s):
    """Uppercase (Turkish) and strip anything the font can't render."""
    out = []
    for ch in tr_upper(s):
        if ch in FONT:
            out.append(ch)
        elif ch == "_":
            out.append(" ")
    text = "".join(out)
    # collapse runs of spaces and trim
    while "  " in text:
        text = text.replace("  ", " ")
    return text.strip()
