"""
Engine version constant.

The single source of truth for the current engine version string.

Every calculation snapshot stores this value at calculation time.
If the formula logic changes in a way that produces different outputs
for the same inputs, this constant must be incremented following semver
and a new EngineVersionRecord inserted in the configuration tables.

Architecture: ENGINE_CONTRACTS.md Part 7.3 — version traceability.
"""

ENGINE_VERSION: str = "1.0.0"
