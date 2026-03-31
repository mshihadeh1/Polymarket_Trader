from __future__ import annotations


class RulesEngineService:
    def parse_resolution_text(self, text: str, source: str | None = None) -> dict[str, object]:
        return {
            "source": source,
            "text": text,
            "contains_threshold_rule": "above" in text.lower() or "below" in text.lower(),
            "todo": "Extend parser for weather and exact-source awareness in Phase 4.",
        }
