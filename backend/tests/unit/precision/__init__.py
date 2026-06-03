"""
Engine package public interface.

The single public entry point is `run`. Callers import:
    from app.engine import run

Returns one of:
    EngineResult       — successful calculation
    ValidationResult   — HARD validation failure
    EngineError        — unexpected failure after validation
"""

from app.engine.orchestrator import run

__all__ = ["run"]
