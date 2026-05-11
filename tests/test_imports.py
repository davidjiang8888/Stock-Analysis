import importlib


def test_new_modules_import_cleanly():
    module_names = [
        "src.providers.market_data",
        "src.providers.mock_market_data",
        "src.providers.local_data_catalog",
        "src.providers.local_importer",
        "src.providers.local_schemas",
        "src.providers.local_templates",
        "src.providers.local_market_data",
        "src.providers.sec_companyfacts",
        "src.providers.yfinance_provider",
        "src.dashboard",
        "src.stock_report",
        "src.valuation",
    ]
    for module_name in module_names:
        module = importlib.import_module(module_name)
        assert module is not None
