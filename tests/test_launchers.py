from pathlib import Path


def test_makefile_contains_convenience_targets():
    makefile = Path("Makefile").read_text(encoding="utf-8")

    for target in (
        "help",
        "test",
        "pipeline",
        "monthly",
        "track-record",
        "validate-data",
        "research-health",
        "action-queue",
        "verify",
        "daily",
        "dashboard",
        "sec-stage",
        "sec-validate",
        "sec-preview",
        "sec-apply",
        "universe-preview",
        "universe-apply",
        "coverage",
        "onboarding",
        "templates",
        "price-status",
        "price-validate",
        "price-preview",
        "price-apply",
        "price-refresh",
        "price-normalize",
    ):
        assert f"{target}:" in makefile


def test_makefile_help_documents_key_workflows():
    makefile = Path("Makefile").read_text(encoding="utf-8")

    for phrase in (
        "Stock Research Screener convenience commands",
        "make verify",
        "make daily",
        "make price-normalize INPUT=data/raw/prices/NVDA.csv TICKER=NVDA SOURCE=yahoo_manual",
        "SEC_USER_AGENT='Name email@example.com' make sec-stage TICKERS=NVDA,MSFT",
        "make universe-preview",
    ):
        assert phrase in makefile


def test_shell_launchers_anchor_to_repo_root():
    for script_name in ("daily.sh", "dashboard.sh", "validate_all.sh"):
        script = (Path("scripts") / script_name).read_text(encoding="utf-8")
        assert "set -euo pipefail" in script
        assert "REPO_ROOT" in script
        assert 'cd "${REPO_ROOT}"' in script
        assert 'echo "Repo root: ${REPO_ROOT}"' in script
