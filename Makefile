.PHONY: test pipeline monthly track-record validate-data research-health action-queue daily dashboard sec-stage sec-validate sec-preview sec-apply universe-preview universe-apply coverage onboarding templates price-status price-validate price-preview price-apply price-refresh price-normalize

test:
	python3 -m pytest tests -q

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

coverage:
	python3 -m src.data_onboarding --coverage

onboarding:
	python3 -m src.data_sources --write-output
	python3 -m src.data_onboarding --write-output
	python3 -m src.action_queue --write-output

templates:
	python3 -m src.data_onboarding --write-templates

price-status:
	python3 -m src.data_update --price-status

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
