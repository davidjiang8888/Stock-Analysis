.PHONY: help status test pipeline monthly track-record validate-data research-health action-queue verify validate-all daily dashboard dashboard-smoke sec-stage sec-validate sec-preview sec-apply universe-preview universe-apply coverage data-wizard unlock-ladder unlock-summary command-bundles command-bundle-details command-bundle-runbook bundle-prices bundle-fundamentals bundle-peers runbook-prices runbook-fundamentals runbook-peers onboarding templates price-status price-worklist fundamentals-peer-worklist optional-context-worklist sec-stage-queue peer-mapping-queue price-validate price-preview price-apply price-refresh price-normalize

help:
	@echo "Stock Research Screener convenience commands"
	@echo ""
	@echo "Core:"
	@echo "  make status           Print read-only local project status"
	@echo "  make test             Run unit tests"
	@echo "  make pipeline         Generate core CSV outputs"
	@echo "  make verify           Run deterministic local verification"
	@echo "  make validate-all     Run extended local validation and dashboard smoke check"
	@echo "  make daily            Refresh local workflow outputs end-to-end"
	@echo "  make dashboard        Open the Streamlit dashboard"
	@echo "  make dashboard-smoke  Start dashboard headless and check Streamlit health"
	@echo ""
	@echo "Research outputs:"
	@echo "  make monthly          Generate monthly research candidates"
	@echo "  make track-record     Generate local monthly picks track record"
	@echo "  make research-health  Generate data quality, liquidity, and correlation outputs"
	@echo "  make action-queue     Generate prioritized data/research actions"
	@echo ""
	@echo "Data onboarding:"
	@echo "  make onboarding       Write source status, coverage, and action queue outputs"
	@echo "  make data-wizard      Show prioritized data coverage unlocks"
	@echo "  make unlock-ladder    Show one next-step unlock stage per ticker"
	@echo "  make unlock-summary   Show grouped unlock priorities by holdings, theme, and sector ETF"
	@echo "  make command-bundles Show holdings-first local command bundles for prices, SEC, and peers"
	@echo "  make command-bundle-details Show ticker-level rows for the current local command bundles"
	@echo "  make command-bundle-runbook Show ordered runbook rows for the current local command bundles"
	@echo "  make bundle-prices    Show only the price bundle and its holdings-first scope when available"
	@echo "  make bundle-fundamentals Show only the SEC fundamentals bundle"
	@echo "  make bundle-peers     Show only the peer-mapping bundle"
	@echo "  make runbook-prices   Show only the price bundle runbook"
	@echo "  make runbook-fundamentals Show only the SEC fundamentals runbook"
	@echo "  make runbook-peers    Show only the peer-mapping runbook"
	@echo "  make price-worklist   Show ticker-by-ticker local price-history gaps"
	@echo "  make fundamentals-peer-worklist Show DCF and peer-relative local blockers"
	@echo "  make optional-context-worklist Show optional earnings and estimate gaps"
	@echo "  make sec-stage-queue  Show prioritized SEC fundamentals staging candidates"
	@echo "  make peer-mapping-queue Show prioritized manual peer-mapping candidates"
	@echo "  make templates        Write local CSV templates"
	@echo "  make validate-data    Validate local CSV datasets"
	@echo ""
	@echo "Price fallback:"
	@echo "  make price-refresh    Attempt free remote price refresh with local fallback"
	@echo "  make price-status     Show latest price update status"
	@echo "  make price-normalize INPUT=data/raw/prices/NVDA.csv TICKER=NVDA SOURCE=yahoo_manual"
	@echo "  make price-validate && make price-preview && make price-apply"
	@echo ""
	@echo "Staged fundamentals and universe:"
	@echo "  SEC_USER_AGENT='Name email@example.com' make sec-stage TICKERS=NVDA,MSFT"
	@echo "  make sec-validate && make sec-preview && make sec-apply"
	@echo "  make universe-preview"
	@echo "  make universe-apply"

test:
	python3 -m pytest tests -q

status:
	python3 -m src.project_status

pipeline:
	python3 -m src.report_generator

monthly:
	python3 -m src.monthly_picks --generate --top-n 5

track-record:
	python3 -m src.track_record --monthly-picks

validate-data:
	python3 -m src.stock_report --validate-local-data

research-health:
	python3 -m src.research_health --write-output

action-queue:
	python3 -m src.action_queue --write-output

verify:
	python3 -m pytest tests -q
	python3 -m src.report_generator
	python3 -m src.stock_report --validate-local-data
	python3 -m src.action_queue --write-output

validate-all:
	scripts/validate_all.sh

coverage:
	python3 -m src.data_onboarding --coverage

data-wizard:
	python3 -m src.data_onboarding --wizard

unlock-ladder:
	python3 -m src.data_onboarding --unlock-ladder

unlock-summary:
	python3 -m src.data_onboarding --unlock-summary

command-bundles:
	python3 -m src.data_onboarding --command-bundles

command-bundle-details:
	python3 -m src.data_onboarding --command-bundle-details

command-bundle-runbook:
	python3 -m src.data_onboarding --command-bundle-runbook

bundle-prices:
	python3 -m src.data_onboarding --command-bundles --lane prices --holdings-only

bundle-fundamentals:
	python3 -m src.data_onboarding --command-bundles --lane fundamentals --holdings-only

bundle-peers:
	python3 -m src.data_onboarding --command-bundles --lane peers --holdings-only

runbook-prices:
	python3 -m src.data_onboarding --command-bundle-runbook --lane prices --holdings-only

runbook-fundamentals:
	python3 -m src.data_onboarding --command-bundle-runbook --lane fundamentals --holdings-only

runbook-peers:
	python3 -m src.data_onboarding --command-bundle-runbook --lane peers --holdings-only

onboarding:
	python3 -m src.data_sources --write-output
	python3 -m src.data_onboarding --write-output
	python3 -m src.action_queue --write-output

templates:
	python3 -m src.data_onboarding --write-templates

price-status:
	python3 -m src.data_update --price-status

price-worklist:
	python3 -m src.data_onboarding --price-worklist

fundamentals-peer-worklist:
	python3 -m src.data_onboarding --fundamentals-peer-worklist

optional-context-worklist:
	python3 -m src.data_onboarding --optional-context-worklist

sec-stage-queue:
	python3 -m src.data_onboarding --sec-stage-queue

peer-mapping-queue:
	python3 -m src.data_onboarding --peer-mapping-queue

price-validate:
	python3 -m src.data_update --validate-price-imports

price-preview:
	python3 -m src.data_update --preview-price-import-merge

price-apply:
	python3 -m src.data_update --apply-price-import-merge

price-refresh:
	python3 -m src.data_update --universe-file data/universe.csv

price-normalize:
ifdef TICKER
	python3 -m src.price_import_normalizer --input $(INPUT) --ticker $(TICKER) --source $(or $(SOURCE),generic_manual)
else
	python3 -m src.price_import_normalizer --input $(INPUT) --source $(or $(SOURCE),generic_manual)
endif

daily:
	python3 -m src.data_update --universe-file data/universe.csv
	python3 -m src.report_generator
	python3 -m src.monthly_picks --generate --top-n 5
	python3 -m src.track_record --monthly-picks
	python3 -m src.stock_report --validate-local-data
	python3 -m src.action_queue --write-output

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

universe-preview:
	python3 -m src.universe_builder --preview --preset sp500_smh --max-tickers 50

universe-apply:
	python3 -m src.universe_builder --write-import --preset sp500_smh --max-tickers 50
	python3 -m src.universe_builder --apply-import
