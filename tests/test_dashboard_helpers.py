from pathlib import Path

import src.dashboard as dashboard
import pandas as pd


def test_dashboard_format_helpers_hide_raw_missing_values():
    assert dashboard.format_missing(None) == "Not available"
    assert dashboard.format_missing(float("nan")) == "Not available"
    assert dashboard.format_percent(None) == "Not enough history"
    assert dashboard.format_date_short("2026-03-14T00:00:00") == "2026-03-14"
    assert "nan" not in dashboard.score_badge(None).lower()
    cleaned = dashboard.clean_display_frame(pd.DataFrame({"Ready": [True, False]}))
    assert cleaned.iloc[0]["Ready"] == "Yes"
    assert cleaned.iloc[1]["Ready"] == "No"


def test_dashboard_badges_use_high_contrast_html():
    html = dashboard.status_badge("Watch")
    assert "background" in html
    assert "color" in html
    assert "Watch" in html


def test_dashboard_card_helpers_render_modern_markup():
    metric = dashboard.metric_card_html("Universe", 12, "local tickers")
    action = dashboard.action_card_html("Price fallback", "Normalize downloaded CSVs", "make price-normalize", "warning")
    notice = dashboard.notice_card_html("Missing output", "Run the pipeline to regenerate local CSV outputs.", "make pipeline")

    assert "metric-card" in metric
    assert "Universe" in metric
    assert "action-card warning" in action
    assert "make price-normalize" in action
    assert "notice-card" in notice
    assert "make pipeline" in notice


def test_notice_card_escapes_content_and_uses_tones():
    html = dashboard.notice_card_html("<Missing>", "Use <safe> local files.", "make pipeline", tone="warning")

    assert "&lt;Missing&gt;" in html
    assert "&lt;safe&gt;" in html
    assert "notice-card warning" in html


def test_state_styles_include_text_color_for_dark_mode():
    styled = dashboard.style_frame(pd.DataFrame({"FinalState": ["Avoid"]}))._compute()
    css_values = [item for styles in styled.ctx.values() for item in styles]

    assert ("color", "#991b1b") in css_values
    assert ("font-weight", "700") in css_values


def test_missing_data_notice_translates_common_gaps():
    html = dashboard.missing_data_notice("fundamentals unavailable, peers")
    assert "Needs SEC enrichment" in html
    assert "Needs peers.csv" in html


def test_missing_data_summary_limits_noisy_fields():
    text = dashboard.summarize_missing_fields("Return1M, Return3M, Return6M, EPSGrowth, FCFMargin, ForwardPE", max_items=3)

    assert "Not enough price history" in text
    assert "+1 more" in text


def test_monthly_pick_availability_message_handles_less_than_top_n():
    message = dashboard.monthly_pick_availability_message(4, 5)

    assert "4 of 5" in message
    assert "not forced" in message


def test_track_record_status_message_explains_insufficient_history():
    message = dashboard.track_record_status_message(None, None)

    assert "Insufficient local history" in message
    assert "forward returns" in message


def test_compact_reason_avoids_wall_of_text():
    reason = (
        "Composite score uses transparent local components. "
        "This row is a research candidate, not a trade instruction. "
        "Missing or incomplete fields reduced confidence."
    )

    compact = dashboard.compact_reason(reason, max_sentences=2)

    assert compact.count(".") == 2
    assert "Missing or incomplete" not in compact


def test_compact_table_columns_prefers_summaries_over_raw_reason():
    frame = pd.DataFrame(
        {
            "Ticker": ["NVDA"],
            "FinalState": ["Review Thesis"],
            "Reason": ["Long reason"],
            "ReasonSummary": ["Short reason"],
            "MissingDataFields": ["Return1M"],
            "DataGaps": ["Not enough price history"],
        }
    )

    columns = dashboard.compact_table_columns(frame)

    assert "ReasonSummary" in columns
    assert "DataGaps" in columns
    assert "Reason" not in columns


def test_ticker_coverage_display_frame_hides_noisy_paths():
    coverage = pd.DataFrame(
        [
            {
                "dataset_name": "prices",
                "file_path": "/tmp/prices.csv",
                "validation_status": "valid",
                "ticker_present": True,
                "row_count_for_ticker": 25,
                "latest_data_timestamp": "2026-03-14T00:00:00",
                "notes": ["Ticker rows found in local dataset."],
            }
        ]
    )

    display = dashboard.ticker_coverage_display_frame(coverage)

    assert list(display.columns) == ["Dataset", "Status", "TickerData", "Rows", "Latest", "Notes"]
    assert display.iloc[0]["TickerData"] == "Available"
    assert display.iloc[0]["Latest"] == "2026-03-14"


def test_data_source_status_tables_handle_missing_outputs(tmp_path):
    tables = dashboard.load_data_source_status_tables(tmp_path)

    assert tables["data_source_status.csv"][0] is None
    assert "has not been generated" in tables["data_source_status.csv"][1]
    assert dashboard.friendly_data_source_status("manual_only") == "Manual input needed"
    assert dashboard.friendly_data_source_status("optional_unofficial") == "Optional unofficial"


def test_price_update_status_helpers_handle_missing_and_counts(tmp_path):
    frame, message = dashboard.load_price_update_status(tmp_path)

    assert frame is None
    assert "price_update_status.csv" in message

    counts = dashboard.summarize_price_update_status(
        pd.DataFrame({"status": ["fetched", "parse_error", "parse_error", "source_unavailable"]})
    )

    assert counts["fetched"] == 1
    assert counts["parse_error"] == 2


def test_onboarding_tables_handle_missing_outputs_and_summary():
    tables = dashboard.load_data_onboarding_tables(Path("/tmp/nonexistent-dashboard-test-dir"))

    assert tables["ticker_data_coverage.csv"][0] is None
    assert "has not been generated" in tables["ticker_data_coverage.csv"][1]
    assert dashboard.summarize_ticker_coverage(None)["usable_price_tickers"] == 0


def test_research_health_tables_handle_missing_outputs_and_summary(tmp_path):
    tables = dashboard.load_research_health_tables(tmp_path)

    assert tables["data_quality_wizard.csv"][0] is None
    assert "has not been generated" in tables["data_quality_wizard.csv"][1]

    summary = dashboard.summarize_research_health_tables(
        pd.DataFrame({"ReadinessStatus": ["Research Ready", "Needs Price Data"]}),
        pd.DataFrame({"LiquidityStatus": ["Liquid", "Thin / Needs Review"]}),
        pd.DataFrame({"CorrelationStatus": ["High Co-movement", "Low Co-movement"]}),
    )

    assert summary["research_ready"] == 1
    assert summary["needs_price_data"] == 1
    assert summary["liquid"] == 1
    assert summary["thin_liquidity"] == 1
    assert summary["high_correlation"] == 1


def test_action_queue_loader_and_summary_handle_missing_outputs(tmp_path):
    frame, message = dashboard.load_action_queue(tmp_path)

    assert frame is None
    assert "research_action_queue.csv" in message

    summary = dashboard.action_queue_summary(
        pd.DataFrame({"urgency": ["critical", "high", "medium", "critical"]})
    )
    assert summary["critical"] == 2
    assert summary["high"] == 1
    assert summary["medium"] == 1


def test_top_priority_signals_are_compact_and_sorted():
    queue = pd.DataFrame(
        [
            {"priority": 2, "urgency": "high", "action_type": "fundamentals", "ticker": "NVDA", "title": "Improve fundamentals", "reason": "Need SEC staging.", "example_command": "make sec-stage"},
            {"priority": 1, "urgency": "critical", "action_type": "prices", "ticker": "AMD", "title": "Repair prices", "reason": "No local prices.", "example_command": "make price-refresh"},
        ]
    )

    signals = dashboard.top_priority_signals(queue, limit=2)

    assert signals[0]["title"] == "Repair prices"
    assert "P1" in signals[0]["badges"]
    assert signals[1]["title"] == "Improve fundamentals"


def test_workflow_health_score_reflects_action_pressure():
    strong_score, strong_label = dashboard.workflow_health_score(
        {"critical": 0, "high": 0, "medium": 1},
        {"needs_price_data": 0, "thin_liquidity": 0, "high_correlation": 0},
    )
    weak_score, weak_label = dashboard.workflow_health_score(
        {"critical": 8, "high": 4, "medium": 0},
        {"needs_price_data": 6, "thin_liquidity": 2, "high_correlation": 1},
    )

    assert strong_score == 100
    assert strong_label == "Ready"
    assert weak_score < strong_score
    assert weak_label in {"Partial", "Needs Data"}


def test_onboarding_summary_counts_core_and_optional_gaps():
    coverage = pd.DataFrame(
        [
            {
                "ticker": "NVDA",
                "usable_for_momentum": True,
                "dcf_ready": True,
                "peer_ready": True,
                "has_earnings": False,
                "has_analyst_estimates": False,
                "missing_required_for_momentum": "",
                "missing_required_for_dcf": "",
                "missing_required_for_peer_relative": "",
            },
            {
                "ticker": "AMD",
                "usable_for_momentum": False,
                "dcf_ready": False,
                "peer_ready": False,
                "has_earnings": False,
                "has_analyst_estimates": False,
                "missing_required_for_momentum": "prices",
                "missing_required_for_dcf": "fundamentals row",
                "missing_required_for_peer_relative": "peer mapping",
            },
        ]
    )

    summary = dashboard.summarize_ticker_coverage(coverage)

    assert summary["usable_price_tickers"] == 1
    assert summary["dcf_ready_tickers"] == 1
    assert summary["peer_ready_tickers"] == 1
    assert summary["optional_only_missing_tickers"] == 1


def test_stock_report_helpers_format_missing_values_cleanly():
    frame = dashboard.stock_report_key_value_frame(
        {"price": None, "return": float("nan"), "volume": 12345},
        [
            ("price", "Price", "currency"),
            ("return", "Return", "percent"),
            ("volume", "Volume", "integer"),
        ],
    )

    assert frame.iloc[0]["Value"] == "Not available"
    assert frame.iloc[1]["Value"] == "Not enough history"
    assert frame.iloc[2]["Value"] == "12,345"
    assert not frame["Value"].astype(str).str.lower().str.contains("nan|none|null").any()


def test_stock_report_summary_cards_are_readable_and_research_only():
    payload = {
        "ticker": "NVDA",
        "provider_name": "LocalCSVMarketDataProvider",
        "price_snapshot": {"price": 100.0, "volume": None, "market_time": None},
        "performance": {"one_month": 0.12, "three_month": None, "one_year": 0.4},
        "valuation_snapshot": {"status": "partial", "coverage": "limited"},
        "valuation_readiness": {
            "dcf_ready": True,
            "peer_ready": False,
            "earnings_available": False,
            "analyst_estimates_available": False,
        },
        "missing_data_warnings": ["peers missing"],
    }

    cards = dashboard.stock_report_summary_cards(payload)
    rendered = " ".join(str(value) for card in cards for value in card.values())

    assert len(cards) == 4
    assert "$100.00" in rendered
    assert "Peers needed" in rendered
    assert "buy" not in rendered.lower()
    assert "sell" not in rendered.lower()


def test_stock_report_source_frame_hides_raw_missing_values():
    frame = dashboard.stock_report_source_frame(
        [
            {
                "provider": "local",
                "freshness": None,
                "retrieved_at": "2026-05-21T10:00:00Z",
                "official": False,
                "notes": ["CSV fallback"],
            }
        ]
    )

    assert frame.iloc[0]["Freshness"] == "Not available"
    assert frame.iloc[0]["Retrieved"] == "2026-05-21"
    assert frame.iloc[0]["Official"] == "No"
    assert "CSV fallback" in frame.iloc[0]["Notes"]


def test_stock_report_missing_data_text_stays_friendly():
    text = dashboard.stock_report_missing_data_text(["fundamentals unavailable, peers, Return1M"])

    assert "Needs SEC enrichment" in text
    assert "Needs peers.csv" in text
    assert "Not enough price history" in text


def test_data_health_overview_cards_prioritize_price_and_actions():
    validation = pd.DataFrame(
        {
            "validation_status": ["valid", "valid_with_warnings", "missing_file"],
        }
    )
    price_status = pd.DataFrame({"status": ["parse_error", "fetched"]})
    action_queue = pd.DataFrame({"urgency": ["critical", "high", "medium"]})
    coverage = pd.DataFrame(
        {
            "usable_for_momentum": [True, False],
            "dcf_ready": [True, False],
            "peer_ready": [False, False],
            "has_earnings": [False, False],
            "has_analyst_estimates": [False, False],
            "missing_required_for_momentum": ["", "prices"],
            "missing_required_for_dcf": ["", "fundamentals"],
            "missing_required_for_peer_relative": ["peer mapping", "peer mapping"],
        }
    )

    cards = dashboard.data_health_overview_cards(validation, price_status, action_queue, coverage)
    rendered = " ".join(str(value) for card in cards for value in card.values())

    assert len(cards) == 4
    assert "2 usable datasets" in rendered
    assert "1 price issue" in rendered
    assert "1 critical actions" in rendered
    assert "1 price-ready tickers" in rendered


def test_universe_preset_cards_include_preview_commands():
    cards = dashboard.universe_preset_cards()
    rendered = " ".join(str(value) for card in cards for value in card.values())

    assert cards
    assert "preview --preset" in rendered
    assert "apply-import" not in rendered


def test_output_tab_summary_cards_explain_rows_status_and_gaps():
    frame = pd.DataFrame(
        {
            "Ticker": ["NVDA", "AMD", "MSFT"],
            "Theme": ["AI", "AI", "Cloud"],
            "FinalState": ["Watch", "Watch", "Review Thesis"],
            "MissingDataFields": ["", "Return1M", None],
            "Reason": ["Clear setup context.", "Needs price history.", "Review valuation context."],
        }
    )

    cards = dashboard.output_tab_summary_cards("Final Watchlist", frame)
    rendered = " ".join(str(value) for card in cards for value in card.values())

    assert len(cards) == 4
    assert "3 rows" in rendered
    assert "Watch" in rendered
    assert "1 row" in rendered
    assert "AI" in rendered


def test_dominant_value_and_non_empty_count_handle_empty_fields():
    frame = pd.DataFrame(
        {
            "Status": ["", None, "Partial", "Partial"],
            "Missing": ["nan", "Return1M", "", "Not available"],
        }
    )

    value, count = dashboard.dominant_value(frame, ["Status"])

    assert value == "Partial"
    assert count == 2
    assert dashboard.non_empty_count(frame, ["Missing"]) == 1


def test_presentation_frame_uses_readable_labels_and_values():
    frame = pd.DataFrame(
        {
            "Ticker": ["NVDA"],
            "Return1M": [0.1234],
            "WatchlistScore": [81.25],
            "MissingDataFields": ["Return1M, peers"],
            "ReasonSummary": ["Transparent local context."],
        }
    )

    display = dashboard.presentation_frame(frame)

    assert list(display.columns) == ["Ticker", "1M Return", "Watchlist Score", "Missing Data", "Reason"]
    assert display.iloc[0]["1M Return"] == "12.3%"
    assert display.iloc[0]["Watchlist Score"] == "81.2"
    assert "Not enough price history" in display.iloc[0]["Missing Data"]
    assert "Needs peers.csv" in display.iloc[0]["Missing Data"]


def test_display_column_label_humanizes_unknown_columns():
    assert dashboard.display_column_label("avg_volume_20d") == "Avg Volume 20D"
    assert dashboard.display_column_label("PeerRelativeStatus") == "Peer Relative"
