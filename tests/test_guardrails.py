from pathlib import Path


BANNED_EXECUTION_TOKENS = (
    "def place_order(",
    "def submit_order(",
    "def execute_trade(",
    "def route_order(",
    "alpaca",
    "interactivebrokers",
    "ibkr",
)

BANNED_RECOMMENDATION_PHRASES = (
    "buy now",
    "sell now",
    "strong buy",
    "guaranteed return",
)


def test_no_trade_execution_module_or_order_placement_was_introduced():
    root = Path("src")
    source_text = "\n".join(path.read_text(encoding="utf-8") for path in root.rglob("*.py"))
    lowered = source_text.lower()
    for token in BANNED_EXECUTION_TOKENS:
        assert token not in lowered


def test_stock_report_workflow_does_not_introduce_direct_recommendation_language():
    guarded_paths = (
        Path("src/stock_report.py"),
        Path("src/valuation.py"),
        Path("src/dashboard.py"),
        Path("src/providers/market_data.py"),
        Path("src/providers/local_market_data.py"),
        Path("src/providers/sec_companyfacts.py"),
    )
    source_text = "\n".join(path.read_text(encoding="utf-8") for path in guarded_paths)
    lowered = source_text.lower()
    for phrase in BANNED_RECOMMENDATION_PHRASES:
        assert phrase not in lowered


def test_gitignore_covers_local_runtime_artifacts():
    gitignore = Path(".gitignore").read_text(encoding="utf-8")
    expected_entries = (
        "data/cache/",
        "data/backups/",
        "data/imports/*.csv",
        "!data/imports/.gitkeep",
        "outputs/*stock_report.json",
        "local_artifacts_backup/",
    )
    for entry in expected_entries:
        assert entry in gitignore
