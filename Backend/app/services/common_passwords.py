"""The bundled list of common passwords (app/data/common_passwords.txt, SecLists 10k, MIT).
Read once, on first use; compared case-insensitively."""
from functools import lru_cache
from pathlib import Path

LIST_PATH = Path(__file__).resolve().parents[1] / "data" / "common_passwords.txt"


@lru_cache(maxsize=1)
def _common():
    lines = LIST_PATH.read_text(encoding="utf-8").splitlines()
    return frozenset(line.casefold() for line in lines if line and not line.startswith("# "))


def is_common(password: str) -> bool:
    return password.casefold() in _common()
