import builtins

import pytest

from src.providers.yfinance_provider import YFinanceProvider


def test_yfinance_provider_fails_gracefully_when_dependency_is_missing(monkeypatch: pytest.MonkeyPatch):
    original_import = builtins.__import__

    def fake_import(name, *args, **kwargs):
        if name == "yfinance":
            raise ImportError("missing yfinance")
        return original_import(name, *args, **kwargs)

    monkeypatch.setattr(builtins, "__import__", fake_import)

    with pytest.raises(RuntimeError, match="yfinance is not installed"):
        YFinanceProvider()
