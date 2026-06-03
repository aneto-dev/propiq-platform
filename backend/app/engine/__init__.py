"""
Engine package.

The single public entry point is engine.run(), added in Commit 2.8.
All other submodules are implementation details.

Architecture:
    ENGINE_ARCHITECTURE.md Part 1 — the engine is a pure function.
    Nothing in this package imports from app.db, app.api, or any
    application infrastructure.
"""

from .orchestrator import run

__all__ = ["run"]
