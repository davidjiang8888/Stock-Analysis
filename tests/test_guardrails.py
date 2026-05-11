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


def test_no_trade_execution_module_or_order_placement_was_introduced():
    root = Path("src")
    source_text = "\n".join(path.read_text(encoding="utf-8") for path in root.rglob("*.py"))
    lowered = source_text.lower()
    for token in BANNED_EXECUTION_TOKENS:
        assert token not in lowered
