from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path
from typing import Any

import yaml


@dataclass
class AppConfig:
    raw: dict[str, Any]

    @classmethod
    def load(cls, path: Path) -> "AppConfig":
        with path.open("r", encoding="utf-8") as handle:
            data = yaml.safe_load(handle) or {}
        return cls(raw=data)

    @property
    def benchmarks(self) -> dict[str, list[str]]:
        return self.raw.get("benchmarks", {})

    @property
    def momentum_rules(self) -> dict[str, Any]:
        return self.raw.get("momentum_rules", {})

    @property
    def moving_averages(self) -> dict[str, list[int]]:
        return self.raw.get("moving_averages", {})

    @property
    def returns(self) -> dict[str, Any]:
        return self.raw.get("returns", {})

    @property
    def volume_rules(self) -> dict[str, Any]:
        return self.raw.get("volume_rules", {})

    @property
    def risk_rules(self) -> dict[str, Any]:
        return self.raw.get("risk_rules", {})

    @property
    def portfolio_rules(self) -> dict[str, Any]:
        return self.raw.get("portfolio_rules", {})

    @property
    def value_rules(self) -> dict[str, Any]:
        return self.raw.get("value_rules", {})

    @property
    def state_labels(self) -> list[str]:
        return self.raw.get("state_labels", [])

    def get_pct(self, section: str, key: str, default: float) -> float:
        value = self.raw.get(section, {}).get(key, default)
        return float(value) / 100.0 if float(value) > 1 else float(value)
