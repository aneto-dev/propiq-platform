"""
Tests for F-13 — SDLT Calculation.

Progressive banded rate structure + flat additional dwelling surcharge.
All values verified against HMRC methodology and ENGINE_CONTRACTS.md.

SDLT Bands (England, 1 April 2025 — from REFERENCE_CONFIG):
  0 – 125,000:       0%
  125,001 – 250,000: 2%
  250,001 – 925,000: 5%
  925,001 – 1,500,000: 10%
  1,500,001+:        12%
Additional dwelling surcharge: 3%

Source: CALCULATION_SPEC.md F-13; TEST_STRATEGY.md Section 3.3 F-13.
"""

from decimal import ROUND_HALF_UP, Decimal

from app.engine.calculations.formulas import (
    SDLTResult,
    f13_sdlt,
)

TWO_DP = Decimal("0.01")


def r2(v: Decimal) -> Decimal:
    return v.quantize(TWO_DP, rounding=ROUND_HALF_UP)


# SDLT bands as plain (lower, upper|None, rate) tuples
# Rate is a decimal fraction. These mirror the v1.0 England config.
ENGLAND_BANDS: tuple[tuple[Decimal, Decimal | None, Decimal], ...] = (
    (Decimal("0"),       Decimal("125000"),  Decimal("0.00")),
    (Decimal("125000"),  Decimal("250000"),  Decimal("0.02")),
    (Decimal("250000"),  Decimal("925000"),  Decimal("0.05")),
    (Decimal("925000"),  Decimal("1500000"), Decimal("0.10")),
    (Decimal("1500000"), None,               Decimal("0.12")),
)
SURCHARGE_RATE = Decimal("0.03")


class TestF13SDLTBaseCalculation:
    """12 boundary value tests — no surcharge."""

    def test_100000_no_surcharge(self) -> None:
        """
        Price=100,000: entirely in 0% band → base=0.00.
        Manual: 100,000 × 0% = 0.00.
        """
        r = f13_sdlt(Decimal("100000"), ENGLAND_BANDS, SURCHARGE_RATE, False)
        assert r2(r.sdlt_base) == Decimal("0.00")
        assert r2(r.sdlt_surcharge) == Decimal("0.00")
        assert r2(r.total_sdlt) == Decimal("0.00")

    def test_125000_no_surcharge(self) -> None:
        """
        Price=125,000: upper limit of 0% band → base=0.00.
        Manual: 125,000 × 0% = 0.00. No tax at 2% band.
        Source: TEST_STRATEGY.md — boundary at 125,000.
        """
        r = f13_sdlt(Decimal("125000"), ENGLAND_BANDS, SURCHARGE_RATE, False)
        assert r2(r.sdlt_base) == Decimal("0.00")
        assert r2(r.total_sdlt) == Decimal("0.00")

    def test_125001_no_surcharge(self) -> None:
        """
        Price=125,001: first penny in 2% band.
        Manual: 0 + (1 × 0.02) = 0.02.
        Source: TEST_STRATEGY.md.
        """
        r = f13_sdlt(Decimal("125001"), ENGLAND_BANDS, SURCHARGE_RATE, False)
        assert r2(r.sdlt_base) == Decimal("0.02")

    def test_200000_no_surcharge(self) -> None:
        """
        Price=200,000 → base=1,500.00.
        Manual: 0 + (75,000 × 0.02) = 1,500.00.
        Source: TEST_STRATEGY.md.
        """
        r = f13_sdlt(Decimal("200000"), ENGLAND_BANDS, SURCHARGE_RATE, False)
        assert r2(r.sdlt_base) == Decimal("1500.00")
        assert r2(r.total_sdlt) == Decimal("1500.00")

    def test_250000_no_surcharge(self) -> None:
        """
        Price=250,000: upper limit of 2% band → base=2,500.00.
        Manual: 0 + (125,000 × 0.02) = 2,500.00.
        Source: TEST_STRATEGY.md.
        """
        r = f13_sdlt(Decimal("250000"), ENGLAND_BANDS, SURCHARGE_RATE, False)
        assert r2(r.sdlt_base) == Decimal("2500.00")

    def test_250001_no_surcharge(self) -> None:
        """
        Price=250,001: first penny in 5% band.
        Manual: 0 + 2,500 + (1 × 0.05) = 2,500.05.
        Source: TEST_STRATEGY.md.
        """
        r = f13_sdlt(Decimal("250001"), ENGLAND_BANDS, SURCHARGE_RATE, False)
        assert r2(r.sdlt_base) == Decimal("2500.05")

    def test_300000_no_surcharge(self) -> None:
        """
        Price=300,000 → base=5,000.00.
        Manual: 0 + 2,500 + (50,000 × 0.05) = 5,000.00.
        Source: TEST_STRATEGY.md.
        """
        r = f13_sdlt(Decimal("300000"), ENGLAND_BANDS, SURCHARGE_RATE, False)
        assert r2(r.sdlt_base) == Decimal("5000.00")

    def test_925000_no_surcharge(self) -> None:
        """
        Price=925,000: upper limit of 5% band → base=36,250.00.
        Manual: 0 + 2,500 + (675,000 × 0.05) = 36,250.00.
        Source: TEST_STRATEGY.md.
        """
        r = f13_sdlt(Decimal("925000"), ENGLAND_BANDS, SURCHARGE_RATE, False)
        assert r2(r.sdlt_base) == Decimal("36250.00")

    def test_925001_no_surcharge(self) -> None:
        """
        Price=925,001: first penny in 10% band.
        Manual: 0 + 2,500 + 33,750 + (1 × 0.10) = 36,250.10.
        Source: TEST_STRATEGY.md.
        """
        r = f13_sdlt(Decimal("925001"), ENGLAND_BANDS, SURCHARGE_RATE, False)
        assert r2(r.sdlt_base) == Decimal("36250.10")

    def test_1500000_no_surcharge(self) -> None:
        """
        Price=1,500,000: upper limit of 10% band → base=93,750.00.
        Manual: 0 + 2,500 + 33,750 + (575,000 × 0.10) = 93,750.00.
        Source: TEST_STRATEGY.md.
        """
        r = f13_sdlt(Decimal("1500000"), ENGLAND_BANDS, SURCHARGE_RATE, False)
        assert r2(r.sdlt_base) == Decimal("93750.00")

    def test_1500001_no_surcharge(self) -> None:
        """
        Price=1,500,001: first penny in 12% band.
        Manual: 0 + 2,500 + 33,750 + 57,500 + (1 × 0.12) = 93,750.12.
        Source: TEST_STRATEGY.md.
        """
        r = f13_sdlt(Decimal("1500001"), ENGLAND_BANDS, SURCHARGE_RATE, False)
        assert r2(r.sdlt_base) == Decimal("93750.12")

    def test_2000000_no_surcharge(self) -> None:
        """
        Price=2,000,000 → base=153,750.00.
        Manual: 0 + 2,500 + 33,750 + 57,500 + (500,000 × 0.12) = 153,750.00.
        Source: TEST_STRATEGY.md.
        """
        r = f13_sdlt(Decimal("2000000"), ENGLAND_BANDS, SURCHARGE_RATE, False)
        assert r2(r.sdlt_base) == Decimal("153750.00")


class TestF13SDLTWithSurcharge:
    """Key prices with additional dwelling surcharge applied."""

    def test_e01_with_surcharge(self) -> None:
        """
        E-01: price=200,000, additional=True → total=7,500.00.
        Manual: base=1,500 + surcharge=6,000 = 7,500.00.
        Source: ENGINE_CONTRACTS.md E-01.
        """
        r = f13_sdlt(Decimal("200000"), ENGLAND_BANDS, SURCHARGE_RATE, True)
        assert r2(r.sdlt_base)      == Decimal("1500.00")
        assert r2(r.sdlt_surcharge) == Decimal("6000.00")
        assert r2(r.total_sdlt)     == Decimal("7500.00")

    def test_e03_with_surcharge(self) -> None:
        """
        E-03: price=350,000, additional=True → total=18,000.00.
        Manual: base=7,500 + surcharge=10,500 = 18,000.00.
        Source: ENGINE_CONTRACTS.md E-03.
        """
        r = f13_sdlt(Decimal("350000"), ENGLAND_BANDS, SURCHARGE_RATE, True)
        assert r2(r.sdlt_base)      == Decimal("7500.00")
        assert r2(r.sdlt_surcharge) == Decimal("10500.00")
        assert r2(r.total_sdlt)     == Decimal("18000.00")

    def test_e05_with_surcharge(self) -> None:
        """
        E-05: price=600,000, additional=True → total=38,000.00.
        Manual: base=20,000 + surcharge=18,000 = 38,000.00.
        Source: ENGINE_CONTRACTS.md E-05.
        """
        r = f13_sdlt(Decimal("600000"), ENGLAND_BANDS, SURCHARGE_RATE, True)
        assert r2(r.sdlt_base)      == Decimal("20000.00")
        assert r2(r.sdlt_surcharge) == Decimal("18000.00")
        assert r2(r.total_sdlt)     == Decimal("38000.00")

    def test_200000_no_surcharge(self) -> None:
        """
        price=200,000, additional=False → total=1,500.00 (no surcharge).
        Source: TEST_STRATEGY.md.
        """
        r = f13_sdlt(Decimal("200000"), ENGLAND_BANDS, SURCHARGE_RATE, False)
        assert r2(r.sdlt_surcharge) == Decimal("0.00")
        assert r2(r.total_sdlt)     == Decimal("1500.00")


class TestF13SDLTBandBreakdown:
    """Band breakdown structure and integrity tests."""

    def test_band_breakdown_count_200000(self) -> None:
        """
        price=200,000: only two bands have taxable_in_band > 0.
        Band 0-125000 (0% — tax=0 but taxable=125000 — included).
        Band 125000-250000 (2% — taxable=75000).
        """
        r = f13_sdlt(Decimal("200000"), ENGLAND_BANDS, SURCHARGE_RATE, False)
        assert len(r.band_breakdown) == 2

    def test_band_breakdown_e01_values(self) -> None:
        """
        E-01 band breakdown verification:
        Band 0:      lower=0, upper=125000, rate=0%, taxable=125000, tax=0
        Band 1:      lower=125000, upper=250000, rate=2%, taxable=75000, tax=1500
        Source: ENGINE_CONTRACTS.md E-01.
        """
        r = f13_sdlt(Decimal("200000"), ENGLAND_BANDS, SURCHARGE_RATE, True)
        band0 = r.band_breakdown[0]
        band1 = r.band_breakdown[1]
        assert band0.taxable_in_band == Decimal("125000")
        assert band0.tax_in_band == Decimal("0")
        assert band1.taxable_in_band == Decimal("75000")
        assert r2(band1.tax_in_band) == Decimal("1500.00")

    def test_band_breakdown_sum_equals_base(self) -> None:
        """
        Sum of tax_in_band across all bands must equal sdlt_base.
        This is a structural integrity test — if this fails, the
        band calculation is inconsistent with the total.
        """
        for price in [
            Decimal("200000"), Decimal("350000"),
            Decimal("600000"), Decimal("925001"), Decimal("2000000"),
        ]:
            r = f13_sdlt(price, ENGLAND_BANDS, SURCHARGE_RATE, True)
            band_sum = sum(b.tax_in_band for b in r.band_breakdown)
            assert r2(band_sum) == r2(r.sdlt_base), (
                f"Band sum {r2(band_sum)} != sdlt_base {r2(r.sdlt_base)} "
                f"for price={price}"
            )

    def test_top_band_upper_is_none(self) -> None:
        """
        The top band (1,500,001+) has band_upper=None.
        """
        r = f13_sdlt(Decimal("2000000"), ENGLAND_BANDS, SURCHARGE_RATE, False)
        top_band = r.band_breakdown[-1]
        assert top_band.band_upper is None

    def test_sdlt_result_is_named_tuple(self) -> None:
        """SDLTResult is a NamedTuple — fields accessible by name."""
        r = f13_sdlt(Decimal("200000"), ENGLAND_BANDS, SURCHARGE_RATE, True)
        assert isinstance(r, SDLTResult)
        assert hasattr(r, "sdlt_base")
        assert hasattr(r, "sdlt_surcharge")
        assert hasattr(r, "total_sdlt")
        assert hasattr(r, "band_breakdown")

    def test_zero_purchase_price(self) -> None:
        """Zero purchase price → all zero, empty breakdown."""
        r = f13_sdlt(Decimal("0"), ENGLAND_BANDS, SURCHARGE_RATE, False)
        assert r2(r.sdlt_base) == Decimal("0.00")
        assert r2(r.total_sdlt) == Decimal("0.00")
        assert len(r.band_breakdown) == 0
