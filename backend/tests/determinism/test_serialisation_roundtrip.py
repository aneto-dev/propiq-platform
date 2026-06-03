"""
DET-05 and DET-06 — Serialisation round-trip tests.

Engine results are fully determined by the explicit data passed in.
No hidden dependency on object identity or memory address.

Source: TEST_STRATEGY.md Part 8.3; ENGINE_CONTRACTS.md G-4, G-8.
"""

import dataclasses
import json
from decimal import Decimal

from app.domain.enums import (
    IncomeTaxBand,
    MortgageType,
    OwnershipStructure,
    PropertyCountry,
    PropertyType,
    Tenure,
)
from app.engine import run
from app.engine.contracts import (
    EngineInput,
    EngineResult,
)
from tests.conftest import REFERENCE_CONFIG, e01_input


def _serialise_input(inp: EngineInput) -> str:
    """Canonical JSON: Decimal as string, enums as string, sorted keys."""
    d = {}
    for field in dataclasses.fields(inp):
        val = getattr(inp, field.name)
        if isinstance(val, Decimal):
            d[field.name] = str(val)
        elif hasattr(val, "value"):  # enum
            d[field.name] = val.value if val is not None else None
        else:
            d[field.name] = val
    return json.dumps(d, sort_keys=True)


def _deserialise_input(s: str) -> EngineInput:
    """Reconstruct EngineInput from canonical JSON."""
    d = json.loads(s)
    enum_map = {
        "mortgage_type": MortgageType,
        "ownership_structure": OwnershipStructure,
        "income_tax_band": IncomeTaxBand,
        "property_type": PropertyType,
        "tenure": Tenure,
        "property_country": PropertyCountry,
    }
    decimal_fields = {
        f.name for f in dataclasses.fields(EngineInput)
        if f.type in ("Decimal", "Optional[Decimal]")
        or "Decimal" in str(f.type)
    }
    kwargs: dict = {}
    for field in dataclasses.fields(EngineInput):
        val = d[field.name]
        if val is None:
            kwargs[field.name] = None
        elif field.name in enum_map:
            kwargs[field.name] = enum_map[field.name](val)
        elif field.name in decimal_fields or isinstance(val, str):
            try:
                kwargs[field.name] = Decimal(val)
            except Exception:
                kwargs[field.name] = val
        else:
            kwargs[field.name] = val
    return EngineInput(**kwargs)


class TestSerialisationRoundtrip:

    def test_det05_input_serialisation_roundtrip(self) -> None:
        """
        DET-05: Serialise E-01 EngineInput to JSON and back. Run engine
        with both. Assert identical outputs.
        Source: TEST_STRATEGY.md DET-05; ENGINE_CONTRACTS.md G-8.
        """
        original_input = e01_input()
        json_str = _serialise_input(original_input)
        roundtrip_input = _deserialise_input(json_str)

        result_1 = run(original_input, REFERENCE_CONFIG)
        result_2 = run(roundtrip_input, REFERENCE_CONFIG)

        assert isinstance(result_1, EngineResult)
        assert isinstance(result_2, EngineResult)
        assert result_1.outputs == result_2.outputs
        assert result_1.intermediates == result_2.intermediates

    def test_det06_config_object_identity_irrelevant(self) -> None:
        """
        DET-06: Two independently constructed REFERENCE_CONFIG objects
        with identical values produce identical results.
        Engine must not depend on object identity.
        Source: TEST_STRATEGY.md DET-06; ENGINE_CONTRACTS.md G-8.
        """
        config_a = REFERENCE_CONFIG
        config_b = dataclasses.replace(
            REFERENCE_CONFIG,
            assumption_config=dataclasses.replace(
                REFERENCE_CONFIG.assumption_config
            ),
        )
        result_a = run(e01_input(), config_a)
        result_b = run(e01_input(), config_b)
        assert isinstance(result_a, EngineResult)
        assert isinstance(result_b, EngineResult)
        assert result_a.outputs == result_b.outputs
        assert result_a.intermediates == result_b.intermediates
