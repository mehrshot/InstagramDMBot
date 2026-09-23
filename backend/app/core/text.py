"""Persian-aware text normalization, used for product matching and number parsing."""

import re

_DIGITS = str.maketrans("۰۱۲۳۴۵۶۷۸۹٠١٢٣٤٥٦٧٨٩", "01234567890123456789")
_LETTERS = str.maketrans({"ي": "ی", "ى": "ی", "ك": "ک", "ۀ": "ه", "ة": "ه", "أ": "ا", "إ": "ا"})
# Arabic diacritics, tatweel, and invisible joiners.
_STRIP = re.compile(r"[ً-ٰٟـ‌‍‎‏]")
_SPACES = re.compile(r"\s+")


def to_ascii_digits(text: str) -> str:
    return text.translate(_DIGITS)


def normalize(text: str) -> str:
    """Canonical form for comparisons: unified letters, ASCII digits, lowercase, one space."""
    text = to_ascii_digits(text).translate(_LETTERS)
    text = _STRIP.sub(" ", text)  # a ZWNJ separates words ("می‌خوام") so it becomes a space
    return _SPACES.sub(" ", text).strip().lower()


def parse_int(value: object) -> int | None:
    """Parse "1,250,000 تومان", "۱۲۵۰۰۰۰", 3.0 or "12" into an int; None if there are no digits."""
    if value is None or isinstance(value, bool):
        return None
    if isinstance(value, int | float):
        return int(value)
    digits = re.sub(r"[^\d.]", "", to_ascii_digits(str(value)).replace("٬", "").replace(",", ""))
    if not digits or digits == ".":
        return None
    try:
        return int(float(digits))
    except ValueError:
        return None
