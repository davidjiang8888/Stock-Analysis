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
        "data-sources-check",
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
        "bundle-prices-broader",
        "bundle-fundamentals-broader",
        "bundle-peers-broader",
        "detail-prices",
        "detail-fundamentals",
        "detail-peers",
        "detail-prices-broader",
        "detail-fundamentals-broader",
        "detail-peers-broader",
        "runbook-prices",
        "runbook-fundamentals",
        "runbook-peers",
        "runbook-prices-broader",
        "runbook-fundamentals-broader",
        "runbook-peers-broader",
        "focus-price",
        "focus-fundamentals",
        "focus-peers",
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
        "make data-sources-check",
        "make data-wizard",
        "make unlock-ladder",
        "make unlock-summary",
        "make command-bundles",
        "make command-bundle-details",
        "make command-bundle-runbook",
        "make bundle-prices",
        "make bundle-fundamentals",
        "make bundle-peers",
        "make bundle-prices-broader",
        "make bundle-fundamentals-broader",
        "make bundle-peers-broader",
        "make detail-prices",
        "make detail-fundamentals",
        "make detail-peers",
        "make detail-prices-broader",
        "make detail-fundamentals-broader",
        "make detail-peers-broader",
        "make runbook-prices",
        "make runbook-fundamentals",
        "make runbook-peers",
        "make runbook-prices-broader",
        "make runbook-fundamentals-broader",
        "make runbook-peers-broader",
        "make focus-price TICKER=AMD",
        "make focus-fundamentals TICKER=NVDA",
        "make focus-peers TICKER=NVDA",
        "make price-worklist",
        "make fundamentals-peer-worklist",
        "make optional-context-worklist",
        "make sec-stage-queue",
        "make peer-mapping-queue",
        "make price-normalize INPUT=data/raw/prices/NVDA.csv TICKER=NVDA SOURCE=yahoo_manual",
        "export SEC_USER_AGENT='Name email@example.com'",
        "make sec-stage TICKERS=NVDA,MSFT",
        "make imports-validate && make imports-preview && make imports-apply",
        "make universe-preview",
    ):
        assert phrase in makefile


def test_readme_front_door_workflows_use_make_based_sec_and_universe_paths():
    readme = Path("README.md").read_text(encoding="utf-8")

    for phrase in (
        'export SEC_USER_AGENT="Your Name your.email@example.com"',
        "make sec-stage TICKERS=NVDA,MSFT",
        "make imports-validate",
        "make imports-preview",
        "make imports-apply",
        "make data-sources-check",
        "make universe-preview",
        "make universe-apply",
        "make price-refresh",
    ):
        assert phrase in readme

    assert "Run a local-only source check:\n\n```bash\nmake data-sources-check" in readme
    assert "Useful flags:\n\n```bash\nmake price-refresh\nmake price-refresh TICKERS=NVDA,MSFT,AVGO" in readme


def test_readme_distinguishes_verify_from_broader_daily_workflow():
    readme = Path("README.md").read_text(encoding="utf-8")

    assert "run deterministic local verification for core outputs, local-data validation, and read-only status artifacts" in readme
    assert "If you also want monthly picks, track record output, and the broader end-to-end refresh path, use `make daily` or `make validate-all`" in readme
    assert "run deterministic local verification for core outputs, diagnostics, monthly layers, and read-only status artifacts" not in readme


def test_readme_safe_data_change_ladders_use_explicit_repo_native_commands():
    readme = Path("README.md").read_text(encoding="utf-8")

    assert "- prices: `data/raw/prices/` -> `make price-normalize` -> `make price-validate` -> `make price-preview` -> `make price-apply`" in readme
    assert "- fundamentals: `export SEC_USER_AGENT=...` -> `make sec-stage ...` -> `make imports-validate` -> `make imports-preview` -> `make imports-apply`" in readme
    assert "- peers/earnings/estimates: fill trusted local CSVs under `data/imports/`, then `make imports-validate` -> `make imports-preview` -> `make imports-apply`" in readme
    assert "- fundamentals: SEC staging -> validate -> preview -> apply" not in readme


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
    assert "make data-sources-check" in script
    assert "make monthly" in script
    assert "make track-record" in script
    assert "make dashboard-smoke" in script
    assert "python3 -m pytest tests -q" not in script
    assert "python3 -m src.data_sources --check" not in script


def test_daily_launcher_reuses_current_make_targets():
    script = Path("scripts/daily.sh").read_text(encoding="utf-8")

    for command in (
        "make price-refresh",
        "make pipeline",
        "make monthly",
        "make track-record",
        "make validate-data",
        "make onboarding",
    ):
        assert command in script

    assert "python3 -m src.data_update --universe-file data/universe.csv" not in script
    assert "python3 -m src.report_generator" not in script


def test_makefile_verify_and_daily_targets_reuse_shared_make_workflows():
    makefile = Path("Makefile").read_text(encoding="utf-8")

    assert "verify:\n\t$(MAKE) test\n\t$(MAKE) pipeline\n\t$(MAKE) validate-data\n\t$(MAKE) onboarding" in makefile
    assert "daily:\n\t$(MAKE) price-refresh\n\t$(MAKE) pipeline\n\t$(MAKE) monthly\n\t$(MAKE) track-record\n\t$(MAKE) validate-data\n\t$(MAKE) onboarding" in makefile
    assert "verify:\n\tpython3 -m pytest tests -q" not in makefile
    assert "daily:\n\tpython3 -m src.data_update --universe-file data/universe.csv" not in makefile
