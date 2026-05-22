from pathlib import Path


def test_makefile_contains_convenience_targets():
    makefile = Path("Makefile").read_text(encoding="utf-8")

    for target in (
        "help",
        "status",
        "test",
        "pipeline",
        "stock-report",
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
        "make stock-report TICKER=NVDA [OUTPUT=outputs/nvda_stock_report.json]",
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

    assert "- Use `make pipeline` to generate the core local outputs." in readme
    assert "- Use `make dashboard` to run the dashboard." in readme
    assert "## Run the pipeline\n\nGenerate all active outputs:\n\n```bash\nmake pipeline" in readme
    assert "Use the repo-native front door to generate a structured local stock report:\n\n```bash\nmake stock-report TICKER=NVDA" in readme
    assert "If you want to write JSON to a file through the same front door:\n\n```bash\nmake stock-report TICKER=NVDA OUTPUT=outputs/nvda_stock_report.json" in readme
    for phrase in (
        'export SEC_USER_AGENT="Your Name your.email@example.com"',
        "make sec-stage TICKERS=NVDA,MSFT",
        "make imports-validate",
        "make imports-preview",
        "make imports-apply",
        "make data-sources-check",
        "make coverage",
        "make data-wizard",
        "make unlock-ladder",
        "make unlock-summary",
        "make command-bundles",
        "make command-bundle-details",
        "make command-bundle-runbook",
        "make templates",
        "make onboarding",
        "make universe-preview",
        "make universe-apply",
        "make price-refresh",
    ):
        assert phrase in readme

    assert "Run a local-only source check:\n\n```bash\nmake data-sources-check" in readme
    assert "If you intentionally want lower-level CLI control against a fixture or alternate local dataset, the raw module commands remain available:\n\n```bash\npython3 -m src.stock_report --project-root \"/Users/yjian070/Documents/New project\" --validate-local-data" in readme
    assert "```bash\nmake validate-data\nmake pipeline\nmake monthly" in readme
    assert "## Run the dashboard\n\n```bash\nmake dashboard" in readme
    assert "```bash\nmake coverage\nmake data-wizard\nmake command-bundles\nmake templates" in readme
    assert "Generate it with:\n\n```bash\nmake status\nmake data-wizard" in readme
    assert "If you want one row per ticker instead of several queue outputs, use:\n\n```bash\nmake unlock-ladder" in readme
    assert "If you want to see where local data gaps are most concentrated by holdings, theme, or sector ETF, use:\n\n```bash\nmake unlock-summary" in readme
    assert "```bash\nmake command-bundles\nmake command-bundle-details\nmake command-bundle-runbook" in readme
    assert "If you only want one lane at a time, use:\n\n```bash\nmake bundle-prices\nmake bundle-fundamentals\nmake bundle-peers" in readme
    assert "make runbook-prices\nmake runbook-fundamentals\nmake runbook-peers" in readme
    assert "If you want the broader queue explicitly instead of the holdings-first slice, use the same bundle views with `--scope broader_queue`, or the matching Make shortcuts:\n\n```bash\nmake bundle-prices-broader\nmake detail-prices-broader\nmake runbook-prices-broader" in readme
    assert "To validate your local CSV datasets and see schema/freshness warnings:\n\n```bash\nmake validate-data" in readme
    assert "If you explicitly want machine-readable validation output:\n\n```bash\npython -m src.stock_report --validate-local-data --json" in readme
    assert "If you intentionally want lower-level CLI control for ticker discovery, provider selection, or direct JSON output, the raw module commands remain available:\n\n```bash\npython -m src.stock_report --list-local-tickers" in readme
    assert "To scaffold header-only local enrichment templates without fabricating any production data:\n\n```bash\nmake templates" in readme
    assert "make imports-validate" in readme
    assert "make imports-preview" in readme
    assert "make imports-apply" in readme
    assert "make onboarding" in readme
    assert "Validate staged files without mutating canonical data:\n\n```bash\nmake imports-validate" in readme
    assert "Preview what would change:\n\n```bash\nmake imports-preview" in readme
    assert "Apply the merge safely:\n\n```bash\nmake imports-apply" in readme
    assert "If you want to refresh `data/prices.csv` from a free daily source before running the screener, you can use:\n\n```bash\nmake price-refresh" in readme
    assert "Useful flags:\n\n```bash\nmake price-refresh\nmake price-refresh TICKERS=NVDA,MSFT,AVGO" in readme
    assert "If you want a larger CLI-only smoke run:\n\n```bash\nmake universe-preview\nmake universe-apply" in readme
    assert "python3 -m src.universe_builder --preview --preset sp500_smh --max-tickers 50" not in readme
    assert "If you want to enrich canonical local fundamentals safely, use the staged SEC + import flow:\n\n```bash\nexport SEC_USER_AGENT=\"Your Name your.email@example.com\"\nmake sec-stage TICKERS=NVDA,MSFT\nmake imports-validate\nmake imports-preview\nmake imports-apply\nmake validate-data" in readme
    assert "make imports-apply\nmake validate-data\nmake stock-report TICKER=NVDA OUTPUT=outputs/nvda_stock_report.json" in readme
    assert "If the current blocker path is already satisfied and you want the monthly layer directly, use:\n\n```bash\nmake monthly" in readme
    assert "The local track-record module uses only local historical prices:\n\n```bash\nmake track-record" in readme


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

    assert "stock-report:\nifndef TICKER\n\t$(error TICKER is required, for example: make stock-report TICKER=NVDA)\nendif\n\tpython3 -m src.stock_report --ticker $(TICKER) --provider $(if $(PROVIDER),$(PROVIDER),local) $(if $(OUTPUT),--output $(OUTPUT),)" in makefile
    assert "verify:\n\t$(MAKE) test\n\t$(MAKE) pipeline\n\t$(MAKE) validate-data\n\t$(MAKE) onboarding" in makefile
    assert "daily:\n\t$(MAKE) price-refresh\n\t$(MAKE) pipeline\n\t$(MAKE) monthly\n\t$(MAKE) track-record\n\t$(MAKE) validate-data\n\t$(MAKE) onboarding" in makefile
    assert "verify:\n\tpython3 -m pytest tests -q" not in makefile
    assert "daily:\n\tpython3 -m src.data_update --universe-file data/universe.csv" not in makefile
