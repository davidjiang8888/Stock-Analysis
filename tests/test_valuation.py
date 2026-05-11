import pytest

from src.valuation import DCFScenarioCase, DCFValuationAssumptions, build_default_valuation_scaffold, validate_dcf_assumptions


def test_validate_dcf_assumptions_rejects_invalid_terminal_growth():
    assumptions = DCFValuationAssumptions(
        base_year_free_cash_flow=100.0,
        shares_outstanding=10.0,
        net_debt=5.0,
        forecast_years=5,
        tax_rate=0.21,
        bear_case=DCFScenarioCase("bear", revenue_growth=0.02, operating_margin=0.10, terminal_growth=0.11, wacc=0.10),
        base_case=DCFScenarioCase("base", revenue_growth=0.05, operating_margin=0.15, terminal_growth=0.03, wacc=0.09),
        bull_case=DCFScenarioCase("bull", revenue_growth=0.08, operating_margin=0.20, terminal_growth=0.03, wacc=0.08),
    )

    with pytest.raises(ValueError):
        validate_dcf_assumptions(assumptions)


def test_build_default_valuation_scaffold_creates_bull_base_bear_and_sensitivity():
    scaffold = build_default_valuation_scaffold(
        ticker="NVDA",
        current_price=900.0,
        shares_outstanding=2_500_000_000,
        net_debt=-10_000_000_000,
        free_cash_flow=30_000_000_000,
        peer_tickers=["AMD", "AVGO"],
    )

    assert scaffold.ticker == "NVDA"
    assert scaffold.dcf.base_case.name == "base"
    assert scaffold.dcf.bull_case.name == "bull"
    assert scaffold.dcf.bear_case.name == "bear"
    assert scaffold.relative.peer_tickers == ["AMD", "AVGO"]
    assert len(scaffold.sensitivity_table) >= 4
