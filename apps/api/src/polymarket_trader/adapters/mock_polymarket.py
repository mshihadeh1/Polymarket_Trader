from __future__ import annotations

import json
from pathlib import Path
from typing import Any


class MockPolymarketAdapter:
    def __init__(self, seed_path: Path) -> None:
        self._seed_path = seed_path

    def load_seed_payload(self) -> dict[str, Any]:
        return json.loads(self._seed_path.read_text(encoding="utf-8"))
