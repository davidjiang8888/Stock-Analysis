import json

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


def test_relative_valuation_returns_peer_data_unavailable_with_reported_multiple_only():
    valuation_input = ValuationInput(
        ticker="NVDA",
        trailing_pe=34.0,
    )

    result = calculate_relative_valuation(valuation_input)

    assert result.status == "peer_data_unavailable"
    assert result.available_multiples["trailing_pe_reported"] == 34.0
