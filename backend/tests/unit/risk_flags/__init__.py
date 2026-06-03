"""
Engine risk flags subpackage.

Public entry point: evaluate_flags(context) → list[RiskFlag]

Architecture: ENGINE_ARCHITECTURE.md — Risk flag evaluation structure.
CALCULATION_SPEC.md — Risk Flag Definitions (16 flags).
"""

from app.engine.risk_flags.definitions import EvaluationContext, evaluate_flags

__all__ = ["EvaluationContext", "evaluate_flags"]
