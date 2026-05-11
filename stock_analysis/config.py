from pathlib import Path


BASE_DIR = Path(__file__).resolve().parent.parent
DATA_DIR = BASE_DIR / "data"
OUTPUT_DIR = BASE_DIR / "outputs"

PRICE_FILE = DATA_DIR / "prices.csv"
FUNDAMENTALS_FILE = DATA_DIR / "fundamentals.csv"
HOLDINGS_FILE = DATA_DIR / "holdings.csv"

BENCHMARKS = ("SPY", "QQQ")
ETF_PURPOSES = {"SPY", "QQQ", "XLK", "XLF", "SMH", "IWM", "XLE", "TLT", "GLD"}

MAX_POSITION_SIZE = 0.15
HIGH_VOLATILITY_THRESHOLD = 0.045
EXTENSION_THRESHOLD = 0.08
PIVOT_PROXIMITY_THRESHOLD = 0.05
