from __future__ import annotations

from dataclasses import asdict, dataclass, field, replace
from typing import Any


ALLOWED_RESULT_STATUSES = {"calculated", "partial", "insufficient_data", "not_applicable", "peer_data_unavailable"}
DEFAULT_NORMALIZED_GROWTH_TARGET = 0.08
DEFAULT_BEAR_NORMALIZED_GROWTH_TARGET = 0.05
DEFAULT_BULL_NORMALIZED_GROWTH_TARGET = 0.10
DEFAULT_MAX_START_GROWTH = 0.40
DEFAULT_MAX_FCF_MARGIN = 0.45
DEFAULT_MAX_PROJECTED_FCF_GROWTH = 0.35


@dataclass
class ValuationInput:
    ticker: str
    current_price: float | None = None
    revenue: float | None = None
    revenue_growth: float | None = None
    free_cash_flow: float | None = None
    fcf_margin: float | None = None
    operating_margin: float | None = None
    profit_margin: float | None = None
    eps: float | None = None
    ebitda: float | None = None
    shares_outstanding: float | None = None
    cash: float | None = None
    debt: float | None = None
    net_debt: float | None = None
    market_cap: float | None = None
    trailing_pe: float | None = None
    forward_pe: float | None = None
    price_to_book: float | None = None
    peer_inputs: list[dict[str, Any]] = field(default_factory=list)
    source_metadata: list[dict[str, Any]] = field(default_factory=list)
    screener_context: dict[str, Any] = field(default_factory=dict)

    def to_dict(self) -> dict[str, Any]:
        return asdict(self)


@dataclass
class DCFAssumptions:
    method_name: str
    revenue_growth: float | None
    fcf_margin: float | None
    operating_margin: float | None
    tax_rate: float
    wacc: float
    terminal_growth: float
    forecast_years: int
    base_revenue: float | None = None
    base_free_cash_flow: float | None = None
    shares_outstanding: float | None = None
    cash: float | None = None
    debt: float | None = None
    net_debt: float | None = None
    observed_revenue_growth: float | None = None
    observed_fcf_margin: float | None = None
    normalized_growth_target: float = DEFAULT_NORMALIZED_GROWTH_TARGET
    max_start_growth: float = DEFAULT_MAX_START_GROWTH
    max_fcf_margin: float = DEFAULT_MAX_FCF_MARGIN
    max_projected_fcf_growth: float | None = DEFAULT_MAX_PROJECTED_FCF_GROWTH
    applied_growth_by_year: list[float] = field(default_factory=list)
    growth_was_capped: bool = False
    fcf_margin_was_capped: bool = False

    def to_dict(self) -> dict[str, Any]:
        return asdict(self)


@dataclass
class DCFResult:
    status: str
    method_name: str
    assumptions: dict[str, Any]
    missing_fields: list[str]
    warnings: list[str]
    notes: list[str]
    projected_fcfs: list[float] = field(default_factory=list)
    discounted_fcfs: list[float] = field(default_factory=list)
    terminal_value: float | None = None
    discounted_terminal_value: float | None = None
    enterprise_value: float | None = None
    equity_value: float | None = None
    fair_value_per_share: float | None = None
    source_metadata: list[dict[str, Any]] = field(default_factory=list)

    def to_dict(self) -> dict[str, Any]:
        return asdict(self)


@dataclass
class RelativeValuationResult:
    status: str
    method_name: str
    available_multiples: dict[str, float | None]
    subject_multiples: dict[str, float | None]
    peer_median_multiples: dict[str, float | None]
    peer_tickers: list[str]
    peer_count: int
    peer_group: str | None
    relative_discount_premium_by_metric: dict[str, float | None]
    peer_relative_status: str
    relative_opportunity_score: float | None
    missing_fields: list[str]
    warnings: list[str]
    peer_missing_data_warnings: list[str]
    notes: list[str]
    source_metadata: list[dict[str, Any]] = field(default_factory=list)

    def to_dict(self) -> dict[str, Any]:
        return asdict(self)


@dataclass
class ValuationScenario:
    name: str
    assumptions: DCFAssumptions
    dcf_result: DCFResult

    def to_dict(self) -> dict[str, Any]:
        return {
            "name": self.name,
            "assumptions": self.assumptions.to_dict(),
            "dcf_result": self.dcf_result.to_dict(),
        }


@dataclass
class SensitivityTable:
    status: str
    method_name: str
    wacc_values: list[float]
    terminal_growth_values: list[float]
    fair_value_grid: list[list[float | None]]
    missing_fields: list[str]
    warnings: list[str]
    notes: list[str]

    def to_dict(self) -> dict[str, Any]:
        return asdict(self)


@dataclass
class ValuationResult:
    status: str
    coverage: str
    method_name: str
    dcf_result: DCFResult
    relative_valuation: RelativeValuationResult
    scenarios: list[ValuationScenario]
    sensitivity_table: SensitivityTable
    missing_fields: list[str]
    warnings: list[str]
    notes: list[str]
    source_metadata: list[dict[str, Any]] = field(default_factory=list)

    def to_dict(self) -> dict[str, Any]:
        return {
            "status": self.status,
            "coverage": self.coverage,
            "method_name": self.method_name,
            "dcf_result": self.dcf_result.to_dict(),
            "relative_valuation": self.relative_valuation.to_dict(),
            "scenarios": [scenario.to_dict() for scenario in self.scenarios],
            "sensitivity_table": self.sensitivity_table.to_dict(),
            "missing_fields": self.missing_fields,
            "warnings": self.warnings,
            "notes": self.notes,
            "source_metadata": self.source_metadata,
        }


def _sorted_unique(items: list[str]) -> list[str]:
    return sorted({item for item in items if item})


def _default_base_growth(valuation_input: ValuationInput) -> float:
    return valuation_input.revenue_growth if valuation_input.revenue_growth is not None else 0.08


def _derive_fcf_margin(valuation_input: ValuationInput) -> float | None:
    if valuation_input.fcf_margin is not None:
        return valuation_input.fcf_margin
    if (
        valuation_input.free_cash_flow is not None
        and valuation_input.revenue is not None
        and valuation_input.revenue != 0
    ):
        return valuation_input.free_cash_flow / valuation_input.revenue
    return None


def _build_scenario_assumptions(
    valuation_input: ValuationInput,
    name: str,
    *,
    growth_delta: float,
    margin_delta: float,
    wacc: float,
    terminal_growth: float,
    normalized_growth_target: float,
    forecast_years: int = 5,
    tax_rate: float = 0.21,
) -> DCFAssumptions:
    base_growth = _default_base_growth(valuation_input)
    base_margin = _derive_fcf_margin(valuation_input)
    scenario_growth = base_growth + growth_delta
    scenario_margin = None if base_margin is None else max(base_margin + margin_delta, -0.5)
    base_free_cash_flow = valuation_input.free_cash_flow
    base_revenue = valuation_input.revenue
    method_name = "fcf_direct" if base_free_cash_flow is not None else "revenue_fcf_margin"
    return DCFAssumptions(
        method_name=method_name,
        revenue_growth=scenario_growth,
        fcf_margin=scenario_margin,
        operating_margin=valuation_input.operating_margin,
        tax_rate=tax_rate,
        wacc=wacc,
        terminal_growth=terminal_growth,
        forecast_years=forecast_years,
        base_revenue=base_revenue,
        base_free_cash_flow=base_free_cash_flow,
        shares_outstanding=valuation_input.shares_outstanding,
        cash=valuation_input.cash,
        debt=valuation_input.debt,
        net_debt=valuation_input.net_debt,
        observed_revenue_growth=scenario_growth,
        observed_fcf_margin=scenario_margin,
        normalized_growth_target=normalized_growth_target,
    )


def build_default_scenarios(valuation_input: ValuationInput) -> dict[str, DCFAssumptions]:
    return {
        "bear": _build_scenario_assumptions(
            valuation_input,
            "bear",
            growth_delta=-0.04,
            margin_delta=-0.03,
            wacc=0.11,
            terminal_growth=0.02,
            normalized_growth_target=DEFAULT_BEAR_NORMALIZED_GROWTH_TARGET,
        ),
        "base": _build_scenario_assumptions(
            valuation_input,
            "base",
            growth_delta=0.0,
            margin_delta=0.0,
            wacc=0.09,
            terminal_growth=0.03,
            normalized_growth_target=DEFAULT_NORMALIZED_GROWTH_TARGET,
        ),
        "bull": _build_scenario_assumptions(
            valuation_input,
            "bull",
            growth_delta=0.04,
            margin_delta=0.03,
            wacc=0.08,
            terminal_growth=0.035,
            normalized_growth_target=DEFAULT_BULL_NORMALIZED_GROWTH_TARGET,
        ),
    }


def validate_dcf_assumptions(assumptions: DCFAssumptions) -> list[str]:
    warnings: list[str] = []
    if assumptions.forecast_years <= 0:
        warnings.append("forecast_years must be positive.")
    if assumptions.wacc <= 0:
        warnings.append("WACC must be positive.")
    if assumptions.terminal_growth < -0.02 or assumptions.terminal_growth > 0.05:
        warnings.append("Terminal growth should stay within a conservative long-term range.")
    if assumptions.terminal_growth >= assumptions.wacc:
        warnings.append("Terminal growth must remain below WACC.")
    if assumptions.shares_outstanding is not None and assumptions.shares_outstanding <= 0:
        warnings.append("Shares outstanding must be positive when present.")
    if assumptions.max_start_growth <= -1:
        warnings.append("max_start_growth must remain above -100%.")
    if assumptions.max_fcf_margin <= -1:
        warnings.append("max_fcf_margin must remain above -100%.")
    return warnings


def _build_growth_path(start_growth: float, target_growth: float, years: int) -> list[float]:
    if years <= 0:
        return []
    if years == 1:
        return [target_growth]
    step = (start_growth - target_growth) / years
    path = [start_growth - (step * year) for year in range(1, years + 1)]
    return [max(growth, -0.95) for growth in path]


def _normalize_dcf_assumptions(assumptions: DCFAssumptions) -> tuple[DCFAssumptions, list[str]]:
    warnings: list[str] = []
    observed_growth = assumptions.observed_revenue_growth if assumptions.observed_revenue_growth is not None else assumptions.revenue_growth
    applied_start_growth = assumptions.revenue_growth if assumptions.revenue_growth is not None else 0.0
    growth_was_capped = False
    if observed_growth is not None:
        applied_start_growth = observed_growth
        if observed_growth > assumptions.max_start_growth:
            applied_start_growth = assumptions.max_start_growth
            growth_was_capped = True
            warnings.append(
                f"Observed revenue growth {observed_growth:.1%} exceeded the conservative start-growth cap of "
                f"{assumptions.max_start_growth:.1%} and was normalized before projection."
            )
        elif observed_growth < -0.50:
            applied_start_growth = -0.50
            growth_was_capped = True
            warnings.append(
                f"Observed revenue growth {observed_growth:.1%} was below the conservative downside floor of -50.0% "
                "and was normalized before projection."
            )
    target_growth = min(assumptions.normalized_growth_target, assumptions.max_start_growth)
    if target_growth >= assumptions.wacc:
        target_growth = min(max(assumptions.terminal_growth + 0.02, assumptions.terminal_growth), assumptions.wacc - 0.01)
        warnings.append("Normalized growth target was reduced to keep it conservatively below WACC.")
    if target_growth < -0.10:
        target_growth = -0.10
        warnings.append("Normalized growth target was raised to keep it within a conservative long-term range.")

    applied_growth_by_year = _build_growth_path(applied_start_growth, target_growth, assumptions.forecast_years)
    if assumptions.max_projected_fcf_growth is not None:
        clipped_path: list[float] = []
        path_capped = False
        for growth in applied_growth_by_year:
            clipped_growth = min(growth, assumptions.max_projected_fcf_growth)
            if clipped_growth != growth:
                path_capped = True
            clipped_path.append(clipped_growth)
        applied_growth_by_year = clipped_path
        if path_capped:
            warnings.append(
                f"Projected growth was capped at {assumptions.max_projected_fcf_growth:.1%} in the early forecast years."
            )

    observed_fcf_margin = assumptions.observed_fcf_margin if assumptions.observed_fcf_margin is not None else assumptions.fcf_margin
    applied_fcf_margin = assumptions.fcf_margin
    fcf_margin_was_capped = False
    if applied_fcf_margin is not None and applied_fcf_margin > assumptions.max_fcf_margin:
        observed_value = observed_fcf_margin if observed_fcf_margin is not None else applied_fcf_margin
        applied_fcf_margin = assumptions.max_fcf_margin
        fcf_margin_was_capped = True
        warnings.append(
            f"Observed FCF margin {observed_value:.1%} exceeded the conservative margin cap of "
            f"{assumptions.max_fcf_margin:.1%} and was normalized before projection."
        )

    normalized = replace(
        assumptions,
        revenue_growth=applied_start_growth,
        fcf_margin=applied_fcf_margin,
        observed_revenue_growth=observed_growth,
        observed_fcf_margin=observed_fcf_margin,
        normalized_growth_target=target_growth,
        applied_growth_by_year=applied_growth_by_year,
        growth_was_capped=growth_was_capped,
        fcf_margin_was_capped=fcf_margin_was_capped,
    )
    return normalized, warnings


def calculate_dcf(valuation_input: ValuationInput, assumptions: DCFAssumptions) -> DCFResult:
    normalized_assumptions, normalization_warnings = _normalize_dcf_assumptions(assumptions)
    validation_warnings = validate_dcf_assumptions(normalized_assumptions)
    warnings = validation_warnings + normalization_warnings
    missing_fields: list[str] = []
    notes = [
        "DCF output is informational only and not a trading recommendation.",
        "Projected cash flows are driven by explicit scenario assumptions rather than hidden model calls.",
    ]

    if validation_warnings:
        return DCFResult(
            status="insufficient_data",
            method_name="dcf",
            assumptions=normalized_assumptions.to_dict(),
            missing_fields=missing_fields,
            warnings=warnings,
            notes=notes + ["DCF calculation was skipped because assumptions failed validation."],
            source_metadata=list(valuation_input.source_metadata),
        )

    projected_fcfs: list[float] = []
    discounted_fcfs: list[float] = []
    current_fcf: float | None = None

    if valuation_input.free_cash_flow is not None:
        current_fcf = valuation_input.free_cash_flow
        if current_fcf < 0:
            warnings.append("Base free cash flow is negative, so DCF outputs may be less stable.")
    elif valuation_input.revenue is not None and normalized_assumptions.fcf_margin is not None:
        current_fcf = valuation_input.revenue * normalized_assumptions.fcf_margin
        notes.append("Base free cash flow was derived from revenue and FCF margin because direct FCF was unavailable.")
    else:
        if valuation_input.free_cash_flow is None:
            missing_fields.append("free_cash_flow")
        if valuation_input.revenue is None:
            missing_fields.append("revenue")
        if normalized_assumptions.fcf_margin is None:
            missing_fields.append("fcf_margin")
        return DCFResult(
            status="insufficient_data",
            method_name="dcf",
            assumptions=normalized_assumptions.to_dict(),
            missing_fields=_sorted_unique(missing_fields),
            warnings=warnings,
            notes=notes + ["DCF requires either direct free cash flow or revenue plus FCF margin."],
            source_metadata=list(valuation_input.source_metadata),
        )

    for growth in normalized_assumptions.applied_growth_by_year:
        current_fcf = current_fcf * (1 + growth)
        projected_fcfs.append(current_fcf)
        discounted_fcfs.append(current_fcf / ((1 + normalized_assumptions.wacc) ** len(projected_fcfs)))

    terminal_fcf = projected_fcfs[-1] * (1 + normalized_assumptions.terminal_growth)
    terminal_value = terminal_fcf / (normalized_assumptions.wacc - normalized_assumptions.terminal_growth)
    discounted_terminal_value = terminal_value / ((1 + normalized_assumptions.wacc) ** normalized_assumptions.forecast_years)
    enterprise_value = sum(discounted_fcfs) + discounted_terminal_value

    equity_value = None
    if normalized_assumptions.cash is not None and normalized_assumptions.debt is not None:
        equity_value = enterprise_value + normalized_assumptions.cash - normalized_assumptions.debt
    elif normalized_assumptions.net_debt is not None:
        equity_value = enterprise_value - normalized_assumptions.net_debt
    else:
        warnings.append("Equity value could not be derived because cash/debt or net debt is unavailable.")
        missing_fields.extend(["cash_or_debt"])

    fair_value_per_share = None
    if equity_value is not None and normalized_assumptions.shares_outstanding is not None and normalized_assumptions.shares_outstanding > 0:
        fair_value_per_share = equity_value / normalized_assumptions.shares_outstanding
    elif equity_value is not None and normalized_assumptions.shares_outstanding is None:
        warnings.append("Fair value per share could not be derived because shares outstanding is unavailable.")
        missing_fields.append("shares_outstanding")

    return DCFResult(
        status="calculated",
        method_name="dcf",
        assumptions=normalized_assumptions.to_dict(),
        missing_fields=_sorted_unique(missing_fields),
        warnings=_sorted_unique(warnings),
        notes=notes,
        projected_fcfs=projected_fcfs,
        discounted_fcfs=discounted_fcfs,
        terminal_value=terminal_value,
        discounted_terminal_value=discounted_terminal_value,
        enterprise_value=enterprise_value,
        equity_value=equity_value,
        fair_value_per_share=fair_value_per_share,
        source_metadata=list(valuation_input.source_metadata),
    )


def calculate_relative_valuation(valuation_input: ValuationInput) -> RelativeValuationResult:
    available_multiples: dict[str, float | None] = {
        "pe": None,
        "ps": None,
        "p_fcf": None,
        "ev_ebitda": None,
        "trailing_pe_reported": valuation_input.trailing_pe,
        "forward_pe_reported": valuation_input.forward_pe,
        "price_to_book_reported": valuation_input.price_to_book,
    }
    subject_multiples: dict[str, float | None] = {
        "pe": None,
        "ps": None,
        "p_fcf": None,
        "ev_ebitda": None,
    }
    missing_fields: list[str] = []
    warnings: list[str] = []
    peer_missing_data_warnings: list[str] = []
    notes = [
        "Relative valuation is limited to standalone multiples unless peer data is available locally.",
        "Standalone multiples are context, not a recommendation.",
    ]
    peer_median_multiples: dict[str, float | None] = {
        "pe": None,
        "ps": None,
        "p_fcf": None,
        "ev_ebitda": None,
    }
    peer_tickers = sorted({str(item.get("ticker")).upper() for item in valuation_input.peer_inputs if item.get("ticker")})
    peer_groups = sorted(
        {
            str(item.get("peer_group")).strip()
            for item in valuation_input.peer_inputs
            if item.get("peer_group")
        }
    )
    peer_group = peer_groups[0] if len(peer_groups) == 1 else None
    source_metadata = list(valuation_input.source_metadata)

    if valuation_input.current_price is not None and valuation_input.eps not in (None, 0):
        subject_multiples["pe"] = valuation_input.current_price / valuation_input.eps
    elif valuation_input.current_price is None:
        missing_fields.append("current_price")
    else:
        missing_fields.append("eps")

    market_cap = valuation_input.market_cap
    if market_cap is None and valuation_input.current_price is not None and valuation_input.shares_outstanding is not None:
        market_cap = valuation_input.current_price * valuation_input.shares_outstanding

    if market_cap is None:
        missing_fields.append("market_cap_or_price_and_shares")

    if market_cap is not None and valuation_input.revenue not in (None, 0):
        subject_multiples["ps"] = market_cap / valuation_input.revenue
    elif valuation_input.revenue is None:
        missing_fields.append("revenue")

    if market_cap is not None and valuation_input.free_cash_flow not in (None, 0):
        subject_multiples["p_fcf"] = market_cap / valuation_input.free_cash_flow
    elif valuation_input.free_cash_flow is None:
        missing_fields.append("free_cash_flow")

    if (
        market_cap is not None
        and valuation_input.ebitda not in (None, 0)
        and valuation_input.cash is not None
        and valuation_input.debt is not None
    ):
        subject_multiples["ev_ebitda"] = (market_cap + valuation_input.debt - valuation_input.cash) / valuation_input.ebitda
    else:
        if valuation_input.ebitda is None:
            missing_fields.append("ebitda")
        if valuation_input.cash is None:
            missing_fields.append("cash")
        if valuation_input.debt is None:
            missing_fields.append("debt")

    available_multiples.update(subject_multiples)

    computed_any = any(
        available_multiples[key] is not None
        for key in ("pe", "ps", "p_fcf", "ev_ebitda", "trailing_pe_reported", "forward_pe_reported", "price_to_book_reported")
    )
    peer_series: dict[str, list[float]] = {"pe": [], "ps": [], "p_fcf": [], "ev_ebitda": []}
    peer_metric_missing: dict[str, list[str]] = {"pe": [], "ps": [], "p_fcf": [], "ev_ebitda": []}
    for peer in valuation_input.peer_inputs:
        peer_ticker = str(peer.get("ticker")).upper() if peer.get("ticker") else "UNKNOWN"
        for source in peer.get("source_metadata", []):
            if source and source not in source_metadata:
                source_metadata.append(source)
        price = peer.get("current_price")
        shares = peer.get("shares_outstanding")
        market_cap = peer.get("market_cap") or (price * shares if price is not None and shares is not None else None)
        eps = peer.get("eps")
        revenue = peer.get("revenue")
        free_cash_flow = peer.get("free_cash_flow")
        ebitda = peer.get("ebitda")
        cash = peer.get("cash")
        debt = peer.get("debt")
        if price is not None and eps not in (None, 0):
            peer_series["pe"].append(price / eps)
        elif peer.get("trailing_pe") is not None:
            peer_series["pe"].append(float(peer["trailing_pe"]))
        else:
            peer_metric_missing["pe"].append(peer_ticker)
        if market_cap is not None and revenue not in (None, 0):
            peer_series["ps"].append(market_cap / revenue)
        else:
            peer_metric_missing["ps"].append(peer_ticker)
        if market_cap is not None and free_cash_flow not in (None, 0):
            peer_series["p_fcf"].append(market_cap / free_cash_flow)
        else:
            peer_metric_missing["p_fcf"].append(peer_ticker)
        if market_cap is not None and ebitda not in (None, 0) and cash is not None and debt is not None:
            peer_series["ev_ebitda"].append((market_cap + debt - cash) / ebitda)
        else:
            peer_metric_missing["ev_ebitda"].append(peer_ticker)
    for key, values in peer_series.items():
        if values:
            peer_median_multiples[key] = float(sorted(values)[len(values) // 2]) if len(values) % 2 == 1 else float((sorted(values)[len(values)//2 - 1] + sorted(values)[len(values)//2]) / 2)
    for metric, tickers in peer_metric_missing.items():
        if tickers and subject_multiples.get(metric) is not None:
            peer_missing_data_warnings.append(
                f"Peer inputs for {metric} were unavailable for: {', '.join(sorted(set(tickers)))}."
            )

    relative_discount_premium_by_metric: dict[str, float | None] = {
        "pe": None,
        "ps": None,
        "p_fcf": None,
        "ev_ebitda": None,
    }
    comparison_values: list[float] = []
    comparison_metrics: list[str] = []
    for metric in ("pe", "ps", "p_fcf", "ev_ebitda"):
        subject_value = subject_multiples.get(metric)
        peer_median = peer_median_multiples.get(metric)
        if subject_value is not None and peer_median not in (None, 0):
            relative_discount_premium_by_metric[metric] = (subject_value - peer_median) / peer_median
            comparison_values.append(relative_discount_premium_by_metric[metric] or 0.0)
            comparison_metrics.append(metric)

    if not comparison_values:
        peer_relative_status = "insufficient_peer_data"
        relative_opportunity_score = None
    else:
        if all(value <= -0.05 for value in comparison_values):
            peer_relative_status = "peer_discount"
        elif all(value >= 0.05 for value in comparison_values):
            peer_relative_status = "peer_premium"
        else:
            peer_relative_status = "mixed"
        metric_scores = [max(0.0, min(100.0, 50.0 - (value * 100.0))) for value in comparison_values]
        relative_opportunity_score = float(sum(metric_scores) / len(metric_scores))

    possible_subject_metrics = sum(1 for metric in ("pe", "ps", "p_fcf", "ev_ebitda") if subject_multiples.get(metric) is not None)
    if comparison_metrics:
        status = "calculated" if len(comparison_metrics) == possible_subject_metrics and possible_subject_metrics > 0 else "partial"
        notes.append("Peer median multiples were calculated from the local peers dataset.")
    elif computed_any:
        status = "peer_data_unavailable"
        warnings.append("Peer data is unavailable or insufficient, so only standalone multiples are shown.")
    else:
        status = "insufficient_data"
        notes.append("Standalone valuation multiples could not be calculated from the available data.")

    if valuation_input.screener_context.get("undervalued_candidates"):
        notes.append("Value/re-rating screener output is included elsewhere as context, not as a replacement for valuation inputs.")

    return RelativeValuationResult(
        status=status,
        method_name="relative_valuation",
        available_multiples=available_multiples,
        subject_multiples=subject_multiples,
        peer_median_multiples=peer_median_multiples,
        peer_tickers=peer_tickers,
        peer_count=len(peer_tickers),
        peer_group=peer_group,
        relative_discount_premium_by_metric=relative_discount_premium_by_metric,
        peer_relative_status=peer_relative_status,
        relative_opportunity_score=relative_opportunity_score,
        missing_fields=_sorted_unique(missing_fields),
        warnings=_sorted_unique(warnings),
        peer_missing_data_warnings=_sorted_unique(peer_missing_data_warnings),
        notes=notes,
        source_metadata=source_metadata,
    )


def build_sensitivity_table(
    valuation_input: ValuationInput,
    base_assumptions: DCFAssumptions,
    wacc_values: list[float] | None = None,
    terminal_growth_values: list[float] | None = None,
) -> SensitivityTable:
    wacc_values = wacc_values or [0.08, 0.09, 0.10]
    terminal_growth_values = terminal_growth_values or [0.02, 0.03, 0.04]
    warnings: list[str] = []
    missing_fields: list[str] = []
    notes = ["Sensitivity grid is shown only when the base DCF can produce a per-share value."]

    base_result = calculate_dcf(valuation_input, base_assumptions)
    if base_result.status != "calculated" or base_result.fair_value_per_share is None:
        missing_fields.extend(base_result.missing_fields)
        warnings.extend(base_result.warnings)
        return SensitivityTable(
            status="insufficient_data",
            method_name="dcf_sensitivity",
            wacc_values=wacc_values,
            terminal_growth_values=terminal_growth_values,
            fair_value_grid=[],
            missing_fields=_sorted_unique(missing_fields),
            warnings=_sorted_unique(warnings),
            notes=notes + ["Sensitivity requires a base DCF that can calculate fair value per share."],
        )

    fair_value_grid: list[list[float | None]] = []
    for wacc in wacc_values:
        row: list[float | None] = []
        for terminal_growth in terminal_growth_values:
            assumptions = DCFAssumptions(
                **{
                    **base_assumptions.to_dict(),
                    "wacc": wacc,
                    "terminal_growth": terminal_growth,
                }
            )
            result = calculate_dcf(valuation_input, assumptions)
            row.append(result.fair_value_per_share if result.status == "calculated" else None)
            warnings.extend(result.warnings)
        fair_value_grid.append(row)

    return SensitivityTable(
        status="calculated",
        method_name="dcf_sensitivity",
        wacc_values=wacc_values,
        terminal_growth_values=terminal_growth_values,
        fair_value_grid=fair_value_grid,
        missing_fields=[],
        warnings=_sorted_unique(warnings),
        notes=notes,
    )


def build_valuation_result(valuation_input: ValuationInput) -> ValuationResult:
    scenarios_map = build_default_scenarios(valuation_input)
    base_result = calculate_dcf(valuation_input, scenarios_map["base"])
    relative_result = calculate_relative_valuation(valuation_input)
    sensitivity = build_sensitivity_table(valuation_input, scenarios_map["base"])

    scenarios: list[ValuationScenario] = []
    for name in ("bear", "base", "bull"):
        assumptions = scenarios_map[name]
        scenarios.append(
            ValuationScenario(
                name=name,
                assumptions=assumptions,
                dcf_result=calculate_dcf(valuation_input, assumptions),
            )
        )

    calculated_components = [
        base_result.status == "calculated",
        relative_result.status in {"calculated", "partial", "peer_data_unavailable"},
    ]
    status = "calculated" if any(calculated_components) else "insufficient_data"
    coverage = "partial" if any(calculated_components) and not all(calculated_components) else ("full" if all(calculated_components) else "insufficient")

    missing_fields = _sorted_unique(
        base_result.missing_fields
        + relative_result.missing_fields
        + sensitivity.missing_fields
    )
    warnings = _sorted_unique(
        base_result.warnings
        + relative_result.warnings
        + sensitivity.warnings
        + [warning for scenario in scenarios for warning in scenario.dcf_result.warnings]
    )

    notes = [
        "Valuation is informational only and should not be treated as financial advice.",
        "Results remain bounded by the quality and completeness of the local research data.",
    ]
    if coverage == "partial":
        notes.append("Only part of the valuation stack could be calculated from the available inputs.")

    return ValuationResult(
        status=status,
        coverage=coverage,
        method_name="dcf_and_relative",
        dcf_result=base_result,
        relative_valuation=relative_result,
        scenarios=scenarios,
        sensitivity_table=sensitivity,
        missing_fields=missing_fields,
        warnings=warnings,
        notes=notes,
        source_metadata=list(valuation_input.source_metadata),
    )
