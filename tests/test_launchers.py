from pathlib import Path


def test_makefile_contains_convenience_targets():
    makefile = Path("Makefile").read_text(encoding="utf-8")

    for target in (
        "help",
        "status",
        "status-check",
        "test",
        "pipeline",
        "stock-report",
        "local-tickers",
        "monthly",
        "track-record",
        "validate-data",
        "data-sources-check",
        "data-sources",
        "research-health-check",
        "research-health",
        "action-queue-check",
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
        "import-staging",
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
        "make status [TOP_N=5]",
        "make status-check [TOP_N=5]",
        "make verify",
        "make validate-all",
        "make daily",
        "make dashboard-smoke",
        "make data-sources-check [TOP_N=10]",
        "make data-sources",
        "make research-health-check [TOP_N=10]",
        "make action-queue-check [TOP_N=10]",
        "make stock-report TICKER=NVDA [OUTPUT=outputs/nvda_stock_report.json]",
        "make local-tickers",
        "make coverage [TICKERS=NVDA,MSFT]",
        "make data-wizard [TICKERS=NVDA,MSFT]",
        "make unlock-ladder [TICKERS=NVDA,MSFT]",
        "make unlock-summary [TICKERS=NVDA,MSFT]",
        "make command-bundles [TICKERS=NVDA,MSFT]",
        "make command-bundle-details [TICKERS=NVDA,MSFT]",
        "make command-bundle-runbook [TICKERS=NVDA,MSFT]",
        "make bundle-prices [TICKERS=NVDA,MSFT]",
        "make bundle-fundamentals [TICKERS=NVDA,MSFT]",
        "make bundle-peers [TICKERS=NVDA,MSFT]",
        "make bundle-prices-broader [TICKERS=NVDA,MSFT]",
        "make bundle-fundamentals-broader [TICKERS=NVDA,MSFT]",
        "make bundle-peers-broader [TICKERS=NVDA,MSFT]",
        "make detail-prices [TICKERS=NVDA,MSFT]",
        "make detail-fundamentals [TICKERS=NVDA,MSFT]",
        "make detail-peers [TICKERS=NVDA,MSFT]",
        "make detail-prices-broader [TICKERS=NVDA,MSFT]",
        "make detail-fundamentals-broader [TICKERS=NVDA,MSFT]",
        "make detail-peers-broader [TICKERS=NVDA,MSFT]",
        "make runbook-prices [TICKERS=NVDA,MSFT]",
        "make runbook-fundamentals [TICKERS=NVDA,MSFT]",
        "make runbook-peers [TICKERS=NVDA,MSFT]",
        "make runbook-prices-broader [TICKERS=NVDA,MSFT]",
        "make runbook-fundamentals-broader [TICKERS=NVDA,MSFT]",
        "make runbook-peers-broader [TICKERS=NVDA,MSFT]",
        "make focus-price TICKER=AMD",
        "make focus-fundamentals TICKER=NVDA",
        "make focus-peers TICKER=NVDA",
        "make price-status [TICKERS=NVDA,MSFT] [TOP_N=10]",
        "make price-worklist [TICKERS=NVDA,MSFT]",
        "make fundamentals-peer-worklist [TICKERS=NVDA,MSFT]",
        "make optional-context-worklist [TICKERS=NVDA,MSFT]",
        "make sec-stage-queue [TICKERS=NVDA,MSFT]",
        "make peer-mapping-queue [TICKERS=NVDA,MSFT]",
        "Most read-only onboarding views also accept TOP_N=10 for a shorter terminal summary",
        "make import-staging",
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
    assert "Use `make status` first when you want the read-only local project snapshot plus a refresh of the supporting operator artifacts, or `make status-check` when you only want the current summary without that refresh step. Both status paths accept `TOP_N=...` if you want a shorter terminal snapshot." in readme
    assert "Use the repo-native front door to generate a structured local stock report:\n\n```bash\nmake stock-report TICKER=NVDA" in readme
    assert "If you want to write JSON to a file through the same front door:\n\n```bash\nmake stock-report TICKER=NVDA OUTPUT=outputs/nvda_stock_report.json" in readme
    assert "To discover locally available tickers first:\n\n```bash\nmake local-tickers" in readme
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
    assert "make data-sources" in readme
    assert "If you want a shorter source and gap summary in the terminal, use `make data-sources-check TOP_N=10`." in readme
    assert "If you intentionally want lower-level CLI control against a fixture or alternate local dataset, the raw module commands remain available:\n\n```bash\npython3 -m src.stock_report --project-root \"/Users/yjian070/Documents/New project\" --validate-local-data" in readme
    assert "```bash\nmake validate-data\nmake pipeline\nmake monthly" in readme
    assert "## Run the dashboard\n\n```bash\nmake dashboard" in readme
    assert "```bash\nmake coverage\nmake data-wizard\nmake command-bundles\nmake templates" in readme
    assert "If you want a narrower targeted coverage pass without leaving the make-based operator path, use:\n\n```bash\nmake coverage TICKERS=NVDA,MSFT,AMD,AVGO\nmake data-wizard TICKERS=NVDA,MSFT,AMD,AVGO" in readme
    assert "If you want either read-only onboarding view to stay shorter in the terminal, add `TOP_N=...`, for example:\n\n```bash\nmake coverage TOP_N=5\nmake data-wizard TICKERS=NVDA,MSFT,AMD,AVGO TOP_N=5" in readme
    assert "Generate it with:\n\n```bash\nmake status\nmake data-wizard" in readme
    assert "Most of the read-only onboarding views also accept `TOP_N=...` when you want a shorter terminal summary without changing the underlying CSV outputs or JSON payloads." in readme
    assert "If you want one row per ticker instead of several queue outputs, use:\n\n```bash\nmake unlock-ladder" in readme
    assert "To narrow that unlock ladder to a specific local ticker slice without leaving the make-based operator path, use:\n\n```bash\nmake unlock-ladder TICKERS=NVDA,MSFT" in readme
    assert "To keep that one-row-per-ticker ladder shorter in the terminal, add `TOP_N=...`, for example `make unlock-ladder TOP_N=5`." in readme
    assert "If you want to see where local data gaps are most concentrated by holdings, theme, or sector ETF, use:\n\n```bash\nmake unlock-summary" in readme
    assert "To focus that grouped unlock summary on a smaller local ticker slice, use:\n\n```bash\nmake unlock-summary TICKERS=NVDA,MSFT" in readme
    assert "You can also cap the grouped summary with `make unlock-summary TOP_N=5` when you only want the first few holdings/theme/sector rows." in readme
    assert "```bash\nmake command-bundles\nmake command-bundle-details\nmake command-bundle-runbook" in readme
    assert "If you want to narrow those bundle views to a specific local ticker slice without leaving the make-based operator path, use:\n\n```bash\nmake command-bundles TICKERS=NVDA,MSFT\nmake command-bundle-details TICKERS=NVDA,MSFT\nmake command-bundle-runbook TICKERS=NVDA,MSFT" in readme
    assert "Those bundle views also accept `TOP_N=...`, so you can use `make command-bundles TOP_N=3` or `make command-bundle-runbook TICKERS=NVDA,MSFT TOP_N=6` when you want a shorter read-only pass." in readme
    assert "If you only want one lane at a time, use:\n\n```bash\nmake bundle-prices\nmake bundle-fundamentals\nmake bundle-peers" in readme
    assert "To narrow one of those lane-specific views to a smaller local ticker slice, use:\n\n```bash\nmake bundle-fundamentals TICKERS=NVDA,MSFT\nmake detail-peers TICKERS=NVDA,MSFT\nmake runbook-prices TICKERS=NVDA,MSFT" in readme
    assert "make runbook-prices\nmake runbook-fundamentals\nmake runbook-peers" in readme
    assert "If you want the broader queue explicitly instead of the holdings-first slice, use the same bundle views with `--scope broader_queue`, or the matching Make shortcuts:\n\n```bash\nmake bundle-prices-broader\nmake detail-prices-broader\nmake runbook-prices-broader" in readme
    assert "The same `-broader` pattern is available for `fundamentals` and `peers`, and those broader queue lane views also accept `TICKERS=...`" in readme
    assert "To validate your local CSV datasets and see schema/freshness warnings:\n\n```bash\nmake validate-data" in readme
    assert "If you explicitly want machine-readable validation output:\n\n```bash\npython -m src.stock_report --validate-local-data --json" in readme
    assert "If you intentionally want lower-level CLI control for provider selection or direct JSON output, the raw module commands remain available:\n\n```bash\npython -m src.stock_report --ticker AAPL --provider mock" in readme
    assert "To scaffold header-only local enrichment templates without fabricating any production data:\n\n```bash\nmake templates" in readme
    assert "To scaffold header-only staging files directly under `data/imports/`:\n\n```bash\nmake import-staging" in readme
    assert "make imports-validate" in readme
    assert "make imports-preview" in readme
    assert "make imports-apply" in readme
    assert "make onboarding" in readme
    assert "Validate staged files without mutating canonical data:\n\n```bash\nmake imports-validate" in readme
    assert "Preview what would change:\n\n```bash\nmake imports-preview" in readme
    assert "Apply the merge safely:\n\n```bash\nmake imports-apply" in readme
    assert "If you want to refresh `data/prices.csv` from a free daily source before running the screener, you can use:\n\n```bash\nmake price-refresh" in readme
    assert "Useful flags:\n\n```bash\nmake price-refresh\nmake price-refresh TICKERS=NVDA,MSFT,AVGO" in readme
    assert "If you want to narrow that pass to a specific local ticker slice without leaving the make-based operator path, use:\n\n```bash\nmake price-worklist TICKERS=NVDA,MSFT" in readme
    assert "Use `make price-status` for the current read-only diagnostics view, `make price-status TOP_N=10` when you want a shorter terminal summary of the latest fallback rows, or `make price-status TICKERS=AMD,AVGO` when you want to inspect only a smaller local ticker slice." in readme
    assert "To keep that price gap list shorter in the terminal, add `TOP_N=...`, for example `make price-worklist TOP_N=5`." in readme
    assert "If you want to narrow those blocker queues to a specific local ticker slice, use:\n\n```bash\nmake fundamentals-peer-worklist TICKERS=NVDA,MSFT\nmake sec-stage-queue TICKERS=NVDA,MSFT\nmake peer-mapping-queue TICKERS=NVDA,MSFT" in readme
    assert "Those read-only blocker views also accept `TOP_N=...`, for example `make fundamentals-peer-worklist TOP_N=5` or `make sec-stage-queue TICKERS=NVDA,MSFT TOP_N=5`." in readme
    assert "To focus that optional-context pass on a smaller local ticker slice, use:\n\n```bash\nmake optional-context-worklist TICKERS=NVDA,MSFT" in readme
    assert "You can also keep that optional-context summary shorter with `make optional-context-worklist TOP_N=5`." in readme
    assert "Generic OHLCV CSVs are also supported when they include `date`, `ticker`, `open`, `high`, `low`, `close`, and `volume` columns:\n\n```bash\nmake price-normalize INPUT=data/raw/prices/prices.csv SOURCE=generic_manual" in readme
    assert "If you explicitly need lower-level CLI control for unusual exports, map columns directly:" in readme
    assert "If you want a larger CLI-only smoke run:\n\n```bash\nmake universe-preview\nmake universe-apply" in readme
    assert "python3 -m src.universe_builder --preview --preset sp500_smh --max-tickers 50" not in readme
    assert "If you want to enrich canonical local fundamentals safely, use the staged SEC + import flow:\n\n```bash\nexport SEC_USER_AGENT=\"Your Name your.email@example.com\"\nmake sec-stage TICKERS=NVDA,MSFT\nmake imports-validate\nmake imports-preview\nmake imports-apply\nmake validate-data" in readme
    assert "make imports-apply\nmake validate-data\nmake stock-report TICKER=NVDA OUTPUT=outputs/nvda_stock_report.json" in readme
    assert "### SEC staging example\n\n```bash\nexport SEC_USER_AGENT=\"Your Name your.email@example.com\"\nmake sec-stage TICKERS=NVDA,MSFT\nmake imports-validate\nmake imports-preview\nmake imports-apply\nmake validate-data\nmake stock-report TICKER=NVDA OUTPUT=outputs/nvda_stock_report.json" in readme
    assert "If the current blocker path is already satisfied and you want the monthly layer directly, use:\n\n```bash\nmake monthly" in readme
    assert "The local track-record module uses only local historical prices:\n\n```bash\nmake track-record" in readme
    assert "If you want the current project-status summary without first refreshing those supporting artifacts, use:\n\n```bash\nmake status-check" in readme
    assert "To keep either status view shorter in the terminal, add `TOP_N=...`, for example:\n\n```bash\nmake status-check TOP_N=2" in readme
    assert "Generate them through the normal workflow or directly:\n\n```bash\nmake status\nmake verify\nmake research-health-check\nmake research-health" in readme
    assert "If you want a shorter diagnostics view in the terminal, use `make research-health-check TOP_N=10`." in readme
    assert "Generate it with:\n\n```bash\nmake status\nmake action-queue-check\nmake action-queue" in readme
    assert "If you want a shorter triage view in the terminal, use `make action-queue-check TOP_N=10`." in readme


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

    assert "status:\n\tpython3 -m src.project_status --refresh-artifacts --top-n $(or $(TOP_N),5)" in makefile
    assert "status-check:\n\tpython3 -m src.project_status --top-n $(or $(TOP_N),5)" in makefile
    assert "coverage:\n\tpython3 -m src.data_onboarding --coverage $(if $(TOP_N),--top-n $(TOP_N),) $(if $(TICKERS),--tickers $(TICKERS),)" in makefile
    assert "data-wizard:\n\tpython3 -m src.data_onboarding --wizard $(if $(TOP_N),--top-n $(TOP_N),) $(if $(TICKERS),--tickers $(TICKERS),)" in makefile
    assert "unlock-ladder:\n\tpython3 -m src.data_onboarding --unlock-ladder $(if $(TOP_N),--top-n $(TOP_N),) $(if $(TICKERS),--tickers $(TICKERS),)" in makefile
    assert "unlock-summary:\n\tpython3 -m src.data_onboarding --unlock-summary $(if $(TOP_N),--top-n $(TOP_N),) $(if $(TICKERS),--tickers $(TICKERS),)" in makefile
    assert "command-bundles:\n\tpython3 -m src.data_onboarding --command-bundles $(if $(TOP_N),--top-n $(TOP_N),) $(if $(TICKERS),--tickers $(TICKERS),)" in makefile
    assert "command-bundle-details:\n\tpython3 -m src.data_onboarding --command-bundle-details $(if $(TOP_N),--top-n $(TOP_N),) $(if $(TICKERS),--tickers $(TICKERS),)" in makefile
    assert "command-bundle-runbook:\n\tpython3 -m src.data_onboarding --command-bundle-runbook $(if $(TOP_N),--top-n $(TOP_N),) $(if $(TICKERS),--tickers $(TICKERS),)" in makefile
    assert "bundle-fundamentals:\n\tpython3 -m src.data_onboarding --command-bundles --lane fundamentals --holdings-only $(if $(TOP_N),--top-n $(TOP_N),) $(if $(TICKERS),--tickers $(TICKERS),)" in makefile
    assert "detail-peers:\n\tpython3 -m src.data_onboarding --command-bundle-details --lane peers --holdings-only $(if $(TOP_N),--top-n $(TOP_N),) $(if $(TICKERS),--tickers $(TICKERS),)" in makefile
    assert "runbook-prices-broader:\n\tpython3 -m src.data_onboarding --command-bundle-runbook --lane prices --scope broader_queue $(if $(TOP_N),--top-n $(TOP_N),) $(if $(TICKERS),--tickers $(TICKERS),)" in makefile
    assert "price-worklist:\n\tpython3 -m src.data_onboarding --price-worklist $(if $(TOP_N),--top-n $(TOP_N),) $(if $(TICKERS),--tickers $(TICKERS),)" in makefile
    assert "fundamentals-peer-worklist:\n\tpython3 -m src.data_onboarding --fundamentals-peer-worklist $(if $(TOP_N),--top-n $(TOP_N),) $(if $(TICKERS),--tickers $(TICKERS),)" in makefile
    assert "optional-context-worklist:\n\tpython3 -m src.data_onboarding --optional-context-worklist $(if $(TOP_N),--top-n $(TOP_N),) $(if $(TICKERS),--tickers $(TICKERS),)" in makefile
    assert "sec-stage-queue:\n\tpython3 -m src.data_onboarding --sec-stage-queue $(if $(TOP_N),--top-n $(TOP_N),) $(if $(TICKERS),--tickers $(TICKERS),)" in makefile
    assert "peer-mapping-queue:\n\tpython3 -m src.data_onboarding --peer-mapping-queue $(if $(TOP_N),--top-n $(TOP_N),) $(if $(TICKERS),--tickers $(TICKERS),)" in makefile
    assert "price-normalize:\nifndef INPUT\n\t$(error INPUT is required, for example: make price-normalize INPUT=data/raw/prices/NVDA.csv TICKER=NVDA SOURCE=yahoo_manual)\nendif" in makefile
    assert "stock-report:\nifndef TICKER\n\t$(error TICKER is required, for example: make stock-report TICKER=NVDA)\nendif\n\tpython3 -m src.stock_report --ticker $(TICKER) --provider $(if $(PROVIDER),$(PROVIDER),local) $(if $(OUTPUT),--output $(OUTPUT),)" in makefile
    assert "local-tickers:\n\tpython3 -m src.stock_report --list-local-tickers" in makefile
    assert "import-staging:\n\tpython3 -m src.stock_report --write-import-staging" in makefile
    assert "data-sources-check:\n\tpython3 -m src.data_sources --check --top-n $(or $(TOP_N),20)" in makefile
    assert "data-sources:\n\tpython3 -m src.data_sources --write-output" in makefile
    assert "research-health-check:\n\tpython3 -m src.research_health --top-n $(or $(TOP_N),20)" in makefile
    assert "action-queue-check:\n\tpython3 -m src.action_queue --check --top-n $(or $(TOP_N),20)" in makefile
    assert "price-status:\n\tpython3 -m src.data_update --price-status $(if $(TOP_N),--top-n $(TOP_N),) $(if $(TICKERS),--tickers $(TICKERS),)" in makefile
    assert "verify:\n\t$(MAKE) test\n\t$(MAKE) pipeline\n\t$(MAKE) validate-data\n\t$(MAKE) onboarding" in makefile
    assert "daily:\n\t$(MAKE) price-refresh\n\t$(MAKE) pipeline\n\t$(MAKE) monthly\n\t$(MAKE) track-record\n\t$(MAKE) validate-data\n\t$(MAKE) onboarding" in makefile
    assert "verify:\n\tpython3 -m pytest tests -q" not in makefile
    assert "daily:\n\tpython3 -m src.data_update --universe-file data/universe.csv" not in makefile
