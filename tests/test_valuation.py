import json
from pathlib import Path

import pytest

from src.providers.local_market_data import LocalCSVMarketDataProvider
from src.valuation import (
    DCFAssumptions,
    ValuationInput,
    build_default_scenarios,
    build_sensitivity_table,
    build_valuation_result,
    calculate_dcf,
    calculate_relative_valuation,
    validate_dcf_assumptions,
)

RICH_FIXTURE_DIR = Path(__file__).parent / "fixtures" / "rich_local_data"


def _copy_rich_fixture(tmp_path: Path) -> Path:
    data_dir = tmp_path / "data"
    data_dir.mkdir()
    for path in RICH_FIXTURE_DIR.glob("*.csv"):
        (data_dir / path.name).write_text(path.read_text(encoding="utf-8"), encoding="utf-8")
    return tmp_path


def test_calculate_dcf_with_direct_fcf_and_shares():
    valuation_input = ValuationInput(
        ticker="AAPL",
        current_price=100.0,
        free_cash_flow=100.0,
        shares_outstanding=10.0,
        net_debt=0.0,
    )
    assumptions = build_default_scenarios(valuation_input)["base"]

    result = calculate_dcf(valuation_input, assumptions)

    assert result.status == "calculated"
    assert result.enterprise_value is not None
    assert result.equity_value is not None
    assert result.fair_value_per_share is not None
    assert len(result.assumptions["applied_growth_by_year"]) == assumptions.forecast_years


def test_calculate_dcf_with_revenue_and_fcf_margin():
    valuation_input = ValuationInput(
        ticker="MSFT",
        current_price=100.0,
        revenue=1000.0,
        fcf_margin=0.20,
        revenue_growth=0.10,
        shares_outstanding=20.0,
        cash=100.0,
        debt=50.0,
    )
    assumptions = build_default_scenarios(valuation_input)["base"]

    result = calculate_dcf(valuation_input, assumptions)

    assert result.status == "calculated"
    assert result.projected_fcfs
    assert result.fair_value_per_share is not None


def test_high_growth_input_gets_normalized_and_warned():
    valuation_input = ValuationInput(
        ticker="NVDA",
        revenue=215_938_000_000.0,
        revenue_growth=0.6547,
        free_cash_flow=96_676_000_000.0,
        fcf_margin=0.4477,
        shares_outstanding=24_300_000_000.0,
        cash=10_605_000_000.0,
        debt=8_468_000_000.0,
    )
    assumptions = build_default_scenarios(valuation_input)["base"]

    result = calculate_dcf(valuation_input, assumptions)

    assert result.status == "calculated"
    assert result.assumptions["observed_revenue_growth"] == pytest.approx(0.6547)
    assert result.assumptions["growth_was_capped"] is True
    assert result.assumptions["revenue_growth"] == pytest.approx(0.40)
    assert result.assumptions["normalized_growth_target"] == pytest.approx(0.08)
    assert len(result.assumptions["applied_growth_by_year"]) == 5
    assert result.assumptions["applied_growth_by_year"][0] > result.assumptions["applied_growth_by_year"][-1]
    assert any("start-growth cap" in warning for warning in result.warnings)


def test_normal_growth_input_is_not_unnecessarily_capped():
    valuation_input = ValuationInput(
        ticker="MSFT",
        revenue=1000.0,
        revenue_growth=0.10,
        free_cash_flow=120.0,
        shares_outstanding=20.0,
        cash=100.0,
        debt=50.0,
    )
    assumptions = build_default_scenarios(valuation_input)["base"]

    result = calculate_dcf(valuation_input, assumptions)

    assert result.status == "calculated"
    assert result.assumptions["growth_was_capped"] is False
    assert result.assumptions["observed_revenue_growth"] == pytest.approx(0.10)
    assert result.assumptions["revenue_growth"] == pytest.approx(0.10)
    assert not any("start-growth cap" in warning for warning in result.warnings)


def test_calculate_dcf_returns_insufficient_data_when_fcf_and_revenue_are_missing():
    valuation_input = ValuationInput(ticker="NVDA")
    assumptions = build_default_scenarios(valuation_input)["base"]

    result = calculate_dcf(valuation_input, assumptions)

    assert result.status == "insufficient_data"
    assert "free_cash_flow" in result.missing_fields
    assert "revenue" in result.missing_fields


def test_calculate_dcf_skips_per_share_value_when_shares_missing():
    valuation_input = ValuationInput(
        ticker="META",
        free_cash_flow=100.0,
        net_debt=0.0,
    )
    assumptions = build_default_scenarios(valuation_input)["base"]

    result = calculate_dcf(valuation_input, assumptions)

    assert result.status == "calculated"
    assert result.equity_value is not None
    assert result.fair_value_per_share is None
    assert "shares outstanding is unavailable" in " ".join(result.warnings).lower()


def test_validate_dcf_assumptions_flags_terminal_growth_and_wacc_errors():
    assumptions = DCFAssumptions(
        method_name="fcf_direct",
        revenue_growth=0.05,
        fcf_margin=None,
        operating_margin=None,
        tax_rate=0.21,
        wacc=0.03,
        terminal_growth=0.03,
        forecast_years=5,
    )

    warnings = validate_dcf_assumptions(assumptions)

    assert any("below WACC" in warning for warning in warnings)


def test_valuation_result_is_json_serializable():
    valuation_input = ValuationInput(
        ticker="AAPL",
        current_price=100.0,
        free_cash_flow=100.0,
        shares_outstanding=10.0,
        net_debt=0.0,
    )

    result = build_valuation_result(valuation_input)
    payload = json.dumps(result.to_dict())

    assert "dcf_result" in payload
    assert "applied_growth_by_year" in payload


def test_bull_base_bear_scenarios_return_structured_results():
    valuation_input = ValuationInput(
        ticker="AAPL",
        revenue=1000.0,
        fcf_margin=0.20,
        shares_outstanding=10.0,
        cash=0.0,
        debt=0.0,
    )

    result = build_valuation_result(valuation_input)

    assert [scenario.name for scenario in result.scenarios] == ["bear", "base", "bull"]
    assert all(scenario.dcf_result.status in {"calculated", "insufficient_data"} for scenario in result.scenarios)
    assert all("applied_growth_by_year" in scenario.dcf_result.assumptions for scenario in result.scenarios)


def test_bull_base_bear_scenarios_all_use_fade_logic_for_high_growth_input():
    valuation_input = ValuationInput(
        ticker="NVDA",
        revenue=215_938_000_000.0,
        revenue_growth=0.6547,
        free_cash_flow=96_676_000_000.0,
        fcf_margin=0.4477,
        shares_outstanding=24_300_000_000.0,
        cash=10_605_000_000.0,
        debt=8_468_000_000.0,
    )

    result = build_valuation_result(valuation_input)

    for scenario in result.scenarios:
        path = scenario.dcf_result.assumptions["applied_growth_by_year"]
        assert path
        assert path[0] >= path[-1]
        assert scenario.dcf_result.assumptions["observed_revenue_growth"] is not None
    assert result.scenarios[1].dcf_result.assumptions["normalized_growth_target"] == pytest.approx(0.08)


def test_sensitivity_table_has_expected_shape_when_base_dcf_is_calculable():
    valuation_input = ValuationInput(
        ticker="AAPL",
        free_cash_flow=100.0,
        shares_outstanding=10.0,
        net_debt=0.0,
    )
    assumptions = build_default_scenarios(valuation_input)["base"]

    sensitivity = build_sensitivity_table(valuation_input, assumptions, wacc_values=[0.08, 0.09], terminal_growth_values=[0.02, 0.03])

    assert sensitivity.status == "calculated"
    assert len(sensitivity.fair_value_grid) == 2
    assert len(sensitivity.fair_value_grid[0]) == 2


def test_sensitivity_table_returns_insufficient_data_when_base_dcf_lacks_per_share_inputs():
    valuation_input = ValuationInput(
        ticker="AAPL",
        free_cash_flow=100.0,
        net_debt=0.0,
    )
    assumptions = build_default_scenarios(valuation_input)["base"]

    sensitivity = build_sensitivity_table(valuation_input, assumptions)

    assert sensitivity.status == "insufficient_data"


def test_relative_valuation_calculates_pe_ps_and_p_fcf_when_inputs_exist():
    valuation_input = ValuationInput(
        ticker="AAPL",
        current_price=100.0,
        eps=5.0,
        revenue=1000.0,
        free_cash_flow=100.0,
        shares_outstanding=10.0,
    )

    result = calculate_relative_valuation(valuation_input)

    assert result.available_multiples["pe"] == 20.0
    assert result.available_multiples["ps"] == 1.0
    assert result.available_multiples["p_fcf"] == 10.0
    assert result.status == "peer_data_unavailable"
    assert result.peer_relative_status == "insufficient_peer_data"


def test_relative_valuation_returns_peer_data_unavailable_with_reported_multiple_only():
    valuation_input = ValuationInput(
        ticker="NVDA",
        trailing_pe=34.0,
    )

    result = calculate_relative_valuation(valuation_input)

    assert result.status == "peer_data_unavailable"
    assert result.available_multiples["trailing_pe_reported"] == 34.0
    assert result.relative_opportunity_score is None


def test_local_rich_fixture_produces_calculated_dcf(tmp_path: Path):
    provider = LocalCSVMarketDataProvider(base_dir=_copy_rich_fixture(tmp_path))
    quote = provider.get_quote("ALFA")
    financials = provider.get_financials("ALFA")

    result = build_valuation_result(
        ValuationInput(
            ticker="ALFA",
            current_price=quote.price,
            revenue=financials.revenue,
            revenue_growth=financials.revenue_growth,
            free_cash_flow=financials.free_cash_flow,
            fcf_margin=financials.fcf_margin,
            operating_margin=financials.operating_margin,
            eps=financials.eps,
            ebitda=financials.ebitda,
            shares_outstanding=financials.shares_outstanding,
            cash=financials.cash,
            debt=financials.debt,
            market_cap=financials.market_cap,
            trailing_pe=financials.trailing_pe,
            peer_inputs=provider.get_peer_valuation_inputs("ALFA"),
        )
    )

    assert result.dcf_result.status == "calculated"
    assert result.dcf_result.fair_value_per_share is not None


def test_local_bundled_data_reflects_available_coverage():
    provider = LocalCSVMarketDataProvider()
    quote = provider.get_quote("NVDA")
    financials = provider.get_financials("NVDA")

    result = build_valuation_result(
        ValuationInput(
            ticker="NVDA",
            current_price=quote.price,
            revenue=financials.revenue,
            revenue_growth=financials.revenue_growth,
            free_cash_flow=financials.free_cash_flow,
            fcf_margin=financials.fcf_margin,
            operating_margin=financials.operating_margin,
            eps=financials.eps,
            ebitda=financials.ebitda,
            shares_outstanding=financials.shares_outstanding,
            cash=financials.cash,
            debt=financials.debt,
            market_cap=financials.market_cap,
            trailing_pe=financials.trailing_pe,
        )
    )

    if financials.revenue is not None and financials.free_cash_flow is not None and financials.shares_outstanding is not None:
        assert result.dcf_result.status == "calculated"
        assert result.dcf_result.assumptions["applied_growth_by_year"]
    else:
        assert result.coverage in {"partial", "insufficient"}
        assert result.dcf_result.status == "insufficient_data"


def test_relative_valuation_uses_peer_medians_when_local_peer_data_exists(tmp_path: Path):
    provider = LocalCSVMarketDataProvider(base_dir=_copy_rich_fixture(tmp_path))
    quote = provider.get_quote("ALFA")
    financials = provider.get_financials("ALFA")

    result = calculate_relative_valuation(
        ValuationInput(
            ticker="ALFA",
            current_price=quote.price,
            revenue=financials.revenue,
            free_cash_flow=financials.free_cash_flow,
            eps=financials.eps,
            shares_outstanding=financials.shares_outstanding,
            cash=financials.cash,
            debt=financials.debt,
            ebitda=financials.ebitda,
            market_cap=financials.market_cap,
            peer_inputs=provider.get_peer_valuation_inputs("ALFA"),
        )
    )

    assert result.status == "calculated"
    assert result.peer_count == 2
    assert result.peer_median_multiples["pe"] is not None
    assert result.peer_group == "fixture_group"
    assert result.relative_discount_premium_by_metric["pe"] is not None
    assert result.peer_relative_status in {"peer_discount", "peer_premium", "mixed"}
    assert result.relative_opportunity_score is not None


def test_relative_valuation_returns_partial_when_only_some_peer_metrics_are_available():
    valuation_input = ValuationInput(
        ticker="ALFA",
        current_price=150.0,
        revenue=1000.0,
        free_cash_flow=120.0,
        eps=6.0,
        shares_outstanding=10.0,
        cash=200.0,
        debt=50.0,
        ebitda=180.0,
        market_cap=1500.0,
        peer_inputs=[
            {
                "ticker": "BETA",
                "current_price": 85.0,
                "revenue": 800.0,
                "eps": 4.0,
                "shares_outstanding": 12.0,
                "market_cap": 1020.0,
                "peer_group": "fixture_group",
            },
            {
                "ticker": "GAMMA",
                "current_price": 66.0,
                "revenue": 650.0,
                "eps": 3.5,
                "free_cash_flow": 70.0,
                "shares_outstanding": 11.0,
                "market_cap": 726.0,
                "peer_group": "fixture_group",
            },
        ],
    )

    result = calculate_relative_valuation(valuation_input)

    assert result.status == "partial"
    assert result.peer_median_multiples["pe"] is not None
    assert result.peer_missing_data_warnings
    assert result.relative_discount_premium_by_metric["ev_ebitda"] is None
