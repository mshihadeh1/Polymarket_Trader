from __future__ import annotations


class ExecutionEngineService:
    def status(self) -> dict[str, object]:
        return {
            "enabled": False,
            "dry_run_default": True,
            "message": "Live routing is disabled by default and not implemented in Phase 1.",
        }
