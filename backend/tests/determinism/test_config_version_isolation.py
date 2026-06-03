"""
DET-07 through DET-09 — Configuration version isolation tests.

Different configurations produce different results for the same inputs.
The original configuration always reproduces the original result.

Source: TEST_STRATEGY.md Part 8.4; ENGINE_CONTRACTS.md G-8.
"""


from app.engine import run
from app.engine.contracts import EngineResult
from tests.conftest import (
    ALTERNATIVE_CONFIG_STRESS,
    REFERENCE_CONFIG,
    e01_input,
)


class TestConfigVersionIsolation:

    def test_det07_different_stress_config_different_result(self) -> None:
        """
        DET-07: ALTERNATIVE_CONFIG_STRESS (stress=7.00%) produces different
        icr_percent than REFERENCE_CONFIG (stress=5.50%).

        ALTERNATIVE_CONFIG_VOID was originally used here but void_rate_percent
        is an EngineInput field (already resolved before engine entry). The
        AssumptionConfig.void_rate_percent_default is a service-layer default —
        the engine never reads it. ALTERNATIVE_CONFIG_STRESS correctly affects
        engine output because stress_test_rate_percent IS read from EngineConfig
        at execution time.

        Source: TEST_STRATEGY.md DET-07; ENGINE_CONTRACTS.md G-8.
        """
        result_ref = run(e01_input(), REFERENCE_CONFIG)
        result_stressed = run(e01_input(), ALTERNATIVE_CONFIG_STRESS)
        assert isinstance(result_ref, EngineResult)
        assert isinstance(result_stressed, EngineResult)
        assert result_ref.outputs.icr_percent != result_stressed.outputs.icr_percent
        assert (
            result_ref.intermediates.stress_test_rate_applied_percent
            != result_stressed.intermediates.stress_test_rate_applied_percent
        )

    def test_det08_original_config_reproduces_original_result(self) -> None:
        """
        DET-08: Run with REFERENCE_CONFIG, then with ALTERNATIVE_CONFIG_STRESS,
        then with REFERENCE_CONFIG again. Result must equal the first.
        Core historical reproducibility guarantee.
        Source: TEST_STRATEGY.md DET-08; ENGINE_CONTRACTS.md G-1, G-8.
        """
        result_original = run(e01_input(), REFERENCE_CONFIG)
        run(e01_input(), ALTERNATIVE_CONFIG_STRESS)  # discard
        result_reproduced = run(e01_input(), REFERENCE_CONFIG)

        assert isinstance(result_original, EngineResult)
        assert isinstance(result_reproduced, EngineResult)
        assert result_original.outputs == result_reproduced.outputs
        assert result_original.intermediates == result_reproduced.intermediates

    def test_det09_higher_stress_rate_produces_lower_icr(self) -> None:
        """
        DET-09: ALTERNATIVE_CONFIG_STRESS (stress=7.00%) produces lower
        ICR than REFERENCE_CONFIG (stress=5.50%). Higher stress rate
        means higher stressed interest → lower ICR for the same deal.
        Source: TEST_STRATEGY.md DET-09; ENGINE_CONTRACTS.md G-8.
        """
        result_standard = run(e01_input(), REFERENCE_CONFIG)
        result_stressed = run(e01_input(), ALTERNATIVE_CONFIG_STRESS)
        assert isinstance(result_standard, EngineResult)
        assert isinstance(result_stressed, EngineResult)
        assert result_standard.outputs.icr_percent is not None
        assert result_stressed.outputs.icr_percent is not None
        assert result_standard.outputs.icr_percent > result_stressed.outputs.icr_percent
