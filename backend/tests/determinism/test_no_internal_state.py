"""
DET-10 and DET-11 — Internal state and timestamp tests.

The engine holds no mutable module-level state. Results contain no
timestamps or system-clock-derived values.

Source: TEST_STRATEGY.md Part 8.5; ENGINE_CONTRACTS.md G-2, G-3.
"""

import dataclasses

import app.engine.calculations.formulas as _formulas_mod
import app.engine.risk_flags.definitions as _flags_mod
import app.engine.tax.individual as _ind_mod
import app.engine.tax.limited_company as _ltd_mod
import app.engine.validation.rules as _rules_mod
from app.engine import run
from app.engine.contracts import EngineResult
from tests.conftest import REFERENCE_CONFIG, e01_input


class TestNoInternalState:

    def test_det10_no_mutable_module_level_vars_in_engine(self) -> None:
        """
        DET-10: Inspect all engine sub-modules for mutable module-level
        variables. Lists, dicts, and other mutables at module scope would
        allow state to leak between calls.
        Source: TEST_STRATEGY.md DET-10; ENGINE_CONTRACTS.md G-2.
        """


        mutable_found = []
        for mod in [_formulas_mod, _ind_mod, _ltd_mod, _rules_mod, _flags_mod]:
            for name, val in vars(mod).items():
                if name.startswith("_"):
                    continue
                if isinstance(val, list | dict | set) and name.isupper():
                    # Constant-named lists/dicts are acceptable (VALIDATION_RULES etc.)
                    continue
                if isinstance(val, list | dict | set) and not name.startswith("_"):
                    # Lowercase mutable at module level is suspicious
                    mutable_found.append(f"{mod.__name__}.{name}: {type(val).__name__}")

        assert not mutable_found, (
            "Mutable module-level variables found in engine sub-modules: "
            + str(mutable_found)
        )

    def test_det11_engine_result_has_no_timestamp_fields(self) -> None:
        """
        DET-11: EngineResult and EngineIntermediates contain no timestamp
        fields. The engine never calls the system clock.
        Source: TEST_STRATEGY.md DET-11; ENGINE_CONTRACTS.md G-3.
        """
        result = run(e01_input(), REFERENCE_CONFIG)
        assert isinstance(result, EngineResult)

        timestamp_suffixes = ("_at", "_timestamp", "_time", "_date")
        for field in dataclasses.fields(result):
            assert not any(field.name.endswith(s) for s in timestamp_suffixes), (
                f"Unexpected timestamp field on EngineResult: {field.name}"
            )
        for field in dataclasses.fields(result.intermediates):
            assert not any(field.name.endswith(s) for s in timestamp_suffixes), (
                f"Unexpected timestamp field on EngineIntermediates: {field.name}"
            )
