from pathlib import Path


def test_makefile_contains_convenience_targets():
    makefile = Path("Makefile").read_text(encoding="utf-8")

    for target in (
        "help",
        "status",
        "test",
        "pipeline",
        "monthly",
        "track-record",
        "validate-data",
        "research-health",
        "action-queue",
        "verify",
        "validate-all",
        "daily",
        "dashboard",
        "dashboard-smoke",
        "sec-stage",
        "sec-validate",
        "sec-preview",
        "sec-apply",
        "universe-preview",
        "universe-apply",
        "coverage",
        "data-wizard",
        "unlock-ladder",
        "unlock-summary",
        "command-bundles",
        "command-bundle-details",
        "command-bundle-runbook",
        "bundle-prices",
        "bundle-fundamentals",
        "bundle-peers",
        "runbook-prices",
        "runbook-fundamentals",
        "runbook-peers",
        "onboarding",
        "templates",
        "price-status",
        "price-worklist",
        "fundamentals-peer-worklist",
        "optional-context-worklist",
        "sec-stage-queue",
        "peer-mapping-queue",
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
        "make status",
        "make verify",
        "make validate-all",
        "make daily",
        "make dashboard-smoke",
        "make data-wizard",
        "make unlock-ladder",
        "make unlock-summary",
        "make command-bundles",
        "make command-bundle-details",
        "make command-bundle-runbook",
        "make bundle-prices",
        "make bundle-fundamentals",
        "make bundle-peers",
        "make runbook-prices",
        "make runbook-fundamentals",
        "make runbook-peers",
        "make price-worklist",
        "make fundamentals-peer-worklist",
        "make optional-context-worklist",
        "make sec-stage-queue",
        "make peer-mapping-queue",
        "make price-normalize INPUT=data/raw/prices/NVDA.csv TICKER=NVDA SOURCE=yahoo_manual",
        "SEC_USER_AGENT='Name email@example.com' make sec-stage TICKERS=NVDA,MSFT",
        "make universe-preview",
    ):
        assert phrase in makefile


def test_shell_launchers_anchor_to_repo_root():
    for script_name in ("daily.sh", "dashboard.sh", "validate_all.sh", "smoke_dashboard.sh"):
        script = (Path("scripts") / script_name).read_text(encoding="utf-8")
        assert "set -euo pipefail" in script
        assert "REPO_ROOT" in script
        assert 'cd "${REPO_ROOT}"' in script
        assert 'echo "Repo root: ${REPO_ROOT}"' in script


def test_dashboard_smoke_launcher_checks_streamlit_health_safely():
    script = Path("scripts/smoke_dashboard.sh").read_text(encoding="utf-8")

    assert "_stcore/health" in script
    assert "SERVER_PID" in script
    assert "trap cleanup EXIT" in script


def test_validate_all_reuses_current_verification_targets():
    script = Path("scripts/validate_all.sh").read_text(encoding="utf-8")

    assert "make verify" in script
    assert "make dashboard-smoke" in script
    assert "python3 -m pytest tests -q" not in script
