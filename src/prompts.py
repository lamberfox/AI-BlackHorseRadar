import os
import re
from functools import lru_cache

_PROMPTS_FILE = os.path.join(os.path.dirname(__file__), "..", "顾问.md")


@lru_cache(maxsize=1)
def _load() -> dict[str, str]:
    with open(_PROMPTS_FILE, encoding="utf-8") as f:
        content = f.read()

    sections: dict[str, str] = {}
    parts = re.split(r"^## (.+)$", content, flags=re.MULTILINE)
    # parts = [preamble, key1, body1, key2, body2, ...]
    for i in range(1, len(parts) - 1, 2):
        key = parts[i].strip()
        body = parts[i + 1].strip()
        sections[key] = body
    return sections


def get(key: str) -> str:
    return _load()[key]
