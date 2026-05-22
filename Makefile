.PHONY: help status test pipeline stock-report local-tickers monthly track-record validate-data data-sources-check data-sources research-health action-queue action-queue-check verify validate-all daily dashboard dashboard-smoke sec-stage sec-validate sec-preview sec-apply imports-validate imports-preview imports-apply import-staging universe-preview universe-apply coverage data-wizard unlock-ladder unlock-summary command-bundles command-bundle-details command-bundle-runbook bundle-prices bundle-fundamentals bundle-peers bundle-prices-broader bundle-fundamentals-broader bundle-peers-broader detail-prices detail-fundamentals detail-peers detail-prices-broader detail-fundamentals-broader detail-peers-broader runbook-prices runbook-fundamentals runbook-peers runbook-prices-broader runbook-fundamentals-broader runbook-peers-broader focus-price focus-fundamentals focus-peers onboarding templates price-status price-worklist fundamentals-peer-worklist optional-context-worklist sec-stage-queue peer-mapping-queue price-validate price-preview price-apply price-refresh price-normalize

help:
	@echo "Stock Research Screener convenience commands"
	@echo ""
	@echo "Core:"
	@echo "  make status           Print read-only local project status"
	@echo "  make test             Run unit tests"
	@echo "  make pipeline         Generate core CSV outputs"
	@echo "  make stock-report TICKER=NVDA [OUTPUT=outputs/nvda_stock_report.json] Generate one local stock report JSON"
	@echo "  make local-tickers    List tickers discoverable from local CSV datasets"
	@echo "  make verify           Run deterministic local verification"
	@echo "  make validate-all     Run extended local validation and dashboard smoke check"
	@echo "  make daily            Optional broader end-to-end local workflow refresh"
	@echo "  make dashboard        Open the Streamlit dashboard"
	@echo "  make dashboard-smoke  Start dashboard headless and check Streamlit health"
	@echo "  make data-sources-check Validate local source availability and gap status without rewriting outputs"
	@echo "  make data-sources    Refresh source status and gap report outputs only"
	@echo "  make status now prints the top focus shortcut, top bundle/runbook shortcut, then verify/smoke steps"
	@echo "  Use make status first, then the printed focus/runbook path, then verify/smoke, then dashboard review"
	@echo ""
	@echo "Research outputs:"
	@echo "  make monthly          Generate monthly research candidates"
	@echo "  make track-record     Generate local monthly picks track record"
	@echo "  make research-health  Generate data quality, liquidity, and correlation outputs"
	@echo "  make action-queue-check Print the current read-only action queue summary"
	@echo "  make action-queue     Generate prioritized data/research actions"
	@echo ""
	@echo "Data onboarding:"
	@echo "  make onboarding       Write source status, coverage, research-health, action queue, and project status outputs"
	@echo "  make coverage [TICKERS=NVDA,MSFT] Show ticker-level local data coverage"
	@echo "  make data-wizard [TICKERS=NVDA,MSFT] Show prioritized data coverage unlocks"
	@echo "  make unlock-ladder [TICKERS=NVDA,MSFT] Show one next-step unlock stage per ticker"
	@echo "  make unlock-summary [TICKERS=NVDA,MSFT] Show grouped unlock priorities by holdings, theme, and sector ETF"
	@echo "  make command-bundles [TICKERS=NVDA,MSFT] Show holdings-first local command bundles for prices, SEC, and peers"
	@echo "  make command-bundle-details [TICKERS=NVDA,MSFT] Show ticker-level rows for the current local command bundles"
	@echo "  make command-bundle-runbook [TICKERS=NVDA,MSFT] Show ordered runbook rows for the current local command bundles"
	@echo "  make bundle-prices [TICKERS=NVDA,MSFT] Show only the price bundle and its holdings-first scope when available"
	@echo "  make bundle-fundamentals [TICKERS=NVDA,MSFT] Show only the SEC fundamentals bundle"
	@echo "  make bundle-peers [TICKERS=NVDA,MSFT] Show only the peer-mapping bundle"
	@echo "  make bundle-prices-broader [TICKERS=NVDA,MSFT] Show only the broader-queue price bundle"
	@echo "  make bundle-fundamentals-broader [TICKERS=NVDA,MSFT] Show only the broader-queue SEC fundamentals bundle"
	@echo "  make bundle-peers-broader [TICKERS=NVDA,MSFT] Show only the broader-queue peer-mapping bundle"
	@echo "  make detail-prices [TICKERS=NVDA,MSFT] Show only the price bundle detail rows"
	@echo "  make detail-fundamentals [TICKERS=NVDA,MSFT] Show only the SEC fundamentals detail rows"
	@echo "  make detail-peers [TICKERS=NVDA,MSFT] Show only the peer-mapping detail rows"
	@echo "  make detail-prices-broader [TICKERS=NVDA,MSFT] Show only the broader-queue price detail rows"
	@echo "  make detail-fundamentals-broader [TICKERS=NVDA,MSFT] Show only the broader-queue SEC detail rows"
	@echo "  make detail-peers-broader [TICKERS=NVDA,MSFT] Show only the broader-queue peer detail rows"
	@echo "  make runbook-prices [TICKERS=NVDA,MSFT] Show only the price bundle runbook"
	@echo "  make runbook-fundamentals [TICKERS=NVDA,MSFT] Show only the SEC fundamentals runbook"
	@echo "  make runbook-peers [TICKERS=NVDA,MSFT] Show only the peer-mapping runbook"
	@echo "  make runbook-prices-broader [TICKERS=NVDA,MSFT] Show only the broader-queue price runbook"
	@echo "  make runbook-fundamentals-broader [TICKERS=NVDA,MSFT] Show only the broader-queue SEC runbook"
	@echo "  make runbook-peers-broader [TICKERS=NVDA,MSFT] Show only the broader-queue peer runbook"
	@echo "  make focus-price TICKER=AMD Show one ticker's price detail row and runbook"
	@echo "  make focus-fundamentals TICKER=NVDA Show one ticker's SEC detail row and runbook"
	@echo "  make focus-peers TICKER=NVDA Show one ticker's peer detail row and runbook"
	@echo "  make price-worklist [TICKERS=NVDA,MSFT] Show ticker-by-ticker local price-history gaps"
	@echo "  make fundamentals-peer-worklist [TICKERS=NVDA,MSFT] Show DCF and peer-relative local blockers"
	@echo "  make optional-context-worklist [TICKERS=NVDA,MSFT] Show optional earnings and estimate gaps"
	@echo "  make sec-stage-queue [TICKERS=NVDA,MSFT] Show prioritized SEC fundamentals staging candidates"
	@echo "  make peer-mapping-queue [TICKERS=NVDA,MSFT] Show prioritized manual peer-mapping candidates"
	@echo "  make templates        Write local CSV templates for peers, earnings, estimates, and manual fallbacks"
	@echo "  make import-staging   Write header-only staging CSV files under data/imports"
	@echo "  make validate-data    Validate local CSV datasets"
	@echo ""
	@echo "Price fallback:"
	@echo "  make price-refresh    Attempt free remote price refresh with local fallback"
	@echo "  make price-status     Show latest price update status"
	@echo "  Start with make status, then the printed price focus or runbook path"
	@echo "  make price-normalize INPUT=data/raw/prices/NVDA.csv TICKER=NVDA SOURCE=yahoo_manual"
	@echo "  make price-validate && make price-preview && make price-apply"
	@echo ""
	@echo "Staged fundamentals and universe:"
	@echo "  export SEC_USER_AGENT='Name email@example.com'"
	@echo "  make sec-stage TICKERS=NVDA,MSFT"
	@echo "  make imports-validate && make imports-preview && make imports-apply"
	@echo "  make universe-preview"
	@echo "  make universe-apply"

test:
	python3 -m pytest tests -q

status:
	python3 -m src.project_status --refresh-artifacts

pipeline:
	python3 -m src.report_generator

stock-report:
ifndef TICKER
	$(error TICKER is required, for example: make stock-report TICKER=NVDA)
endif
	python3 -m src.stock_report --ticker $(TICKER) --provider $(if $(PROVIDER),$(PROVIDER),local) $(if $(OUTPUT),--output $(OUTPUT),)

local-tickers:
	python3 -m src.stock_report --list-local-tickers

monthly:
	python3 -m src.monthly_picks --generate --top-n 5

track-record:
	python3 -m src.track_record --monthly-picks

validate-data:
	python3 -m src.stock_report --validate-local-data

data-sources-check:
	python3 -m src.data_sources --check

data-sources:
	python3 -m src.data_sources --write-output

research-health:
	python3 -m src.research_health --write-output

action-queue:
	python3 -m src.action_queue --write-output

action-queue-check:
	python3 -m src.action_queue --check

verify:
	$(MAKE) test
	$(MAKE) pipeline
	$(MAKE) validate-data
	$(MAKE) onboarding

validate-all:
	scripts/validate_all.sh

coverage:
	python3 -m src.data_onboarding --coverage $(if $(TICKERS),--tickers $(TICKERS),)

data-wizard:
	python3 -m src.data_onboarding --wizard $(if $(TICKERS),--tickers $(TICKERS),)

unlock-ladder:
	python3 -m src.data_onboarding --unlock-ladder $(if $(TICKERS),--tickers $(TICKERS),)

unlock-summary:
	python3 -m src.data_onboarding --unlock-summary $(if $(TICKERS),--tickers $(TICKERS),)

command-bundles:
	python3 -m src.data_onboarding --command-bundles $(if $(TICKERS),--tickers $(TICKERS),)

command-bundle-details:
	python3 -m src.data_onboarding --command-bundle-details $(if $(TICKERS),--tickers $(TICKERS),)

command-bundle-runbook:
	python3 -m src.data_onboarding --command-bundle-runbook $(if $(TICKERS),--tickers $(TICKERS),)

bundle-prices:
	python3 -m src.data_onboarding --command-bundles --lane prices --holdings-only $(if $(TICKERS),--tickers $(TICKERS),)

bundle-fundamentals:
	python3 -m src.data_onboarding --command-bundles --lane fundamentals --holdings-only $(if $(TICKERS),--tickers $(TICKERS),)

bundle-peers:
	python3 -m src.data_onboarding --command-bundles --lane peers --holdings-only $(if $(TICKERS),--tickers $(TICKERS),)

bundle-prices-broader:
	python3 -m src.data_onboarding --command-bundles --lane prices --scope broader_queue $(if $(TICKERS),--tickers $(TICKERS),)

bundle-fundamentals-broader:
	python3 -m src.data_onboarding --command-bundles --lane fundamentals --scope broader_queue $(if $(TICKERS),--tickers $(TICKERS),)

bundle-peers-broader:
	python3 -m src.data_onboarding --command-bundles --lane peers --scope broader_queue $(if $(TICKERS),--tickers $(TICKERS),)

detail-prices:
	python3 -m src.data_onboarding --command-bundle-details --lane prices --holdings-only $(if $(TICKERS),--tickers $(TICKERS),)

detail-fundamentals:
	python3 -m src.data_onboarding --command-bundle-details --lane fundamentals --holdings-only $(if $(TICKERS),--tickers $(TICKERS),)

detail-peers:
	python3 -m src.data_onboarding --command-bundle-details --lane peers --holdings-only $(if $(TICKERS),--tickers $(TICKERS),)

detail-prices-broader:
	python3 -m src.data_onboarding --command-bundle-details --lane prices --scope broader_queue $(if $(TICKERS),--tickers $(TICKERS),)

detail-fundamentals-broader:
	python3 -m src.data_onboarding --command-bundle-details --lane fundamentals --scope broader_queue $(if $(TICKERS),--tickers $(TICKERS),)

detail-peers-broader:
	python3 -m src.data_onboarding --command-bundle-details --lane peers --scope broader_queue $(if $(TICKERS),--tickers $(TICKERS),)

runbook-prices:
	python3 -m src.data_onboarding --command-bundle-runbook --lane prices --holdings-only $(if $(TICKERS),--tickers $(TICKERS),)

runbook-fundamentals:
	python3 -m src.data_onboarding --command-bundle-runbook --lane fundamentals --holdings-only $(if $(TICKERS),--tickers $(TICKERS),)

runbook-peers:
	python3 -m src.data_onboarding --command-bundle-runbook --lane peers --holdings-only $(if $(TICKERS),--tickers $(TICKERS),)

runbook-prices-broader:
	python3 -m src.data_onboarding --command-bundle-runbook --lane prices --scope broader_queue $(if $(TICKERS),--tickers $(TICKERS),)

runbook-fundamentals-broader:
	python3 -m src.data_onboarding --command-bundle-runbook --lane fundamentals --scope broader_queue $(if $(TICKERS),--tickers $(TICKERS),)

runbook-peers-broader:
	python3 -m src.data_onboarding --command-bundle-runbook --lane peers --scope broader_queue $(if $(TICKERS),--tickers $(TICKERS),)

focus-price:
ifndef TICKER
	$(error TICKER is required, for example: make focus-price TICKER=AMD)
endif
	python3 -m src.data_onboarding --command-bundle-details --lane prices --tickers $(TICKER)
	python3 -m src.data_onboarding --command-bundle-runbook --lane prices --tickers $(TICKER)

focus-fundamentals:
ifndef TICKER
	$(error TICKER is required, for example: make focus-fundamentals TICKER=NVDA)
endif
	python3 -m src.data_onboarding --command-bundle-details --lane fundamentals --tickers $(TICKER)
	python3 -m src.data_onboarding --command-bundle-runbook --lane fundamentals --tickers $(TICKER)

focus-peers:
ifndef TICKER
	$(error TICKER is required, for example: make focus-peers TICKER=NVDA)
endif
	python3 -m src.data_onboarding --command-bundle-details --lane peers --tickers $(TICKER)
	python3 -m src.data_onboarding --command-bundle-runbook --lane peers --tickers $(TICKER)

onboarding:
	python3 -m src.data_sources --write-output
	python3 -m src.data_onboarding --write-output
	python3 -m src.research_health --write-output
	python3 -m src.action_queue --write-output
	python3 -m src.project_status --write-output

templates:
	python3 -m src.data_onboarding --write-templates

import-staging:
	python3 -m src.stock_report --write-import-staging

price-status:
	python3 -m src.data_update --price-status

price-worklist:
	python3 -m src.data_onboarding --price-worklist $(if $(TICKERS),--tickers $(TICKERS),)

fundamentals-peer-worklist:
	python3 -m src.data_onboarding --fundamentals-peer-worklist $(if $(TICKERS),--tickers $(TICKERS),)

optional-context-worklist:
	python3 -m src.data_onboarding --optional-context-worklist $(if $(TICKERS),--tickers $(TICKERS),)

sec-stage-queue:
	python3 -m src.data_onboarding --sec-stage-queue $(if $(TICKERS),--tickers $(TICKERS),)

peer-mapping-queue:
	python3 -m src.data_onboarding --peer-mapping-queue $(if $(TICKERS),--tickers $(TICKERS),)

price-validate:
	python3 -m src.data_update --validate-price-imports

price-preview:
	python3 -m src.data_update --preview-price-import-merge

price-apply:
	python3 -m src.data_update --apply-price-import-merge

price-refresh:
ifdef TICKERS
	python3 -m src.data_update --tickers $(TICKERS)
else
	python3 -m src.data_update --universe-file data/universe.csv
endif

price-normalize:
ifndef INPUT
	$(error INPUT is required, for example: make price-normalize INPUT=data/raw/prices/NVDA.csv TICKER=NVDA SOURCE=yahoo_manual)
endif
ifdef TICKER
	python3 -m src.price_import_normalizer --input $(INPUT) --ticker $(TICKER) --source $(or $(SOURCE),generic_manual)
else
	python3 -m src.price_import_normalizer --input $(INPUT) --source $(or $(SOURCE),generic_manual)
endif

daily:
	$(MAKE) price-refresh
	$(MAKE) pipeline
	$(MAKE) monthly
	$(MAKE) track-record
	$(MAKE) validate-data
	$(MAKE) onboarding
	python3 -m src.action_queue --write-output
	python3 -m src.project_status --write-output

dashboard:
	streamlit run src/dashboard.py

dashboard-smoke:
	scripts/smoke_dashboard.sh

sec-stage:
ifdef TICKERS
	python3 -m src.stock_report --sec-stage-fundamentals --tickers $(TICKERS)
else
	python3 -m src.stock_report --sec-stage-fundamentals --from-local-tickers
endif

sec-validate:
	python3 -m src.stock_report --validate-imports

sec-preview:
	python3 -m src.stock_report --preview-import-merge

sec-apply:
	python3 -m src.stock_report --apply-import-merge

imports-validate:
	python3 -m src.stock_report --validate-imports

imports-preview:
	python3 -m src.stock_report --preview-import-merge

imports-apply:
	python3 -m src.stock_report --apply-import-merge

universe-preview:
	python3 -m src.universe_builder --preview --preset sp500_smh --max-tickers 50

universe-apply:
	python3 -m src.universe_builder --write-import --preset sp500_smh --max-tickers 50
	python3 -m src.universe_builder --apply-import
