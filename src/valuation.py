from __future__ import annotations

from dataclasses import asdict, dataclass, field
from typing import Any


@dataclass
class DCFScenarioCase:
    name: str
    revenue_growth: float
    operating_margin: float
    terminal_growth: float
    wacc: float

    def to_dict(self) -> dict[str, Any]:
        return asdict(self)


@dataclass
class DCFValuationAssumptions:
    base_year_free_cash_flow: float | None
    shares_outstanding: float | None
    net_debt: float | None
    forecast_years: int
    tax_rate: float | None
    base_case: DCFScenarioCase
    bull_case: DCFScenarioCase
    bear_case: DCFScenarioCase
    notes: list[str] = field(default_factory=list)

    def to_dict(self) -> dict[str, Any]:
        return {
            "base_year_free_cash_flow": self.base_year_free_cash_flow,
            "shares_outstanding": self.shares_outstanding,
            "net_debt": self.net_debt,
            "forecast_years": self.forecast_years,
            "tax_rate": self.tax_rate,
            "base_case": self.base_case.to_dict(),
            "bull_case": self.bull_case.to_dict(),
            "bear_case": self.bear_case.to_dict(),
            "notes": self.notes,
        }


@dataclass
class RelativeValuationAssumptions:
    peer_tickers: list[str]
    target_metric: str
    low_multiple: float | None
    base_multiple: float | None
    high_multiple: float | None
    notes: list[str] = field(default_factory=list)

    def to_dict(self) -> dict[str, Any]:
        return asdict(self)


@dataclass
class SensitivityPoint:
    wacc: float
    terminal_growth: float
    implied_value_per_share: float | None = None
    notes: list[str] = field(default_factory=lambda: ["TODO: connect model outputs when full valuation math is available."])

    def to_dict(self) -> dict[str, Any]:
        return asdict(self)


@dataclass
class ValuationScaffold:
    ticker: str
    dcf: DCFValuationAssumptions
    relative: RelativeValuationAssumptions
    sensitivity_table: list[SensitivityPoint]
    notes: list[str] = field(default_factory=list)

    def to_dict(self) -> dict[str, Any]:
        return {
            "ticker": self.ticker,
            "dcf": self.dcf.to_dict(),
            "relative": self.relative.to_dict(),
            "sensitivity_table": [point.to_dict() for point in self.sensitivity_table],
            "notes": self.notes,
        }


def validate_dcf_assumptions(assumptions: DCFValuationAssumptions) -> None:
    if assumptions.forecast_years <= 0:
        raise ValueError("forecast_years must be positive")
    for case in (assumptions.bear_case, assumptions.base_case, assumptions.bull_case):
        if case.wacc <= 0:
            raise ValueError(f"{case.name} WACC must be positive")
        if case.terminal_growth >= case.wacc:
            raise ValueError(f"{case.name} terminal growth must be below WACC")
        if case.operating_margin < -1:
            raise ValueError(f"{case.name} operating margin is unrealistically low")


def build_default_valuation_scaffold(
    ticker: str,
    current_price: float | None = None,
    shares_outstanding: float | None = None,
    net_debt: float | None = None,
    free_cash_flow: float | None = None,
    peer_tickers: list[str] | None = None,
) -> ValuationScaffold:
    base_case = DCFScenarioCase("base", revenue_growth=0.08, operating_margin=0.20, terminal_growth=0.03, wacc=0.09)
    bull_case = DCFScenarioCase("bull", revenue_growth=0.12, operating_margin=0.24, terminal_growth=0.035, wacc=0.085)
    bear_case = DCFScenarioCase("bear", revenue_growth=0.03, operating_margin=0.16, terminal_growth=0.02, wacc=0.10)

    dcf = DCFValuationAssumptions(
        base_year_free_cash_flow=free_cash_flow,
        shares_outstanding=shares_outstanding,
        net_debt=net_debt,
        forecast_years=5,
        tax_rate=0.21,
        base_case=base_case,
        bull_case=bull_case,
        bear_case=bear_case,
        notes=[
            "Phase 1 scaffold only: assumptions are explicit, but full DCF projection math is still a TODO.",
            "Use with scenario analysis rather than single-point precision.",
        ],
    )
    validate_dcf_assumptions(dcf)

    relative = RelativeValuationAssumptions(
        peer_tickers=peer_tickers or [],
        target_metric="forward_pe",
        low_multiple=None,
        base_multiple=None,
        high_multiple=None,
        notes=[
            "Fill in peer multiples once peer set and source coverage are available.",
            "Relative valuation should be interpreted alongside DCF scenarios.",
        ],
    )

    sensitivity_table = [
        SensitivityPoint(wacc=0.08, terminal_growth=0.02),
        SensitivityPoint(wacc=0.08, terminal_growth=0.03),
        SensitivityPoint(wacc=0.09, terminal_growth=0.02),
        SensitivityPoint(wacc=0.09, terminal_growth=0.03),
        SensitivityPoint(wacc=0.10, terminal_growth=0.02),
        SensitivityPoint(wacc=0.10, terminal_growth=0.03),
    ]

    notes = [
        "Valuation output is research scaffolding only and not a trading recommendation.",
    ]
    if current_price is not None:
        notes.append(f"Current market price reference captured at {current_price:.2f}.")

    return ValuationScaffold(
        ticker=ticker.upper(),
        dcf=dcf,
        relative=relative,
        sensitivity_table=sensitivity_table,
        notes=notes,
    )
