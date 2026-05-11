from __future__ import annotations

from abc import ABC, abstractmethod
from dataclasses import dataclass, field

import pandas as pd


@dataclass
class FetchResult:
    prices: pd.DataFrame
    warnings: list[str] = field(default_factory=list)


class DataFetcher(ABC):
    @abstractmethod
    def load_ohlcv(self, tickers: list[str]) -> FetchResult:
        raise NotImplementedError
