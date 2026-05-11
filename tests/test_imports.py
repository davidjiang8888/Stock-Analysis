import importlib


def test_new_modules_import_cleanly():
    module_names = [
        "src.providers.market_data",
        "src.providers.mock_market_data",
        "src.providers.local_market_data",
        "src.providers.yfinance_provider",
        "src.stock_report",
        "src.valuation",
    ]
    for module_name in module_names:
        module = importlib.import_module(module_name)
        assert module is not None
