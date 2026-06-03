"""
DET-01 through DET-04 — Idempotent execution tests.

The same inputs always produce the same result, regardless of how many
times the engine is called or in what order.

Source: TEST_STRATEGY.md Part 8.2; ENGINE_CONTRACTS.md G-1, G-2.
"""


from app.engine import run
from app.engine.contracts import EngineResult, ValidationResult
from tests.conftest import (
    REFERENCE_CONFIG,
    e01_input,
    e03_input,
    e07_input,
)


class TestIdempotentExecution:

    def test_det01_individual_pathway_identical(self) -> None:
        """
        DET-01: E-01 run twice produces identical EngineResults.
        Source: TEST_STRATEGY.md DET-01; ENGINE_CONTRACTS.md G-1.
        """
        result_1 = run(e01_input(), REFERENCE_CONFIG)
        result_2 = run(e01_input(), REFERENCE_CONFIG)
        assert isinstance(result_1, EngineResult)
        assert isinstance(result_2, EngineResult)
        assert result_1.outputs == result_2.outputs
        assert result_1.intermediates == result_2.intermediates
        flag_codes_1 = {f.code for f in result_1.risk_flags}
        flag_codes_2 = {f.code for f in result_2.risk_flags}
        assert flag_codes_1 == flag_codes_2

    def test_det02_ltd_co_pathway_identical(self) -> None:
        """
        DET-02: E-03 (LIMITED_COMPANY) run twice produces identical results.
        Source: TEST_STRATEGY.md DET-02; ENGINE_CONTRACTS.md G-1.
        """
        result_1 = run(e03_input(), REFERENCE_CONFIG)
        result_2 = run(e03_input(), REFERENCE_CONFIG)
        assert isinstance(result_1, EngineResult)
        assert isinstance(result_2, EngineResult)
        assert result_1.outputs == result_2.outputs
        assert result_1.intermediates == result_2.intermediates

    def test_det03_validation_failure_identical(self) -> None:
        """
        DET-03: E-07 (HARD failure) run twice returns identical
        ValidationResult.
        Source: TEST_STRATEGY.md DET-03; ENGINE_CONTRACTS.md G-1.
        """
        result_1 = run(e07_input(), REFERENCE_CONFIG)
        result_2 = run(e07_input(), REFERENCE_CONFIG)
        assert isinstance(result_1, ValidationResult)
        assert isinstance(result_2, ValidationResult)
        assert result_1.is_valid == result_2.is_valid
        codes_1 = {e.rule_code for e in result_1.hard_errors}
        codes_2 = {e.rule_code for e in result_2.hard_errors}
        assert codes_1 == codes_2

    def test_det04_ten_sequential_calls_identical(self) -> None:
        """
        DET-04: Ten sequential calls with E-01 inputs all produce
        identical outputs. Verifies no state accumulates between calls.
        Source: TEST_STRATEGY.md DET-04; ENGINE_CONTRACTS.md G-2.
        """
        results = [run(e01_input(), REFERENCE_CONFIG) for _ in range(10)]
        assert all(isinstance(r, EngineResult) for r in results)
        first = results[0]
        for i, r in enumerate(results[1:], 2):
            assert r.outputs == first.outputs, (
                f"Call {i} produced different outputs from call 1"
            )
            assert r.intermediates == first.intermediates, (
                f"Call {i} produced different intermediates from call 1"
            )
