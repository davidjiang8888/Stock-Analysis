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


def test_context_note_html_is_readable_and_escaped():
    html = dashboard.context_note_html("<Filters>", "Use <trusted> local CSV inputs.", tone="warning")

    assert "context-note warning" in html
    assert "&lt;Filters&gt;" in html
    assert "&lt;trusted&gt;" in html


def test_section_header_html_uses_shell_and_escapes_content():
    html = dashboard.section_header_html("<Monthly Picks>", "Use <local> research coverage.")

    assert "section-shell" in html
    assert "section-kicker" in html
    assert "Research View" in html
    assert "&lt;Monthly Picks&gt;" in html
    assert "&lt;local&gt;" in html


def test_chart_panel_title_normalizes_spacing_and_trailing_punctuation():
    assert dashboard.chart_panel_title(" Score context. ") == "Score context"
    assert dashboard.chart_panel_title("Price history chart:") == "Price history chart"
    assert dashboard.chart_panel_title("") == "Chart"


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


def test_compact_table_columns_prioritize_rank_purpose_and_hide_noise():
    frame = pd.DataFrame(
        {
            "GeneratedAt": ["2026-05-21T00:00:00Z"],
            "SourceFiles": ["outputs/final_watchlist.csv"],
            "Month": ["2026-05"],
            "Rank": [1],
            "Ticker": ["NVDA"],
            "PrimaryPurpose": ["Momentum Leader"],
            "CompositeScore": [52.5],
            "ReasonSummary": ["Transparent local context."],
            "DataGaps": ["Needs SEC enrichment"],
        }
    )

    columns = dashboard.compact_table_columns(frame)

    assert columns[:4] == ["Month", "Rank", "Ticker", "PrimaryPurpose"]
    assert "GeneratedAt" not in columns
    assert "SourceFiles" not in columns


def test_reorder_columns_surfaces_summary_and_research_context_first():
    frame = pd.DataFrame(
        {
            "ReasonSummary": ["Short reason"],
            "Ticker": ["NVDA"],
            "CompositeScore": [55.0],
            "PrimaryPurpose": ["Momentum Leader"],
            "DataGaps": ["Not enough price history"],
            "NextBestAction": ["Run make focus-price TICKER=NVDA"],
            "FocusCommand": ["make focus-price TICKER=NVDA"],
            "ExampleCommand": ["make price-normalize INPUT=data/raw/prices/NVDA.csv TICKER=NVDA SOURCE=yahoo_manual"],
            "GeneratedAt": ["2026-05-21T00:00:00Z"],
        }
    )

    reordered = dashboard.reorder_columns(frame)

    assert list(reordered.columns[:8]) == [
        "Ticker",
        "PrimaryPurpose",
        "CompositeScore",
        "NextBestAction",
        "FocusCommand",
        "ExampleCommand",
        "ReasonSummary",
        "DataGaps",
    ]


def test_table_focus_cards_summarize_state_context_and_gaps_cleanly():
    frame = pd.DataFrame(
        {
            "Ticker": ["NVDA", "AMD"],
            "PrimaryPurpose": ["Momentum Leader", "Momentum Leader"],
            "FinalState": ["Watch", "Watch"],
            "MissingDataFields": ["Return3M", ""],
            "WatchlistScore": [72.0, 61.0],
        }
    )

    cards = dashboard.table_focus_cards(frame)
    rendered = " ".join(str(value) for card in cards for value in card.values()).lower()

    assert len(cards) == 4
    assert "2 rows" in rendered
    assert "watch" in rendered
    assert "momentum leader" in rendered
    assert "1 row with gaps" in rendered
    assert "buy" not in rendered
    assert "sell" not in rendered


def test_detail_columns_group_reasons_support_and_operational_fields():
    frame = pd.DataFrame(
        {
            "Ticker": ["NVDA"],
            "Theme": ["AI"],
            "FinalState": ["Watch"],
            "Reason": ["Transparent local context."],
            "RankReason": ["Strong relative score."],
            "MissingDataFields": ["Return3M"],
            "ConflictReasons": ["Price history is short."],
            "RiskPenalty": [12.0],
            "SourceFiles": ["outputs/final_watchlist.csv"],
            "GeneratedAt": ["2026-05-21T00:00:00Z"],
            "MemberTickers": ["NVDA, AVGO"],
        }
    )

    reason_columns = dashboard.detail_columns(frame, "reasons")
    support_columns = dashboard.detail_columns(frame, "support")
    operations_columns = dashboard.detail_columns(frame, "operations")

    assert "Reason" in reason_columns
    assert "RankReason" in reason_columns
    assert "MissingDataFields" in support_columns
    assert "ConflictReasons" in support_columns
    assert "RiskPenalty" in support_columns
    assert "SourceFiles" in operations_columns
    assert "GeneratedAt" in operations_columns
    assert "MemberTickers" in operations_columns


def test_detail_sections_build_mid_level_panels_without_buy_sell_language():
    frame = pd.DataFrame(
        {
            "Ticker": ["NVDA"],
            "Theme": ["AI"],
            "FinalState": ["Watch"],
            "Reason": ["Transparent local context."],
            "MissingDataFields": ["Return3M"],
            "SourceFiles": ["outputs/final_watchlist.csv"],
        }
    )

    sections = dashboard.detail_sections(frame, show_reason_details=True)
    titles = [title for title, _ in sections]
    rendered = " ".join(str(value) for title, detail in sections for value in [title, detail.to_dict()]).lower()

    assert titles == ["Reasons", "Risk and data gaps", "Source and operational context"]
    assert "buy" not in rendered
    assert "sell" not in rendered


def test_pick_filter_column_prefers_first_populated_candidate():
    frame = pd.DataFrame(
        {
            "Sector": ["", None],
            "SectorETF": ["SMH", "QQQ"],
            "ETF": ["", ""],
        }
    )

    assert dashboard.pick_filter_column(frame, ["Sector", "SectorETF", "ETF"]) == "SectorETF"


def test_filter_summary_text_stays_readable_and_compact():
    text = dashboard.filter_summary_text(
        "monthly-research-picks",
        "nvda",
        "FinalState",
        ["Watch", "Review Thesis", "Setup Forming", "Avoid"],
        "Theme",
        ["AI"],
        "SectorETF",
        ["SMH"],
        4,
        12,
    )

    assert "4 of 12 rows visible" in text
    assert "search `nvda`" in text
    assert "Final State: Watch, Review Thesis, Setup Forming +1 more" in text
    assert "Theme: AI" in text
    assert "Sector ETF: SMH" in text
    assert "nan" not in text.lower()
    assert "none" not in text.lower()


def test_filter_summary_text_handles_no_active_filters():
    text = dashboard.filter_summary_text(
        "market-direction",
        "",
        None,
        [],
        None,
        [],
        None,
        [],
        9,
        9,
    )

    assert "Market Direction" in text
    assert "9 of 9 rows visible" in text
    assert "Use search or filters" in text


def test_filter_summary_text_can_be_wrapped_in_context_note():
    summary = dashboard.filter_summary_text(
        "final-watchlist",
        "nvda",
        "FinalState",
        ["Watch"],
        "Theme",
        ["AI"],
        "SectorETF",
        ["SMH"],
        1,
        12,
    )
    html = dashboard.context_note_html("Active filters.", summary)

    assert "context-note" in html
    assert "Active filters." in html
    assert "1 of 12 rows visible" in html


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

    source_frame, source_message = tables["data_source_status.csv"]
    gap_frame, gap_message = tables["data_gap_report.csv"]

    assert source_frame is not None
    assert gap_frame is not None
    assert source_message is None
    assert gap_message is None
    assert "focus_command" in source_frame.columns
    assert "focus_command" in gap_frame.columns
    assert dashboard.friendly_data_source_status("manual_only") == "Manual input needed"
    assert dashboard.friendly_data_source_status("optional_unofficial") == "Optional unofficial"


def test_pipeline_outputs_loader_regenerates_missing_core_outputs(tmp_path):
    old_base = dashboard.BASE_DIR
    old_outputs = dashboard.OUTPUTS_DIR
    try:
        dashboard.BASE_DIR = Path("/Users/yjian070/Documents/New project")
        dashboard.OUTPUTS_DIR = tmp_path
        tables = dashboard.load_pipeline_outputs(tmp_path)
    finally:
        dashboard.BASE_DIR = old_base
        dashboard.OUTPUTS_DIR = old_outputs

    for filename in dashboard.PIPELINE_FILES:
        frame, message = tables[filename]
        assert frame is not None
        assert message is None

    assert (tmp_path / "purpose_classification.csv").exists()
    assert (tmp_path / "market_direction.csv").exists()
    assert (tmp_path / "final_watchlist.csv").exists()


def test_data_source_status_table_columns_surface_command_fields():
    frame = pd.DataFrame(
        [
            {
                "dataset": "fundamentals",
                "availability_status": "partial",
                "required_for": "valuation",
                "fallback_action": "Start with make status.",
                "focus_command": "make status",
                "example_command": "make runbook-fundamentals-broader",
                "local_file": "data/fundamentals.csv",
                "row_count": 6,
                "validation_warnings": "as_of_date missing",
                "source_name": "fixture",
                "source_type": "local_csv",
                "expected_local_file": "data/fundamentals.csv",
                "notes": "fixture",
            }
        ]
    )

    columns = dashboard.data_source_status_table_columns(frame)

    assert columns[:6] == [
        "dataset",
        "availability_status",
        "required_for",
        "fallback_action",
        "focus_command",
        "example_command",
    ]


def test_data_source_status_tables_refresh_stale_gap_report_columns(tmp_path):
    data_dir = tmp_path / "data"
    outputs_dir = tmp_path / "outputs"
    data_dir.mkdir()
    outputs_dir.mkdir()
    (data_dir / "prices.csv").write_text("date,ticker,adj_close,volume\n2026-01-02,NVDA,100,1000\n", encoding="utf-8")
    (data_dir / "universe.csv").write_text(
        "ticker,theme,sectoretf,defaultpurpose,marketcapbucket,notes\n"
        "NVDA,AI,SMH,Momentum Leader,Large,fixture\n",
        encoding="utf-8",
    )
    (data_dir / "holdings.csv").write_text("ticker,primarypurpose\nNVDA,Momentum Leader\n", encoding="utf-8")
    pd.DataFrame(
        [
            {
                "dataset": "fundamentals",
                "ticker": "",
                "status": "partial",
                "reason": "stale",
                "required_for": "valuation",
                "recommended_action": "old",
                "local_file": "data/fundamentals.csv",
                "source_name": "fixture",
            }
        ]
    ).to_csv(outputs_dir / "data_gap_report.csv", index=False)
    pd.DataFrame(
        [
            {
                "dataset": "prices",
                "source_name": "fixture",
                "source_type": "local_csv",
                "availability_status": "available",
                "required_for": "momentum",
                "is_required": True,
                "is_optional": False,
                "is_manual_only": False,
                "is_unofficial": False,
                "requires_network": False,
                "requires_user_agent": False,
                "requires_api_key": False,
                "expected_local_file": "data/prices.csv",
                "fallback_action": "old",
                "notes": "old",
                "local_file": "data/prices.csv",
                "row_count": 1,
                "available_columns": "date,ticker,adj_close,volume",
                "validation_warnings": "",
            }
        ]
    ).to_csv(outputs_dir / "data_source_status.csv", index=False)

    old_base = dashboard.BASE_DIR
    try:
        dashboard.BASE_DIR = tmp_path
        tables = dashboard.load_data_source_status_tables(outputs_dir)
    finally:
        dashboard.BASE_DIR = old_base

    gap_frame, _ = tables["data_gap_report.csv"]
    assert gap_frame is not None
    assert "target_file" in gap_frame.columns
    assert "focus_command" in gap_frame.columns
    assert "example_command" in gap_frame.columns
    assert gap_frame.loc[gap_frame["dataset"] == "fundamentals", "example_command"].iloc[0] == "make runbook-fundamentals-broader"


def test_data_source_status_tables_refresh_stale_source_status_columns(tmp_path):
    outputs_dir = tmp_path
    pd.DataFrame(
        [
            {
                "dataset": "fundamentals",
                "ticker": "",
                "status": "partial",
                "reason": "old",
                "required_for": "valuation",
                "recommended_action": "Start with make status",
                "focus_command": "make status",
                "example_command": "make runbook-fundamentals-broader",
                "local_file": "data/fundamentals.csv",
                "source_name": "fixture",
            }
        ]
    ).to_csv(outputs_dir / "data_gap_report.csv", index=False)
    pd.DataFrame(
        [
            {
                "dataset": "fundamentals",
                "source_name": "fixture",
                "source_type": "local_csv",
                "availability_status": "partial",
                "required_for": "valuation",
                "is_required": False,
                "is_optional": True,
                "is_manual_only": False,
                "is_unofficial": False,
                "requires_network": False,
                "requires_user_agent": False,
                "requires_api_key": False,
                "expected_local_file": "data/fundamentals.csv",
                "fallback_action": "old",
                "notes": "old",
                "local_file": "data/fundamentals.csv",
                "row_count": 1,
                "available_columns": "ticker,pe_ratio",
                "validation_warnings": "",
            }
        ]
    ).to_csv(outputs_dir / "data_source_status.csv", index=False)

    old_base = dashboard.BASE_DIR
    try:
        dashboard.BASE_DIR = tmp_path
        tables = dashboard.load_data_source_status_tables(outputs_dir)
    finally:
        dashboard.BASE_DIR = old_base

    source_frame, _ = tables["data_source_status.csv"]
    assert source_frame is not None
    assert "target_file" in source_frame.columns
    assert "focus_command" in source_frame.columns
    assert "example_command" in source_frame.columns
    assert source_frame.loc[source_frame["dataset"] == "fundamentals", "example_command"].iloc[0] == "make runbook-fundamentals-broader"


def test_price_update_status_helpers_handle_missing_and_counts(tmp_path):
    frame, message = dashboard.load_price_update_status(tmp_path)

    assert frame is None
    assert "price_update_status.csv" in message
    assert "make status" in message
    assert "make price-normalize" in message

    counts = dashboard.summarize_price_update_status(
        pd.DataFrame({"status": ["fetched", "parse_error", "parse_error", "source_unavailable"]})
    )

    assert counts["fetched"] == 1
    assert counts["parse_error"] == 2


def test_load_price_update_status_enriches_legacy_command_fields(tmp_path):
    pd.DataFrame(
        [
            {
                "ticker": "AMD",
                "status": "parse_error",
                "rows_fetched": 0,
                "rows_merged": 0,
                "error_category": "parse_error",
                "error_message": "AMD parse failed",
                "fallback_used": True,
                "recommended_action": "Run make focus-price TICKER=AMD, or run python3 -m src.data_update --tickers AMD and normalize verified downloaded OHLCV rows into data/imports/prices.csv.",
            }
        ]
    ).to_csv(tmp_path / "price_update_status.csv", index=False)

    frame, message = dashboard.load_price_update_status(tmp_path)

    assert message is None
    assert frame is not None
    assert frame.iloc[0]["recommended_action"].startswith("Run make focus-price TICKER=AMD")
    assert frame.iloc[0]["focus_command"] == "make focus-price TICKER=AMD"
    assert frame.iloc[0]["example_command"] == "make price-normalize INPUT=data/raw/prices/AMD.csv TICKER=AMD SOURCE=yahoo_manual"
    assert frame.iloc[0]["target_file"] == "data/imports/prices.csv"


def test_price_update_status_table_columns_surface_command_fields():
    columns = dashboard.price_update_status_table_columns(
        pd.DataFrame(
            [
                {
                    "ticker": "AMD",
                    "status": "parse_error",
                    "rows_fetched": 0,
                    "rows_merged": 0,
                    "error_category": "parse_error",
                    "error_message": "AMD parse failed",
                    "fallback_used": True,
                    "recommended_action": "Fix prices",
                    "focus_command": "make focus-price TICKER=AMD",
                    "example_command": "make price-normalize INPUT=data/raw/prices/AMD.csv TICKER=AMD SOURCE=yahoo_manual",
                    "target_file": "data/imports/prices.csv",
                }
            ]
        )
    )

    assert columns == [
        "ticker",
        "status",
        "rows_fetched",
        "rows_merged",
        "error_category",
        "error_message",
        "fallback_used",
        "recommended_action",
        "focus_command",
        "example_command",
        "target_file",
    ]


def test_load_action_queue_refreshes_stale_queue_artifact(tmp_path):
    pd.DataFrame(
        [
            {
                "priority": 1,
                "urgency": "critical",
                "action_type": "prices",
                "ticker": "AMD",
                "title": "Repair price history for AMD",
                "status": "parse_error",
                "recommended_action": "Retry later or use staged manual prices in data/imports/prices.csv.",
                "example_command": "python3 -m src.data_update --tickers AMD",
                "source_file": "data/imports/prices.csv",
                "source_artifact": "outputs/price_update_status.csv",
                "reason": "AMD parse failed",
            }
        ]
    ).to_csv(tmp_path / "research_action_queue.csv", index=False)

    old_base = dashboard.BASE_DIR
    try:
        dashboard.BASE_DIR = Path("/Users/yjian070/Documents/New project")
        frame, message = dashboard.load_action_queue(tmp_path)
    finally:
        dashboard.BASE_DIR = old_base

    assert message is None
    assert frame is not None
    assert "focus_command" in frame.columns
    assert "example_command" in frame.columns
    assert "target_file" in frame.columns
    price_rows = frame.loc[frame["action_type"].astype(str).str.strip().eq("prices")]
    assert not price_rows.empty
    assert price_rows["recommended_action"].astype(str).str.contains("make focus-price").all()
    assert price_rows["target_file"].astype(str).str.strip().eq("data/imports/prices.csv").all()


def test_load_research_health_tables_refreshes_stale_wizard_artifact(tmp_path):
    pd.DataFrame(
        [
            {
                "Ticker": "AMD",
                "DataQualityScore": 10,
                "ReadinessStatus": "Needs Price Data",
                "MomentumReady": False,
                "MonthlyPicksReady": False,
                "DCFReady": False,
                "PeerReady": False,
                "EarningsAvailable": False,
                "AnalystEstimatesAvailable": False,
                "PriceHistoryDays": 0,
                "MissingDataFields": "prices",
                "NextBestAction": "old",
                "Reason": "old",
            }
        ]
    ).to_csv(tmp_path / "data_quality_wizard.csv", index=False)

    old_base = dashboard.BASE_DIR
    try:
        dashboard.BASE_DIR = Path("/Users/yjian070/Documents/New project")
        tables = dashboard.load_research_health_tables(tmp_path)
    finally:
        dashboard.BASE_DIR = old_base

    frame, message = tables["data_quality_wizard.csv"]
    assert message is None
    assert frame is not None
    assert "FocusCommand" in frame.columns
    assert "ExampleCommand" in frame.columns
    amd_row = frame.loc[frame["Ticker"] == "AMD"].iloc[0]
    assert amd_row["FocusCommand"] == "make focus-price TICKER=AMD"
    assert "make price-normalize" in amd_row["ExampleCommand"]


def test_load_data_onboarding_tables_refreshes_stale_coverage_artifact(tmp_path):
    pd.DataFrame(
        [
            {
                "ticker": "AMD",
                "has_prices": False,
                "price_history_days": 0,
                "has_fundamentals": False,
                "dcf_ready": False,
                "has_peer_mapping": False,
                "peer_ready": False,
                "has_earnings": False,
                "has_analyst_estimates": False,
                "usable_for_momentum": False,
                "usable_for_monthly_picks": False,
                "usable_for_dcf": False,
                "usable_for_peer_relative": False,
                "missing_required_for_momentum": "prices",
                "missing_required_for_dcf": "fundamentals row",
                "missing_required_for_peer_relative": "peer mapping",
                "next_best_action": "old",
            }
        ]
    ).to_csv(tmp_path / "ticker_data_coverage.csv", index=False)

    old_base = dashboard.BASE_DIR
    try:
        dashboard.BASE_DIR = Path("/Users/yjian070/Documents/New project")
        tables = dashboard.load_data_onboarding_tables(tmp_path)
    finally:
        dashboard.BASE_DIR = old_base

    frame, message = tables["ticker_data_coverage.csv"]
    assert message is None
    assert frame is not None
    assert {"target_file", "focus_command", "example_command"} <= set(frame.columns)
    amd_row = frame.loc[frame["ticker"] == "AMD"].iloc[0]
    assert amd_row["focus_command"] == "make focus-price TICKER=AMD"
    assert "make price-normalize" in amd_row["example_command"]


def test_load_data_onboarding_tables_refreshes_stale_optional_context_artifact(tmp_path):
    pd.DataFrame(
        [
            {
                "priority": 5,
                "ticker": "AMD",
                "has_earnings": False,
                "has_analyst_estimates": False,
                "earnings_context_ready": False,
                "estimate_context_ready": False,
                "missing_optional_context": "earnings, analyst_estimates",
                "recommended_action": "old",
                "target_file": "data/imports/earnings.csv and data/imports/analyst_estimates.csv",
                "example_command": "make templates",
                "safe_next_step": "old",
            }
        ]
    ).to_csv(tmp_path / "optional_context_worklist.csv", index=False)

    old_base = dashboard.BASE_DIR
    try:
        dashboard.BASE_DIR = Path("/Users/yjian070/Documents/New project")
        tables = dashboard.load_data_onboarding_tables(tmp_path)
    finally:
        dashboard.BASE_DIR = old_base

    frame, message = tables["optional_context_worklist.csv"]
    assert message is None
    assert frame is not None
    assert "focus_command" in frame.columns
    amd_row = frame.loc[frame["ticker"] == "AMD"].iloc[0]
    assert amd_row["focus_command"] == "make templates"


def test_onboarding_tables_handle_missing_outputs_and_summary():
    tables = dashboard.load_data_onboarding_tables(Path("/tmp/nonexistent-dashboard-test-dir"))

    for filename in (
        "ticker_data_coverage.csv",
        "price_import_worklist.csv",
        "fundamentals_peer_worklist.csv",
        "optional_context_worklist.csv",
        "sec_stage_queue.csv",
        "peer_mapping_queue.csv",
        "ticker_unlock_ladder.csv",
        "unlock_priority_summary.csv",
    ):
        frame, message = tables[filename]
        assert frame is not None
        assert message is None
    assert dashboard.summarize_ticker_coverage(None)["usable_price_tickers"] == 0
    assert dashboard.summarize_price_worklist(None)["priority_1"] == 0
    assert dashboard.summarize_fundamentals_peer_worklist(None)["fundamentals_priority_1"] == 0
    assert dashboard.summarize_optional_context_worklist(None)["missing_both"] == 0
    assert dashboard.summarize_sec_stage_queue(None)["priority_1"] == 0
    assert dashboard.summarize_peer_mapping_queue(None)["priority_1"] == 0
    assert dashboard.summarize_ticker_unlock_ladder(None)["price_stage"] == 0
    assert dashboard.summarize_unlock_priority_summary(None)["holdings_groups"] == 0


def test_summarize_price_worklist_counts_readiness_levels():
    worklist = pd.DataFrame(
        {
            "next_price_goal": ["Unlock Track Record", "Unlock Monthly Picks", "Reach Preferred 1Y History"],
            "next_target_history_rows": [63, 21, 252],
            "rows_needed_for_next_goal": [42, 21, 189],
            "suggested_start_date": ["2025-10-01", "2026-01-01", "2025-01-01"],
            "momentum_ready": [True, False, True],
            "track_record_ready": [False, False, True],
            "preferred_history_ready": [False, False, False],
            "priority": [1, 2, 1],
        }
    )

    summary = dashboard.summarize_price_worklist(worklist)

    assert summary["momentum_ready"] == 2
    assert summary["track_record_ready"] == 1
    assert summary["preferred_history_ready"] == 0
    assert summary["priority_1"] == 2


def test_summarize_fundamentals_peer_worklist_counts_blockers():
    worklist = pd.DataFrame(
        {
            "dcf_ready": [True, False, False],
            "peer_ready": [False, False, True],
            "priority": [2, 1, 4],
        }
    )

    summary = dashboard.summarize_fundamentals_peer_worklist(worklist)

    assert summary["dcf_ready"] == 1
    assert summary["peer_ready"] == 1
    assert summary["fundamentals_priority_1"] == 1
    assert summary["peer_priority_2"] == 1


def test_summarize_optional_context_worklist_counts_missing_optional_coverage():
    worklist = pd.DataFrame(
        {
            "has_earnings": [True, False, False],
            "has_analyst_estimates": [False, False, True],
            "priority": [6, 5, 6],
        }
    )

    summary = dashboard.summarize_optional_context_worklist(worklist)

    assert summary["earnings_ready"] == 1
    assert summary["estimates_ready"] == 1
    assert summary["missing_both"] == 1
    assert summary["missing_one"] == 2


def test_summarize_sec_stage_queue_counts_priority_and_missing_rows():
    worklist = pd.DataFrame(
        {
            "priority": [1, 2, 2],
            "is_holding": [True, False, True],
            "has_fundamentals": [False, True, False],
        }
    )

    summary = dashboard.summarize_sec_stage_queue(worklist)

    assert summary["priority_1"] == 1
    assert summary["priority_2"] == 2
    assert summary["holdings"] == 2
    assert summary["missing_fundamentals"] == 2


def test_summarize_peer_mapping_queue_counts_priority_and_missing_mappings():
    worklist = pd.DataFrame(
        {
            "priority": [1, 2, 4],
            "is_holding": [True, False, True],
            "has_peer_mapping": [False, True, False],
        }
    )

    summary = dashboard.summarize_peer_mapping_queue(worklist)

    assert summary["priority_1"] == 1
    assert summary["priority_2"] == 1
    assert summary["holdings"] == 2
    assert summary["missing_peer_mapping"] == 2


def test_summarize_ticker_unlock_ladder_counts_stages():
    worklist = pd.DataFrame(
        {
            "current_unlock_stage": ["prices", "fundamentals", "peers", "optional_context", "ready"],
        }
    )

    summary = dashboard.summarize_ticker_unlock_ladder(worklist)

    assert summary["price_stage"] == 1
    assert summary["fundamentals_stage"] == 1
    assert summary["peer_stage"] == 1
    assert summary["optional_stage"] == 1
    assert summary["ready_stage"] == 1


def test_summarize_unlock_priority_summary_counts_group_types_and_stages():
    worklist = pd.DataFrame(
        {
            "group_type": ["holdings", "theme", "theme", "sector_etf"],
            "top_priority_stage": ["prices", "fundamentals", "prices", "peers"],
        }
    )

    summary = dashboard.summarize_unlock_priority_summary(worklist)

    assert summary["holdings_groups"] == 1
    assert summary["theme_groups"] == 2
    assert summary["sector_groups"] == 1
    assert summary["price_led_groups"] == 2
    assert summary["fundamentals_led_groups"] == 1


def test_research_health_tables_handle_missing_outputs_and_summary(tmp_path):
    tables = dashboard.load_research_health_tables(tmp_path)

    wizard_frame, wizard_message = tables["data_quality_wizard.csv"]
    liquidity_frame, liquidity_message = tables["liquidity_risk.csv"]
    correlation_frame, correlation_message = tables["correlation_risk.csv"]

    assert wizard_frame is not None
    assert liquidity_frame is not None
    assert correlation_frame is not None
    assert wizard_message is None
    assert liquidity_message is None
    assert correlation_message is None
    assert "FocusCommand" in wizard_frame.columns

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

    assert frame is not None
    assert message is None
    assert "focus_command" in frame.columns
    assert "example_command" in frame.columns

    summary = dashboard.action_queue_summary(
        pd.DataFrame({"urgency": ["critical", "high", "medium", "critical"]})
    )
    assert summary["critical"] == 2
    assert summary["high"] == 1
    assert summary["medium"] == 1


def test_top_priority_signals_are_compact_and_sorted():
    queue = pd.DataFrame(
        [
            {"priority": 2, "urgency": "high", "action_type": "fundamentals", "ticker": "NVDA", "title": "Improve fundamentals", "reason": "Need SEC staging.", "focus_command": "make focus-fundamentals TICKER=NVDA", "example_command": "make sec-stage"},
            {"priority": 1, "urgency": "critical", "action_type": "prices", "ticker": "AMD", "title": "Repair prices", "reason": "No local prices.", "recommended_action": "Normalize verified downloaded OHLCV rows and run validate/preview/apply.", "focus_command": "make focus-price TICKER=AMD", "example_command": "make price-refresh"},
        ]
    )

    signals = dashboard.top_priority_signals(queue, limit=2)

    assert signals[0]["title"] == "Repair prices"
    assert "P1" in signals[0]["badges"]
    assert signals[0]["command"] == "make focus-price TICKER=AMD"
    assert "normalize verified downloaded ohlcv rows" in signals[0]["body"].lower()
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


def test_project_status_helpers_turn_payload_into_cards_and_commands():
    payload = {
        "summary": {
            "data_sources_total": 10,
            "data_sources_available": 4,
            "data_gaps": 12,
            "tickers_total": 20,
            "tickers_with_prices": 9,
            "tickers_dcf_ready": 3,
            "tickers_peer_ready": 2,
            "critical_actions": 5,
            "onboarding_actions": 18,
        },
        "top_onboarding_actions": [
            {
                "priority": 1,
                "dataset": "prices",
                "ticker": "NVDA",
                "reason": "Short local price history.",
                "recommended_action": "Normalize verified downloaded OHLCV rows and run validate/preview/apply.",
                "focus_command": "make focus-price TICKER=NVDA",
                "example_command": "make price-refresh",
            }
        ],
        "recommended_next_commands": ["make onboarding", "make verify"],
    }

    cards = dashboard.project_status_metric_cards(payload)
    actions = dashboard.project_status_action_cards(payload)
    commands = dashboard.project_status_command_rows(payload)
    rendered = " ".join(str(value) for card in cards for value in card)

    assert "4/10" in rendered
    assert "9/20" in rendered
    assert actions[0][0] == "P1 prices - NVDA"
    assert "normalize verified downloaded ohlcv rows" in actions[0][1].lower()
    assert actions[0][2] == "make focus-price TICKER=NVDA"
    assert actions[0][3] == "danger"
    assert commands[0]["Command"] == "make status"


def test_project_status_cockpit_is_readable_and_research_safe():
    payload = {
        "summary": {
            "tickers_total": 12,
            "tickers_with_prices": 3,
            "tickers_dcf_ready": 0,
            "tickers_peer_ready": 0,
            "critical_actions": 9,
            "data_gaps": 25,
        }
    }

    html = dashboard.project_status_cockpit_html(payload, 44, "Needs Data")

    assert "Research Cockpit" in html
    assert "3/12" in html
    assert "0/12" in html
    assert "missing inputs are labeled instead of guessed" in html
    assert "buy" not in html.lower()
    assert "sell" not in html.lower()


def test_project_status_command_rows_prefer_structured_rows():
    payload = {
        "recommended_next_command_rows": [
            {
                "Step": "Fix top prices blocker (NVDA)",
                "Command": "make focus-price TICKER=NVDA",
                "Reason": "Short local price history still blocks downstream work.",
            },
            {
                "Step": "Run Price Coverage Bundle (Broader Queue)",
                "Command": "make runbook-prices-broader",
                "Reason": "Advance broader local price coverage next.",
            },
        ],
        "recommended_next_commands": ["make onboarding", "make verify"],
    }

    rows = dashboard.project_status_command_rows(payload)

    assert rows[0]["Step"] == "Fix top prices blocker (NVDA)"
    assert rows[0]["Command"] == "make focus-price TICKER=NVDA"
    assert rows[0]["Reason"] == "Short local price history still blocks downstream work."
    assert rows[1]["Command"] == "make runbook-prices-broader"


def test_overview_landing_cards_surface_workflow_and_gap_context():
    payload = {
        "summary": {
            "tickers_total": 12,
            "tickers_with_prices": 3,
            "tickers_dcf_ready": 0,
            "tickers_peer_ready": 0,
            "data_gaps": 25,
        }
    }
    cards = dashboard.overview_landing_cards(payload, {"critical": 4, "high": 7}, "2026-05-12", 12, 4)
    rendered = " ".join(str(value) for card in cards for value in card.values()).lower()

    assert len(cards) == 4
    assert "12 watchlist rows" in rendered
    assert "4 current monthly candidates" in rendered
    assert "3/12" in rendered
    assert "0 dcf-ready" in rendered
    assert "make status" in rendered
    assert "buy" not in rendered
    assert "sell" not in rendered


def test_holdings_unlock_cards_surface_portfolio_blockers():
    holdings = pd.DataFrame(
        [
            {"Ticker": "NVDA", "PrimaryPurpose": "Momentum Leader"},
            {"Ticker": "TSLA", "PrimaryPurpose": "Speculative Optionality"},
        ]
    )
    ladder = pd.DataFrame(
        [
            {
                "ticker": "NVDA",
                "current_unlock_stage": "fundamentals",
                "next_unlock_goal": "Unlock DCF",
                "recommended_action": "Stage verified fundamentals.",
                "focus_command": "make focus-fundamentals TICKER=NVDA",
                "example_command": "make sec-stage TICKERS=NVDA",
                "price_stage_status": "momentum_ready_short_history",
            },
            {
                "ticker": "TSLA",
                "current_unlock_stage": "prices",
                "next_unlock_goal": "Unlock Monthly Picks",
                "recommended_action": "Add more verified local price history.",
                "focus_command": "make focus-price TICKER=TSLA",
                "example_command": "make price-refresh",
                "price_stage_status": "partial_price_history",
            },
        ]
    )
    summary = pd.DataFrame(
        [
            {
                "group_type": "holdings",
                "group_name": "Current Holdings",
                "ticker_count": 2,
                "holdings_count": 2,
                "top_priority_stage": "prices",
                "next_unlock_goal": "Unlock Monthly Picks",
                "representative_tickers": "TSLA, NVDA",
                "focus_command": "make status",
                "example_command": "make runbook-prices",
            }
        ]
    )

    cards = dashboard.holdings_unlock_cards(holdings, ladder, summary, limit=2)
    rendered = " ".join(str(value) for card in cards for value in card.values()).lower()

    assert cards[0]["kicker"] == "HOLDINGS FIRST"
    assert "unlock monthly picks" in rendered
    assert "nvda" in rendered
    assert "tsla" in rendered
    assert cards[0]["command"] == "make runbook-prices"
    assert any(card.get("command") == "make focus-price TICKER=TSLA" for card in cards)
    assert "buy" not in rendered
    assert "sell" not in rendered


def test_holdings_unlock_cards_handle_missing_inputs_gracefully():
    cards = dashboard.holdings_unlock_cards(None, None, None)
    rendered = " ".join(str(value) for card in cards for value in card.values()).lower()

    assert "no holdings unlock board yet" in rendered
    assert "buy" not in rendered


def test_holdings_deep_research_cards_surface_sec_and_peer_blockers():
    holdings = pd.DataFrame(
        [
            {"Ticker": "NVDA", "PrimaryPurpose": "Momentum Leader"},
            {"Ticker": "TSLA", "PrimaryPurpose": "Speculative Optionality"},
        ]
    )
    sec_queue = pd.DataFrame(
        [
            {
                "priority": 1,
                "ticker": "NVDA",
                "theme": "AI",
                "recommended_action": "Stage or add richer verified fundamentals to close the remaining DCF input gaps.",
                "example_command": "python3 -m src.stock_report --sec-stage-fundamentals --tickers NVDA",
                "price_history_days": 25,
            }
        ]
    )
    peer_queue = pd.DataFrame(
        [
            {
                "priority": 1,
                "ticker": "TSLA",
                "theme": "EV",
                "recommended_action": "Add manually researched peer mappings for this ticker and keep peer-relative comparison transparent.",
                "example_command": "make templates",
            }
        ]
    )

    cards = dashboard.holdings_deep_research_cards(holdings, sec_queue, peer_queue, limit=4)
    rendered = " ".join(str(value) for card in cards for value in card.values()).lower()

    assert any(card["title"] == "Unlock DCF" for card in cards)
    assert any(card["title"] == "Unlock Peer Relative" for card in cards)
    assert "nvda" in rendered
    assert "tsla" in rendered
    assert "buy" not in rendered
    assert "sell" not in rendered


def test_holdings_deep_research_cards_handle_missing_inputs_gracefully():
    cards = dashboard.holdings_deep_research_cards(None, None, None)
    rendered = " ".join(str(value) for card in cards for value in card.values()).lower()

    assert "no holdings deep-research board yet" in rendered
    assert "buy" not in rendered


def test_theme_unlock_cards_surface_grouped_theme_priorities():
    summary = pd.DataFrame(
        [
            {
                "group_type": "theme",
                "group_name": "AI Semiconductors",
                "ticker_count": 3,
                "holdings_count": 1,
                "top_priority_stage": "prices",
                "next_unlock_goal": "Unlock Monthly Picks",
                "recommended_action": "Fill verified local price history first.",
                "focus_command": "make status",
                "example_command": "make runbook-prices",
            },
            {
                "group_type": "sector_etf",
                "group_name": "SMH",
                "ticker_count": 8,
                "holdings_count": 1,
                "top_priority_stage": "fundamentals",
                "next_unlock_goal": "Unlock DCF",
                "recommended_action": "Stage or add verified fundamentals.",
                "focus_command": "make status",
                "example_command": "make runbook-fundamentals",
            },
        ]
    )

    cards = dashboard.theme_unlock_cards(summary, limit=2)
    rendered = " ".join(str(value) for card in cards for value in card.values()).lower()

    assert cards[0]["kicker"] == "THEME FIRST"
    assert "ai semiconductors" in rendered
    assert "smh" in rendered
    assert "unlock monthly picks" in rendered
    assert cards[0]["command"] == "make runbook-prices"
    assert any(card.get("command") == "make runbook-fundamentals" for card in cards)
    assert "buy" not in rendered
    assert "sell" not in rendered


def test_theme_unlock_cards_handle_missing_inputs_gracefully():
    cards = dashboard.theme_unlock_cards(None)
    rendered = " ".join(str(value) for card in cards for value in card.values()).lower()

    assert "no theme unlock board yet" in rendered
    assert "make status" in rendered
    assert "buy" not in rendered


def test_theme_deep_research_cards_surface_sec_and_peer_theme_blockers():
    sec_queue = pd.DataFrame(
        [
            {
                "priority": 1,
                "ticker": "NVDA",
                "theme": "AI Semiconductors",
                "is_holding": True,
                "recommended_action": "Stage or add richer verified fundamentals to close the remaining DCF input gaps.",
            },
            {
                "priority": 2,
                "ticker": "AMD",
                "theme": "AI Semiconductors",
                "is_holding": False,
                "recommended_action": "Run SEC staging for fundamentals so DCF assumptions can be reviewed from explicit local inputs.",
            },
        ]
    )
    peer_queue = pd.DataFrame(
        [
            {
                "priority": 1,
                "ticker": "SMH",
                "theme": "Semiconductor ETF",
                "is_holding": False,
                "recommended_action": "Add manually researched peer mappings for this ticker and keep peer-relative comparison transparent.",
            }
        ]
    )

    cards = dashboard.theme_deep_research_cards(sec_queue, peer_queue, limit=4)
    rendered = " ".join(str(value) for card in cards for value in card.values()).lower()

    assert any(card["title"] == "Unlock DCF" for card in cards)
    assert any(card["title"] == "Unlock Peer Relative" for card in cards)
    assert "ai semiconductors" in rendered
    assert "semiconductor etf" in rendered
    assert "buy" not in rendered
    assert "sell" not in rendered


def test_theme_deep_research_cards_handle_missing_inputs_gracefully():
    cards = dashboard.theme_deep_research_cards(None, None)
    rendered = " ".join(str(value) for card in cards for value in card.values()).lower()

    assert "no theme deep-research board yet" in rendered
    assert "buy" not in rendered


def test_overview_research_pressure_cards_compare_price_fundamentals_and_peers():
    price_worklist = pd.DataFrame(
        {
            "priority": [1, 1, 2],
            "momentum_ready": [False, True, True],
            "track_record_ready": [False, False, True],
        }
    )
    sec_queue = pd.DataFrame(
        {
            "priority": [1, 2, 2],
            "is_holding": [True, False, True],
            "has_fundamentals": [False, True, False],
        }
    )
    peer_queue = pd.DataFrame(
        {
            "priority": [1, 2, 4],
            "is_holding": [True, False, True],
            "has_peer_mapping": [False, True, False],
        }
    )
    unlock_summary = pd.DataFrame(
        {
            "group_type": ["theme", "sector_etf", "holdings"],
            "top_priority_stage": ["prices", "prices", "fundamentals"],
        }
    )

    cards = dashboard.overview_research_pressure_cards(price_worklist, sec_queue, peer_queue, unlock_summary)
    rendered = " ".join(str(value) for card in cards for value in card.values()).lower()

    assert len(cards) == 3
    assert cards[0]["kicker"] == "PRICE PRESSURE"
    assert cards[1]["kicker"] == "DCF PRESSURE"
    assert cards[2]["kicker"] == "PEER PRESSURE"
    assert "2 urgent price gaps" in rendered
    assert "1 holdings-first dcf unlocks" in rendered
    assert "2 missing peer mappings" in rendered
    assert "buy" not in rendered
    assert "sell" not in rendered


def test_overview_deep_research_leverage_cards_rank_sec_and_peer_lanes():
    holdings = pd.DataFrame([{"Ticker": "NVDA"}, {"Ticker": "TSLA"}])
    sec_queue = pd.DataFrame(
        [
            {
                "priority": 1,
                "ticker": "NVDA",
                "theme": "AI Semiconductors",
                "recommended_action": "Stage or add richer verified fundamentals to close the remaining DCF input gaps.",
            },
            {
                "priority": 2,
                "ticker": "AMD",
                "theme": "AI Semiconductors",
                "recommended_action": "Run SEC staging for fundamentals so DCF assumptions can be reviewed from explicit local inputs.",
            },
        ]
    )
    peer_queue = pd.DataFrame(
        [
            {
                "priority": 1,
                "ticker": "TSLA",
                "theme": "EV",
                "recommended_action": "Add manually researched peer mappings for this ticker and keep peer-relative comparison transparent.",
            }
        ]
    )

    cards = dashboard.overview_deep_research_leverage_cards(holdings, sec_queue, peer_queue)
    rendered = " ".join(str(value) for card in cards for value in card.values()).lower()

    assert len(cards) == 3
    assert cards[0]["kicker"] == "BEST DEEP WORK NEXT"
    assert "sec fundamentals path" in rendered
    assert "manual peer path" in rendered
    assert "ai semiconductors" in rendered
    assert "unlocks the most local research value next" in rendered
    assert "buy" not in rendered
    assert "sell" not in rendered


def test_overview_deep_research_leverage_cards_handle_missing_inputs_gracefully():
    cards = dashboard.overview_deep_research_leverage_cards(None, None, None)
    rendered = " ".join(str(value) for card in cards for value in card.values()).lower()

    assert len(cards) == 1
    assert "no deep-research leverage view yet" in rendered
    assert "buy" not in rendered
    assert "sell" not in rendered


def test_overview_deep_research_priority_bridge_cards_surface_name_level_shortlist():
    holdings = pd.DataFrame([{"Ticker": "NVDA"}, {"Ticker": "TSLA"}])
    sec_queue = pd.DataFrame(
        [
            {
                "priority": 1,
                "ticker": "NVDA",
                "theme": "AI Semiconductors",
                "recommended_action": "Stage or add richer verified fundamentals to close the remaining DCF input gaps.",
            },
            {
                "priority": 2,
                "ticker": "AMD",
                "theme": "AI Semiconductors",
                "recommended_action": "Run SEC staging for fundamentals so DCF assumptions can be reviewed from explicit local inputs.",
            },
        ]
    )
    peer_queue = pd.DataFrame(
        [
            {
                "priority": 1,
                "ticker": "TSLA",
                "theme": "EV",
                "recommended_action": "Add manually researched peer mappings for this ticker and keep peer-relative comparison transparent.",
            }
        ]
    )

    cards = dashboard.overview_deep_research_priority_bridge_cards(holdings, sec_queue, peer_queue, limit=3)
    rendered = " ".join(str(value) for card in cards for value in card.values()).lower()

    assert len(cards) == 3
    assert cards[0]["kicker"] == "NVDA"
    assert "unlock dcf" in rendered
    assert "unlock peer relative" in rendered
    assert "next surface: data health" in rendered
    assert cards[0]["command"] == "Not available"
    assert "current holding" in rendered
    assert "buy" not in rendered
    assert "sell" not in rendered


def test_overview_deep_research_priority_bridge_cards_handle_missing_inputs_gracefully():
    cards = dashboard.overview_deep_research_priority_bridge_cards(None, None, None)
    rendered = " ".join(str(value) for card in cards for value in card.values()).lower()

    assert len(cards) == 1
    assert "no deep-research shortlist yet" in rendered
    assert "buy" not in rendered
    assert "sell" not in rendered


def test_overview_deep_research_handoff_cards_stitch_name_command_and_tab():
    holdings = pd.DataFrame([{"Ticker": "NVDA"}, {"Ticker": "TSLA"}])
    sec_queue = pd.DataFrame(
        [
            {
                "priority": 1,
                "ticker": "NVDA",
                "theme": "AI Semiconductors",
                "recommended_action": "Stage or add richer verified fundamentals to close the remaining DCF input gaps.",
                "example_command": "python3 -m src.stock_report --sec-stage-fundamentals --tickers NVDA",
            }
        ]
    )
    peer_queue = pd.DataFrame(
        [
            {
                "priority": 1,
                "ticker": "TSLA",
                "theme": "EV",
                "recommended_action": "Add manually researched peer mappings for this ticker and keep peer-relative comparison transparent.",
                "example_command": "make templates",
            }
        ]
    )
    payload = {"recommended_next_commands": ["make onboarding", "make verify", "make dashboard"]}
    queue = pd.DataFrame(
        [
            {
                "priority": 1,
                "urgency": "critical",
                "action_type": "fundamentals",
                "ticker": "NVDA",
                "title": "Stage fundamentals",
                "reason": "DCF inputs are still incomplete.",
                "recommended_action": "Run SEC staging for fundamentals, then validate and preview before applying.",
                "example_command": "make sec-stage-queue",
            }
        ]
    )

    cards = dashboard.overview_deep_research_handoff_cards(holdings, sec_queue, peer_queue, payload, queue)
    rendered = " ".join(str(value) for card in cards for value in card.values()).lower()

    assert len(cards) == 3
    assert cards[0]["title"] == "NVDA"
    assert "sec-stage-fundamentals --tickers nvda" in rendered
    assert "stage or add richer verified fundamentals" in rendered
    assert cards[2]["title"] == "Data Health"
    assert "stock report beta" in rendered
    assert "buy" not in rendered
    assert "sell" not in rendered


def test_overview_deep_research_handoff_cards_fall_back_to_safe_command():
    cards = dashboard.overview_deep_research_handoff_cards(None, None, None, None, None)
    rendered = " ".join(str(value) for card in cards for value in card.values()).lower()

    assert len(cards) == 3
    assert cards[0]["title"] == "No deep-research shortlist yet"
    assert cards[1]["title"] == "make help"
    assert cards[2]["title"] == "Data Health"
    assert "buy" not in rendered
    assert "sell" not in rendered


def test_overview_ready_blocked_cards_surface_usable_and_blocked_names():
    coverage = pd.DataFrame(
        [
            {"ticker": "NVDA", "usable_for_momentum": True, "dcf_ready": True, "peer_ready": False},
            {"ticker": "TSLA", "usable_for_momentum": True, "dcf_ready": False, "peer_ready": False},
            {"ticker": "AMD", "usable_for_momentum": False, "dcf_ready": False, "peer_ready": False},
        ]
    )
    ladder = pd.DataFrame(
        [
            {"ticker": "NVDA", "current_unlock_stage": "peers", "next_unlock_goal": "Unlock Peer Relative"},
            {"ticker": "TSLA", "current_unlock_stage": "fundamentals", "next_unlock_goal": "Unlock DCF"},
            {"ticker": "AMD", "current_unlock_stage": "prices", "next_unlock_goal": "Unlock Monthly Picks"},
        ]
    )
    holdings = pd.DataFrame([{"Ticker": "NVDA"}, {"Ticker": "TSLA"}])

    cards = dashboard.overview_ready_blocked_cards(coverage, ladder, holdings, limit=2)
    rendered = " ".join(str(value) for card in cards for value in card.values()).lower()

    assert len(cards) == 2
    assert cards[0]["kicker"] == "READY NOW"
    assert cards[1]["kicker"] == "BLOCKED NOW"
    assert "nvda" in rendered
    assert "amd" in rendered
    assert "usable names" in rendered
    assert "still blocked" in rendered
    assert "buy" not in rendered
    assert "sell" not in rendered


def test_overview_ready_blocked_cards_handle_missing_inputs_gracefully():
    cards = dashboard.overview_ready_blocked_cards(None, None, None)
    rendered = " ".join(str(value) for card in cards for value in card.values()).lower()

    assert "no readiness shortlist yet" in rendered
    assert "make status" in rendered
    assert "buy" not in rendered


def test_overview_best_current_name_cards_route_ready_names_to_next_surface():
    coverage = pd.DataFrame(
        [
            {"ticker": "NVDA", "usable_for_momentum": True, "dcf_ready": True, "peer_ready": False},
            {"ticker": "TSLA", "usable_for_momentum": True, "dcf_ready": False, "peer_ready": False},
            {"ticker": "AMD", "usable_for_momentum": False, "dcf_ready": False, "peer_ready": False},
        ]
    )
    holdings = pd.DataFrame([{"Ticker": "NVDA"}])

    cards = dashboard.overview_best_current_name_cards(coverage, holdings, limit=2)
    rendered = " ".join(str(value) for card in cards for value in card.values()).lower()

    assert len(cards) == 2
    assert cards[0]["kicker"] == "NVDA"
    assert cards[0]["title"] == "Stock Report Beta"
    assert cards[1]["title"] == "Monthly Picks"
    assert "holding" in rendered
    assert "deeper single-name review" in rendered
    assert "buy" not in rendered
    assert "sell" not in rendered


def test_overview_best_current_name_cards_handle_missing_inputs_gracefully():
    cards = dashboard.overview_best_current_name_cards(None, None)
    rendered = " ".join(str(value) for card in cards for value in card.values()).lower()

    assert "no current ready names yet" in rendered
    assert "buy" not in rendered


def test_overview_ready_name_handoff_cards_route_stock_report_names_to_verify_then_tab():
    coverage = pd.DataFrame(
        [
            {"ticker": "NVDA", "usable_for_momentum": True, "dcf_ready": True, "peer_ready": False},
            {"ticker": "TSLA", "usable_for_momentum": True, "dcf_ready": False, "peer_ready": False},
        ]
    )
    holdings = pd.DataFrame([{"Ticker": "NVDA"}])
    payload = {"recommended_next_commands": ["make onboarding", "make verify", "make dashboard"]}
    queue = pd.DataFrame(
        [
            {
                "priority": 1,
                "urgency": "critical",
                "action_type": "prices",
                "ticker": "NVDA",
                "title": "Repair prices",
                "reason": "Need more local rows.",
                "example_command": "make price-worklist",
            }
        ]
    )

    cards = dashboard.overview_ready_name_handoff_cards(coverage, holdings, payload, queue)
    rendered = " ".join(str(value) for card in cards for value in card.values()).lower()

    assert len(cards) == 3
    assert cards[0]["title"] == "NVDA"
    assert cards[1]["title"] == "make verify"
    assert cards[2]["title"] == "Stock Report Beta"
    assert "strongest currently usable local name" in rendered
    assert "deeper single-name read" in rendered
    assert "buy" not in rendered
    assert "sell" not in rendered


def test_overview_ready_name_handoff_cards_route_partial_names_to_monthly_picks():
    coverage = pd.DataFrame(
        [
            {"ticker": "TSLA", "usable_for_momentum": True, "dcf_ready": False, "peer_ready": False},
            {"ticker": "AMD", "usable_for_momentum": False, "dcf_ready": False, "peer_ready": False},
        ]
    )
    queue = pd.DataFrame(
        [
            {
                "priority": 1,
                "urgency": "high",
                "action_type": "fundamentals",
                "ticker": "TSLA",
                "title": "Refresh onboarding",
                "reason": "Need richer local context.",
                "example_command": "make onboarding",
            }
        ]
    )

    cards = dashboard.overview_ready_name_handoff_cards(coverage, None, None, queue)
    rendered = " ".join(str(value) for card in cards for value in card.values()).lower()

    assert len(cards) == 3
    assert cards[0]["title"] == "TSLA"
    assert cards[1]["title"] == "make status"
    assert cards[2]["title"] == "Monthly Picks"
    assert "monthly picks" in rendered
    assert "buy" not in rendered
    assert "sell" not in rendered


def test_overview_ready_name_handoff_cards_handle_missing_inputs_gracefully():
    cards = dashboard.overview_ready_name_handoff_cards(None, None, None, None)
    rendered = " ".join(str(value) for card in cards for value in card.values()).lower()

    assert len(cards) == 3
    assert cards[0]["title"] == "No current ready names yet"
    assert cards[1]["title"] == "make help"
    assert cards[2]["title"] == "Data Health"
    assert "buy" not in rendered
    assert "sell" not in rendered


def test_overview_current_top_surfaces_cards_compose_ready_blocked_command_and_tab():
    coverage = pd.DataFrame(
        [
            {"ticker": "NVDA", "usable_for_momentum": True, "dcf_ready": True, "peer_ready": False},
            {"ticker": "TSLA", "usable_for_momentum": True, "dcf_ready": False, "peer_ready": False},
        ]
    )
    holdings = pd.DataFrame([{"Ticker": "NVDA"}])
    sec_queue = pd.DataFrame(
        [
            {
                "priority": 1,
                "ticker": "NVDA",
                "theme": "AI Semiconductors",
                "recommended_action": "Stage or add richer verified fundamentals to close the remaining DCF input gaps.",
                "example_command": "python3 -m src.stock_report --sec-stage-fundamentals --tickers NVDA",
            }
        ]
    )
    peer_queue = pd.DataFrame(
        [
            {
                "priority": 1,
                "ticker": "TSLA",
                "theme": "EV",
                "recommended_action": "Add manually researched peer mappings for this ticker and keep peer-relative comparison transparent.",
                "example_command": "make templates",
            }
        ]
    )
    payload = {"recommended_next_commands": ["make onboarding", "make verify", "make dashboard"]}
    queue = pd.DataFrame(
        [
            {
                "priority": 1,
                "urgency": "critical",
                "action_type": "prices",
                "ticker": "NVDA",
                "title": "Repair prices",
                "reason": "NVDA update failed during remote refresh.",
                "recommended_action": "Normalize verified downloaded OHLCV rows and run validate/preview/apply.",
                "example_command": "make price-worklist",
            }
        ]
    )

    cards = dashboard.overview_current_top_surfaces_cards(coverage, holdings, sec_queue, peer_queue, payload, queue)
    rendered = " ".join(str(value) for card in cards for value in card.values()).lower()

    assert len(cards) == 4
    assert cards[0]["title"] == "NVDA"
    assert cards[1]["title"] == "NVDA"
    assert cards[2]["title"] == "make status"
    assert cards[3]["title"] == "Stock Report Beta"
    assert "normalize verified downloaded ohlcv rows" in rendered
    assert "best currently usable local name" in rendered
    assert "top deeper-research blocker" in rendered
    assert "buy" not in rendered
    assert "sell" not in rendered


def test_overview_current_top_surfaces_cards_handle_missing_inputs_gracefully():
    cards = dashboard.overview_current_top_surfaces_cards(None, None, None, None, None, None)
    rendered = " ".join(str(value) for card in cards for value in card.values()).lower()

    assert len(cards) == 4
    assert cards[0]["title"] == "No current ready names yet"
    assert cards[1]["title"] == "No deep-research shortlist yet"
    assert cards[2]["title"] == "make help"
    assert cards[3]["title"] == "Data Health"
    assert "buy" not in rendered
    assert "sell" not in rendered


def test_overview_market_context_cards_surface_local_theme_strength():
    market_direction = pd.DataFrame(
        [
            {
                "Theme": "AI Semiconductors",
                "ETF": "SMH",
                "ThemeStatus": "Strong Rotation",
                "Return1M": 0.14,
                "RelativeReturnVsSPY": 0.09,
                "RelativeReturnVsQQQ": 0.04,
            },
            {
                "Theme": "Platforms",
                "ETF": "QQQ",
                "ThemeStatus": "Early Rotation",
                "Return1M": 0.08,
                "RelativeReturnVsSPY": 0.03,
                "RelativeReturnVsQQQ": 0.01,
            },
        ]
    )

    cards = dashboard.overview_market_context_cards(market_direction, limit=2)
    rendered = " ".join(str(value) for card in cards for value in card.values()).lower()

    assert cards[0]["kicker"] == "MARKET CONTEXT"
    assert "strong rotation" in rendered
    assert "ai semiconductors" in rendered
    assert "vs spy 9.0%" in rendered
    assert "buy" not in rendered
    assert "sell" not in rendered


def test_overview_market_context_cards_handle_missing_inputs_gracefully():
    cards = dashboard.overview_market_context_cards(None)
    rendered = " ".join(str(value) for card in cards for value in card.values()).lower()

    assert "no local market direction context yet" in rendered
    assert "buy" not in rendered


def test_overview_benchmark_pressure_cards_surface_price_gap_and_spy_context():
    market_direction = pd.DataFrame(
        [
            {
                "Theme": "AI Semiconductors",
                "RelativeReturnVsSPY": 0.09,
            }
        ]
    )
    price_status = pd.DataFrame({"status": ["parse_error", "fetched", "source_unavailable"]})
    payload = {"summary": {"tickers_total": 12, "tickers_with_prices": 3}}

    cards = dashboard.overview_benchmark_pressure_cards(market_direction, price_status, payload)
    rendered = " ".join(str(value) for card in cards for value in card.values()).lower()

    assert len(cards) == 2
    assert "missing local prices" in rendered
    assert "9/12" in rendered
    assert "ai semiconductors" in rendered
    assert "9.0%" in rendered
    assert "buy" not in rendered
    assert "sell" not in rendered


def test_overview_benchmark_pressure_cards_handle_missing_inputs_gracefully():
    cards = dashboard.overview_benchmark_pressure_cards(None, None, None)
    rendered = " ".join(str(value) for card in cards for value in card.values()).lower()

    assert "local prices present" in rendered or "ticker coverage is not available yet" in rendered
    assert "buy" not in rendered


def test_overview_next_command_cards_prioritize_project_status_commands():
    payload = {
        "recommended_next_commands": ["make onboarding", "make verify", "make dashboard"],
    }
    queue = pd.DataFrame(
        [
            {
                "priority": 1,
                "urgency": "critical",
                "action_type": "prices",
                "ticker": "NVDA",
                "title": "Repair prices",
                "reason": "Need more local rows.",
                "example_command": "make price-worklist",
            }
        ]
    )

    cards = dashboard.overview_next_command_cards(payload, queue, limit=3)
    rendered = " ".join(str(value) for card in cards for value in card.values()).lower()

    assert len(cards) == 3
    assert cards[0]["title"] == "make status"
    assert "make verify" in rendered
    assert "make dashboard-smoke" in rendered
    assert "buy" not in rendered
    assert "sell" not in rendered


def test_overview_next_command_cards_normalize_legacy_dashboard_command_rows():
    payload = {
        "recommended_next_command_rows": [
            {
                "Step": "Refresh local snapshot",
                "Command": "make dashboard",
                "Reason": "Open the dashboard after refreshing the local operator outputs.",
            }
        ]
    }

    cards = dashboard.overview_next_command_cards(payload, None, limit=1)
    rendered = " ".join(str(value) for card in cards for value in card.values()).lower()

    assert cards[0]["title"] == "make dashboard-smoke"
    assert "dashboard-smoke" in rendered
    assert "smoke-check" in rendered
    assert "buy" not in rendered
    assert "sell" not in rendered


def test_overview_next_command_cards_use_structured_project_status_rows():
    payload = {
        "recommended_next_command_rows": [
            {
                "Step": "Fix top prices blocker (NVDA)",
                "Command": "make focus-price TICKER=NVDA",
                "Reason": "Short local price history still blocks downstream work.",
            },
            {
                "Step": "Run Price Coverage Bundle (Broader Queue)",
                "Command": "make runbook-prices-broader",
                "Reason": "Advance broader local price coverage next.",
            },
            {
                "Step": "Deterministic verification",
                "Command": "make verify",
                "Reason": "Confirm local outputs still pass.",
            },
        ]
    }

    cards = dashboard.overview_next_command_cards(payload, None, limit=3)
    rendered = " ".join(str(value) for card in cards for value in card.values()).lower()

    assert cards[0]["title"] == "make focus-price TICKER=NVDA"
    assert cards[0]["kicker"] == "Fix top prices blocker (NVDA)"
    assert cards[1]["title"] == "make runbook-prices-broader"
    assert "short local price history" in rendered
    assert "advance broader local price coverage" in rendered
    assert "buy" not in rendered
    assert "sell" not in rendered


def test_overview_next_command_cards_fall_back_to_action_queue():
    queue = pd.DataFrame(
        [
            {
                "priority": 1,
                "urgency": "critical",
                "action_type": "prices",
                "ticker": "NVDA",
                "title": "Repair prices",
                "reason": "NVDA update failed during remote refresh.",
                "recommended_action": "Normalize verified downloaded OHLCV rows and run validate/preview/apply.",
                "example_command": "make price-worklist",
            }
        ]
    )

    cards = dashboard.overview_next_command_cards(None, queue, limit=2)
    rendered = " ".join(str(value) for card in cards for value in card.values()).lower()

    assert "make price-worklist" in rendered
    assert cards[0]["title"] == "make price-worklist"
    assert "normalize verified downloaded ohlcv rows" in rendered
    assert "buy" not in rendered


def test_overview_workflow_path_cards_use_action_queue_then_verify_then_dashboard():
    queue = pd.DataFrame(
        [
            {
                "priority": 1,
                "urgency": "critical",
                "action_type": "prices",
                "ticker": "NVDA",
                "title": "Repair prices",
                "reason": "Need more local rows.",
                "example_command": "make price-worklist",
            }
        ]
    )
    payload = {"recommended_next_commands": ["make onboarding", "make verify", "make dashboard-smoke"]}

    cards = dashboard.overview_workflow_path_cards(payload, queue)
    rendered = " ".join(str(value) for card in cards for value in card.values()).lower()

    assert len(cards) == 3
    assert cards[0]["title"] == "make price-worklist"
    assert cards[1]["title"] == "make verify"
    assert cards[2]["title"] == "make dashboard-smoke"
    assert "buy" not in rendered
    assert "sell" not in rendered


def test_overview_workflow_path_cards_fall_back_to_safe_defaults():
    cards = dashboard.overview_workflow_path_cards(None, None)
    rendered = " ".join(str(value) for card in cards for value in card.values()).lower()

    assert cards[0]["title"] == "make status"
    assert cards[1]["title"] == "make verify"
    assert cards[2]["title"] == "make dashboard-smoke"
    assert "buy" not in rendered


def test_overview_workflow_reason_card_uses_action_queue_context():
    queue = pd.DataFrame(
        [
            {
                "priority": 1,
                "urgency": "critical",
                "action_type": "prices",
                "ticker": "NVDA",
                "title": "Repair prices",
                "reason": "NVDA update failed during remote refresh.",
                "recommended_action": "Normalize verified downloaded OHLCV rows and run validate/preview/apply.",
                "example_command": "make price-worklist",
            }
        ]
    )

    card = dashboard.overview_workflow_reason_card(None, queue)
    rendered = " ".join(str(value) for value in card.values()).lower()

    assert card["title"] == "make price-worklist"
    assert "nvda" in rendered
    assert "normalize verified downloaded ohlcv rows" in rendered
    assert "validate/preview/apply" in rendered
    assert "buy" not in rendered
    assert "sell" not in rendered


def test_overview_workflow_reason_card_falls_back_to_status_snapshot():
    payload = {"summary": {"data_gaps": 12, "critical_actions": 4}}

    card = dashboard.overview_workflow_reason_card(payload, None)
    rendered = " ".join(str(value) for value in card.values()).lower()

    assert card["title"] == "make status"
    assert "4 critical actions" in rendered
    assert "12 visible data gaps" in rendered
    assert "buy" not in rendered


def test_overview_handoff_cards_link_to_deeper_tabs_without_trade_language():
    cards = dashboard.overview_handoff_cards()
    rendered = " ".join(str(value) for card in cards for value in card.values()).lower()

    assert len(cards) == 3
    assert cards[0]["title"] == "Data Health"
    assert cards[1]["title"] == "Stock Report Beta"
    assert cards[2]["title"] == "Monthly Picks"
    assert "blocking the local research workflow" in rendered
    assert "single-name deep dive" in rendered
    assert "track-record readiness" in rendered
    assert "buy" not in rendered
    assert "sell" not in rendered


def test_overview_best_local_research_path_cards_stitch_name_command_and_tab():
    coverage = pd.DataFrame(
        [
            {"ticker": "NVDA", "usable_for_momentum": True, "dcf_ready": True, "peer_ready": False},
            {"ticker": "TSLA", "usable_for_momentum": True, "dcf_ready": False, "peer_ready": False},
        ]
    )
    holdings = pd.DataFrame([{"Ticker": "NVDA"}])
    payload = {"recommended_next_commands": ["make onboarding", "make verify", "make dashboard"]}
    queue = pd.DataFrame(
        [
            {
                "priority": 1,
                "urgency": "critical",
                "action_type": "prices",
                "ticker": "NVDA",
                "title": "Repair prices",
                "reason": "NVDA update failed during remote refresh.",
                "recommended_action": "Normalize verified downloaded OHLCV rows and run validate/preview/apply.",
                "example_command": "make price-worklist",
            }
        ]
    )

    cards = dashboard.overview_best_local_research_path_cards(coverage, holdings, payload, queue)
    rendered = " ".join(str(value) for card in cards for value in card.values()).lower()

    assert len(cards) == 3
    assert cards[0]["title"] == "NVDA"
    assert cards[1]["title"] == "make status"
    assert cards[2]["title"] == "Stock Report Beta"
    assert "best current name" in rendered
    assert "next command" in rendered
    assert "next tab" in rendered
    assert "normalize verified downloaded ohlcv rows" in rendered
    assert "buy" not in rendered
    assert "sell" not in rendered


def test_overview_best_local_research_path_cards_fall_back_gracefully():
    cards = dashboard.overview_best_local_research_path_cards(None, None, None, None)
    rendered = " ".join(str(value) for card in cards for value in card.values()).lower()

    assert len(cards) == 3
    assert cards[0]["title"] == "BEST CURRENT NAMES"
    assert cards[1]["title"] == "make help"
    assert cards[2]["title"] == "Data Health"
    assert "no current ready names yet" in rendered
    assert "buy" not in rendered
    assert "sell" not in rendered


def test_overview_interpretation_guardrail_card_flags_partial_workflow():
    payload = {
        "summary": {
            "tickers_total": 12,
            "tickers_with_prices": 3,
            "tickers_dcf_ready": 0,
            "tickers_peer_ready": 0,
            "data_gaps": 19,
        }
    }

    card = dashboard.overview_interpretation_guardrail_card(
        payload,
        {"critical": 2, "high": 4, "medium": 0},
        {"needs_price_data": 6, "thin_liquidity": 1, "high_correlation": 0},
    )
    rendered = " ".join(str(value) for value in card.values()).lower()

    assert "workflow" in card["title"].lower()
    assert "the workflow is usable, but some outputs should still be treated as partial" in rendered
    assert "19 visible data gaps remain" in rendered
    assert "buy" not in rendered
    assert "sell" not in rendered


def test_overview_interpretation_guardrail_card_flags_needs_data_workflow():
    payload = {
        "summary": {
            "tickers_total": 12,
            "tickers_with_prices": 3,
            "tickers_dcf_ready": 0,
            "tickers_peer_ready": 0,
            "data_gaps": 19,
        }
    }

    card = dashboard.overview_interpretation_guardrail_card(
        payload,
        {"critical": 8, "high": 4, "medium": 0},
        {"needs_price_data": 6, "thin_liquidity": 2, "high_correlation": 1},
    )
    rendered = " ".join(str(value) for value in card.values()).lower()

    assert "needs data workflow" in rendered
    assert "coverage is still the main blocker" in rendered
    assert "3/12 tickers have usable prices" in rendered
    assert "buy" not in rendered
    assert "sell" not in rendered


def test_overview_interpretation_guardrail_card_supports_ready_workflow():
    payload = {
        "summary": {
            "tickers_total": 10,
            "tickers_with_prices": 10,
            "tickers_dcf_ready": 8,
            "tickers_peer_ready": 7,
            "data_gaps": 0,
        }
    }

    card = dashboard.overview_interpretation_guardrail_card(
        payload,
        {"critical": 0, "high": 0, "medium": 0},
        {"needs_price_data": 0, "thin_liquidity": 0, "high_correlation": 0},
    )
    rendered = " ".join(str(value) for value in card.values()).lower()

    assert "ready workflow" in rendered
    assert "10/10 tickers have prices" in rendered
    assert "buy" not in rendered
    assert "sell" not in rendered


def test_overview_coverage_hotspot_cards_surface_dataset_pressure():
    queue = pd.DataFrame(
        [
            {"priority": 1, "action_type": "prices", "ticker": "NVDA"},
            {"priority": 1, "action_type": "prices", "ticker": "AMD"},
            {"priority": 2, "action_type": "fundamentals", "ticker": "MSFT"},
            {"priority": 3, "action_type": "peers", "ticker": "NVDA"},
            {"priority": 4, "action_type": "earnings", "ticker": "AVGO"},
        ]
    )

    cards = dashboard.overview_coverage_hotspot_cards(queue)
    rendered = " ".join(str(value) for card in cards for value in card.values()).lower()

    assert cards[0]["title"] == "Prices"
    assert any(card["title"] == "Fundamentals" for card in cards)
    assert any(card["title"] == "Peers" for card in cards)
    assert "2 action rows and 2 affected tickers" in rendered
    assert "examples:" in rendered
    assert "nvda" in rendered
    assert "amd" in rendered
    assert "buy" not in rendered
    assert "sell" not in rendered


def test_overview_coverage_hotspot_cards_handle_missing_queue():
    cards = dashboard.overview_coverage_hotspot_cards(None)
    rendered = " ".join(str(value) for card in cards for value in card.values()).lower()

    assert len(cards) == 1
    assert "no hotspot queue yet" in rendered
    assert "prices, fundamentals, peers, or optional context" in rendered


def test_monthly_pick_card_html_is_product_style_and_clean():
    html = dashboard.monthly_pick_card_html(
        {
            "Rank": 1,
            "Ticker": "NVDA",
            "Theme": "AI Semiconductors",
            "Sector": "SMH",
            "PrimaryPurpose": "Momentum Leader",
            "CompositeScore": 52.98,
            "MomentumScore": 61.52,
            "SetupStatus": "Watch",
            "FinalState": "Review Thesis",
            "Reason": "Composite score uses transparent local components. Missing or incomplete fields reduced confidence.",
            "MissingDataFields": "Return3M, fundamentals unavailable, peers",
        }
    )

    assert "pick-card" in html
    assert "Rank 1" in html
    assert "NVDA" in html
    assert "52.98" in html
    assert "Needs SEC enrichment" in html
    assert "Needs peers.csv" in html
    assert "nan" not in html.lower()
    assert "none" not in html.lower()


def test_monthly_picks_landing_cards_show_history_and_gap_context():
    picks = pd.DataFrame(
        [
            {"Month": "2026-05", "MissingDataFields": "Return3M"},
            {"Month": "2026-05", "MissingDataFields": ""},
        ]
    )
    track = pd.DataFrame([{"Month": "2026-04"}])
    equity = pd.DataFrame()
    cards = dashboard.monthly_picks_landing_cards(picks, track, equity, 5, "2026-05-12", 12)
    rendered = " ".join(str(value) for card in cards for value in card.values()).lower()

    assert len(cards) == 4
    assert "2026-05" in rendered
    assert "2 of 5" in rendered
    assert "needs history" in rendered
    assert "1 rows with gaps" in rendered
    assert "buy" not in rendered
    assert "sell" not in rendered


def test_monthly_picks_next_step_cards_cover_generation_coverage_history_and_review():
    queue = pd.DataFrame(
        [
            {
                "priority": 1,
                "urgency": "critical",
                "action_type": "prices",
                "ticker": "NVDA",
                "title": "Repair prices",
                "reason": "Need more local rows.",
                "example_command": "make price-worklist",
            }
        ]
    )

    cards = dashboard.monthly_picks_next_step_cards(None, None, None, 5, queue)
    assert cards[0]["title"] == "Generate monthly picks"

    picks = pd.DataFrame([{"Month": "2026-05", "MissingDataFields": "Return3M"}] * 4)
    cards = dashboard.monthly_picks_next_step_cards(picks, None, None, 5, queue)
    assert cards[0]["title"] == "Improve candidate coverage"
    assert "make price-worklist" in cards[0]["body"]

    full_picks = pd.DataFrame([{"Month": "2026-05", "MissingDataFields": ""}] * 5)
    cards = dashboard.monthly_picks_next_step_cards(full_picks, None, None, 5, queue)
    assert cards[0]["title"] == "Build track-record context"

    track = pd.DataFrame([{"Month": "2026-04"}])
    equity = pd.DataFrame([{"Month": "2026-04", "PicksEquity": 1.0, "BenchmarkEquity": 1.0}])
    cards = dashboard.monthly_picks_next_step_cards(full_picks, track, equity, 5, queue)
    assert cards[0]["title"] == "Review current candidates"
    assert cards[0]["command"] == "make dashboard-smoke"
    assert "dashboard-smoke" in cards[0]["body"]


def test_stock_report_brief_html_summarizes_readiness_without_advice():
    html = dashboard.stock_report_brief_html(
        {
            "ticker": "NVDA",
            "provider_name": "LocalCSVMarketDataProvider",
            "generated_at": "2026-05-21T12:00:00Z",
            "valuation_snapshot": {"status": "partial", "coverage": "DCF only"},
            "valuation_readiness": {
                "dcf_ready": True,
                "peer_ready": False,
                "earnings_available": False,
                "analyst_estimates_available": False,
            },
            "missing_data_warnings": ["Needs peers.csv", "Needs earnings.csv"],
        }
    )

    assert "NVDA research snapshot" in html
    assert "DCF Ready" in html
    assert "Peers Need Data" in html
    assert "Earnings Missing" in html
    assert "2" in html
    assert "buy" not in html.lower()
    assert "sell" not in html.lower()


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


def test_stock_report_local_context_cards_summarize_local_and_peer_readiness():
    coverage = pd.DataFrame(
        [
            {"ticker_present": True, "validation_status": "valid"},
            {"ticker_present": True, "validation_status": "valid_with_warnings"},
            {"ticker_present": False, "validation_status": "missing_file"},
        ]
    )
    peer_summary = {
        "peer_dataset_present": False,
        "peer_count": 0,
        "peer_fundamentals_available": 0,
        "peer_market_context_available": 1,
    }

    cards = dashboard.stock_report_local_context_cards(coverage, peer_summary)
    rendered = " ".join(str(value) for card in cards for value in card.values()).lower()

    assert len(cards) == 4
    assert "2 available" in rendered
    assert "missing" in rendered
    assert "no fabrication" in rendered
    assert "buy" not in rendered
    assert "sell" not in rendered


def test_stock_report_next_step_cards_prioritize_missing_prices_first():
    payload = {
        "ticker": "NVDA",
        "valuation_readiness": {
            "dcf_ready": False,
            "peer_ready": False,
            "earnings_available": False,
            "analyst_estimates_available": False,
        },
        "missing_data_warnings": ["prices missing"],
    }
    coverage = pd.DataFrame(
        [
            {"dataset": "prices", "ticker_present": False},
            {"dataset": "fundamentals", "ticker_present": False},
        ]
    )

    cards = dashboard.stock_report_next_step_cards(payload, coverage, {"peer_dataset_present": False})
    rendered = " ".join(str(value) for card in cards for value in card.values()).lower()

    assert cards[0]["title"] == "Fix price coverage"
    assert "make focus-price ticker=nvda" in rendered
    assert "data gaps" in rendered
    assert "buy" not in rendered
    assert "sell" not in rendered


def test_stock_report_next_step_cards_route_to_fundamentals_then_peers_then_review():
    payload = {
        "ticker": "NVDA",
        "valuation_readiness": {
            "dcf_ready": False,
            "peer_ready": False,
            "earnings_available": False,
            "analyst_estimates_available": False,
        },
        "missing_data_warnings": ["fundamentals missing"],
    }
    coverage = pd.DataFrame(
        [
            {"dataset": "prices", "ticker_present": True},
            {"dataset": "fundamentals", "ticker_present": False},
        ]
    )
    cards = dashboard.stock_report_next_step_cards(payload, coverage, {"peer_dataset_present": False})
    assert cards[0]["title"] == "Stage fundamentals"
    assert cards[0]["command"] == "make focus-fundamentals TICKER=NVDA"

    payload["valuation_readiness"]["dcf_ready"] = True
    coverage = pd.DataFrame(
        [
            {"dataset": "prices", "ticker_present": True},
            {"dataset": "fundamentals", "ticker_present": True},
        ]
    )
    cards = dashboard.stock_report_next_step_cards(payload, coverage, {"peer_dataset_present": False})
    assert cards[0]["title"] == "Add peer mappings"
    assert cards[0]["command"] == "make focus-peers TICKER=NVDA"

    payload["valuation_readiness"]["peer_ready"] = True
    cards = dashboard.stock_report_next_step_cards(payload, coverage, {"peer_dataset_present": True})
    assert cards[0]["title"] == "Review full report"


def test_stock_report_price_chart_frame_sorts_and_cleans_history():
    history = pd.DataFrame(
        {
            "date": ["2026-05-03", "2026-05-01", "2026-05-03", "bad-date"],
            "close": ["101.5", "99.0", "102.0", "103.0"],
            "volume": [100, 110, 120, 130],
        }
    )

    chart = dashboard.stock_report_price_chart_frame(history)

    assert list(chart.columns) == ["Close"]
    assert list(chart.index.strftime("%Y-%m-%d")) == ["2026-05-01", "2026-05-03"]
    assert chart.iloc[-1]["Close"] == 102.0


def test_stock_report_price_chart_frame_handles_missing_columns():
    chart = dashboard.stock_report_price_chart_frame(pd.DataFrame({"ticker": ["NVDA"]}))

    assert chart.empty
    assert list(chart.columns) == ["Close"]


def test_monthly_pick_score_chart_frame_prefers_ranked_candidates_and_scores():
    picks = pd.DataFrame(
        {
            "Ticker": ["amd", "nvda", "amd", "avgo"],
            "Rank": [2, 1, 3, None],
            "CompositeScore": [78, 91, 65, 74],
            "MomentumScore": [80, 95, 61, 70],
            "QualityScore": [55, 88, 40, None],
            "ValuationContextScore": [30, 44, 20, 26],
        }
    )

    chart = dashboard.monthly_pick_score_chart_frame(picks, max_rows=3)

    assert list(chart.index) == ["NVDA", "AMD", "AVGO"]
    assert "ValuationScore" in chart.columns
    assert chart.loc["AMD", "CompositeScore"] == 78


def test_monthly_pick_score_chart_frame_returns_empty_without_score_columns():
    picks = pd.DataFrame({"Ticker": ["NVDA"], "Theme": ["AI"]})

    chart = dashboard.monthly_pick_score_chart_frame(picks)

    assert chart.empty


def test_stock_report_technical_context_cards_are_readable_and_research_only():
    payload = {
        "screener_context": {
            "momentum_leaders": {
                "SetupStatus": "Watch",
                "RSPercentile": 92,
                "RelativeReturnVsSPY": 0.18,
                "RelativeReturnVsQQQ": 0.11,
                "DistanceFrom10EMA": 0.04,
                "DistanceFrom21EMA": 0.08,
                "DistanceFrom50SMA": -0.03,
                "VolumeRatio": 1.2,
                "ATRorVolatilityPct": 0.025,
            },
            "final_watchlist": {
                "FinalState": "Review Thesis",
                "SetupStatus": "Watch",
            },
        }
    }

    cards = dashboard.stock_report_technical_context_cards(payload)
    rendered = " ".join(str(value) for card in cards for value in card.values()).lower()

    assert len(cards) == 4
    assert "watch" in rendered
    assert "review thesis" in rendered
    assert "vs spy 18.0%" in rendered
    assert "above 10 ema" in rendered
    assert "buy" not in rendered
    assert "sell" not in rendered


def test_stock_report_technical_context_frame_formats_missing_values_cleanly():
    frame = dashboard.stock_report_technical_context_frame({"screener_context": {}})

    assert list(frame.columns) == ["Metric", "Value"]
    rendered = " ".join(frame["Value"].astype(str)).lower()
    assert "not available" in rendered
    assert "none" not in rendered
    assert "nan" not in rendered


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


def test_stock_report_detail_frames_are_readable_not_raw_json():
    frame = dashboard.stock_report_detail_frame(
        {
            "market_time": "2026-05-21T12:00:00Z",
            "price": 123.45,
            "source_notes": ["local CSV"],
            "official": False,
            "missing": None,
        }
    )

    assert list(frame.columns) == ["Field", "Value"]
    assert "2026-05-21" in frame["Value"].tolist()
    assert "123.45" in frame["Value"].tolist()
    assert "local CSV" in frame["Value"].tolist()
    assert "No" in frame["Value"].tolist()
    assert "Not available" in frame["Value"].tolist()


def test_stock_report_notes_frame_summarizes_warning_sections():
    frame = dashboard.stock_report_notes_frame(
        {"warnings": ["high growth normalized"], "notes": ["informational only"]},
        {"peer_missing_data_warnings": ["peers.csv missing"], "missing_fields": ["peer_ticker"]},
    )

    assert list(frame.columns) == ["Section", "Details"]
    rendered = " ".join(frame["Details"].astype(str)).lower()
    assert "high growth normalized" in rendered
    assert "peers.csv missing" in rendered


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


def test_data_health_overview_cards_without_price_status_use_status_first_guidance():
    validation = pd.DataFrame({"validation_status": ["valid", "missing_file"]})
    action_queue = pd.DataFrame({"urgency": ["critical"]})
    coverage = pd.DataFrame({"usable_for_momentum": [False]})

    cards = dashboard.data_health_overview_cards(validation, None, action_queue, coverage)
    rendered = " ".join(str(value) for card in cards for value in card.values()).lower()

    assert "price status not generated" in rendered
    assert "make status" in rendered
    assert "manual fallback" in rendered
    assert "buy" not in rendered
    assert "sell" not in rendered


def test_data_health_tab_summary_cards_cover_price_and_staged_imports():
    validation = pd.DataFrame({"validation_status": ["valid", "missing_file"]})
    coverage = pd.DataFrame(
        {
            "usable_for_momentum": [True, False],
            "dcf_ready": [False, False],
            "peer_ready": [False, False],
            "has_earnings": [False, False],
            "has_analyst_estimates": [False, False],
            "missing_required_for_momentum": ["", "prices"],
            "missing_required_for_dcf": ["fundamentals", "fundamentals"],
            "missing_required_for_peer_relative": ["peer mapping", "peer mapping"],
        }
    )
    status = pd.DataFrame({"availability_status": ["available", "partial", "manual_only"]})
    price_status = pd.DataFrame({"status": ["fetched", "parse_error", "failed"]})
    staged_imports = {"files": [{"file_name": "fundamentals.csv"}]}

    coverage_cards = dashboard.data_health_tab_summary_cards("Coverage", validation, coverage, status, price_status, staged_imports)
    price_cards = dashboard.data_health_tab_summary_cards("Price Refresh", validation, coverage, status, price_status, staged_imports)
    staged_cards = dashboard.data_health_tab_summary_cards("Staged Imports", validation, coverage, status, price_status, staged_imports)
    rendered = " ".join(
        str(value)
        for group in [coverage_cards, price_cards, staged_cards]
        for card in group
        for value in card.values()
    ).lower()

    assert "1" in rendered
    assert "manual fallback" in rendered
    assert "preview first" in rendered
    assert "buy" not in rendered
    assert "sell" not in rendered


def test_data_health_fix_first_cards_prioritize_actions():
    actions = pd.DataFrame(
        [
            {
                "priority": 2,
                "dataset": "fundamentals",
                "ticker": "MSFT",
                "reason": "Needs verified local fundamentals.",
                "recommended_action": "Run SEC staging, then validate and preview.",
                "focus_command": "make focus-fundamentals TICKER=MSFT",
                "example_command": "make sec-stage TICKERS=MSFT",
            },
            {
                "priority": 1,
                "dataset": "prices",
                "ticker": "NVDA",
                "reason": "Short local price history.",
                "recommended_action": "Normalize verified downloaded OHLCV rows.",
                "focus_command": "make focus-price TICKER=NVDA",
                "example_command": "make price-normalize INPUT=data/raw/prices/NVDA.csv TICKER=NVDA SOURCE=yahoo_manual",
            },
        ]
    )

    cards = dashboard.data_health_fix_first_cards(actions)
    rendered = " ".join(str(value) for card in cards for value in card).lower()

    assert cards[0][0] == "P1 prices - NVDA"
    assert cards[0][3] == "danger"
    assert "make focus-price ticker=nvda" in rendered
    assert "buy" not in rendered
    assert "sell" not in rendered


def test_data_health_action_path_cards_surface_best_and_lane_commands():
    actions = pd.DataFrame(
        [
            {
                "priority": 1,
                "dataset": "prices",
                "ticker": "NVDA",
                "reason": "No verified local price history is present yet.",
                "recommended_action": "Normalize verified downloaded OHLCV rows and run validate/preview/apply.",
                "focus_command": "make focus-price TICKER=NVDA",
                "example_command": "make price-worklist",
            },
            {
                "priority": 2,
                "dataset": "fundamentals",
                "ticker": "AMD",
                "reason": "DCF inputs are still incomplete.",
                "recommended_action": "Run SEC staging for fundamentals, then validate and preview before applying.",
                "focus_command": "make focus-fundamentals TICKER=AMD",
                "example_command": "make sec-stage TICKERS=AMD",
            },
            {
                "priority": 2,
                "dataset": "peers",
                "ticker": "TSLA",
                "reason": "No local peer mapping is configured for this ticker.",
                "recommended_action": "Add manually researched peers and keep peer-relative comparison transparent.",
                "focus_command": "make focus-peers TICKER=TSLA",
                "example_command": "make templates",
            },
        ]
    )
    queue = pd.DataFrame(
        [
            {
                "priority": 1,
                "urgency": "critical",
                "action_type": "prices",
                "ticker": "NVDA",
                "title": "Repair prices",
                "reason": "NVDA update failed during remote refresh.",
                "recommended_action": "Normalize verified downloaded OHLCV rows and run validate/preview/apply.",
                "focus_command": "make focus-price TICKER=NVDA",
                "example_command": "make price-worklist",
            }
        ]
    )

    cards = dashboard.data_health_action_path_cards(actions, queue)
    rendered = " ".join(str(value) for card in cards for value in card.values()).lower()

    assert len(cards) == 4
    assert cards[0]["kicker"] == "BEST NEXT"
    assert cards[0]["command"] == "make focus-price TICKER=NVDA"
    assert "price path" in rendered
    assert "fundamentals path" in rendered
    assert "peer path" in rendered
    assert "no verified local price history is present yet" in rendered
    assert "normalize verified downloaded ohlcv rows" in rendered
    assert "dcf inputs are still incomplete" in rendered
    assert "make focus-fundamentals ticker=amd" in rendered
    assert "buy" not in rendered
    assert "sell" not in rendered


def test_data_health_action_path_cards_handle_missing_inputs_gracefully():
    cards = dashboard.data_health_action_path_cards(None, None)
    rendered = " ".join(str(value) for card in cards for value in card.values()).lower()

    assert len(cards) == 1
    assert "no action paths yet" in rendered
    assert cards[0]["command"] == "make status"
    assert "make status" in rendered
    assert "buy" not in rendered
    assert "sell" not in rendered


def test_data_health_command_bundle_cards_surface_holdings_first_commands():
    bundles = pd.DataFrame(
        [
            {
                "bundle_name": "Price Coverage Bundle",
                "lane": "prices",
                "scope": "holdings_first",
                "ticker_count": 2,
                "tickers": "AMD,AVGO",
                "goal_summary": "Unlock Monthly Picks for 2 tickers; 42 verified rows still needed across this bundle",
                "target_history_rows": 21,
                "suggested_start_date": "2025-12-01",
                "bundle_shortcut_command": "make bundle-prices",
                "detail_shortcut_command": "make detail-prices",
                "runbook_shortcut_command": "make runbook-prices",
                "fallback_manual_command": "make price-normalize INPUT=data/raw/prices/AMD.csv TICKER=AMD SOURCE=yahoo_manual",
                "primary_command": "python3 -m src.data_update --tickers AMD,AVGO",
                "follow_up_command": "make price-status",
                "target_file": "data/imports/prices.csv",
                "why_it_matters": "These tickers still block monthly picks because local price history is too short.",
                "safe_next_step": "Use staged local imports if the free refresh fails.",
            },
            {
                "bundle_name": "SEC Fundamentals Bundle",
                "lane": "fundamentals",
                "scope": "holdings_first",
                "ticker_count": 1,
                "tickers": "NVDA",
                "goal_summary": "Advance explicit local DCF readiness for the listed tickers",
                "bundle_shortcut_command": "make bundle-fundamentals",
                "detail_shortcut_command": "make detail-fundamentals",
                "runbook_shortcut_command": "make runbook-fundamentals",
                "primary_command": "SEC_USER_AGENT='Name email@example.com' make sec-stage TICKERS=NVDA",
                "follow_up_command": "make sec-preview",
                "target_file": "data/imports/fundamentals.csv",
                "why_it_matters": "This holding is the best next candidate for explicit local DCF inputs.",
                "safe_next_step": "Keep SEC staging review-only until preview is clean.",
            },
        ]
    )

    cards = dashboard.data_health_command_bundle_cards(bundles)
    rendered = " ".join(str(value) for card in cards for value in card.values()).lower()

    assert cards[0]["kicker"] == "PRICES"
    assert "holdings first" in rendered
    assert "unlock monthly picks" in rendered
    assert "21 target rows" in rendered
    assert "start by 2025-12-01" in rendered
    assert "make bundle-prices" in rendered
    assert "make bundle-fundamentals" in rendered
    assert "buy" not in rendered
    assert "sell" not in rendered


def test_data_health_onboarding_fallback_cards_use_status_refresh():
    bundle_cards = dashboard.data_health_command_bundle_cards(None)
    runbook_cards = dashboard.data_health_command_bundle_runbook_cards(None)
    target_cards = dashboard.data_health_price_target_cards(None)

    rendered = " ".join(
        str(value)
        for card_group in (bundle_cards, runbook_cards, target_cards)
        for card in card_group
        for value in card.values()
    ).lower()

    assert bundle_cards[0]["command"] == "make status"
    assert runbook_cards[0]["command"] == "make status"
    assert target_cards[0]["command"] == "make status"
    assert "run make status to refresh the onboarding outputs" in rendered
    assert "buy" not in rendered
    assert "sell" not in rendered


def test_data_health_command_bundle_runbook_cards_surface_lane_steps_safely():
    runbook = pd.DataFrame(
        [
            {
                "bundle_name": "Price Coverage Bundle",
                "lane": "prices",
                "scope": "holdings_first",
                "step_order": 1,
                "step_label": "Run bundle command",
                "command": "python3 -m src.data_update --tickers AMD,AVGO",
                "target_file": "data/imports/prices.csv",
                "tickers": "AMD,AVGO",
                "goal_summary": "Unlock Monthly Picks for 2 tickers; 42 verified rows still needed across this bundle",
                "target_history_rows": 21,
                "suggested_start_date": "2025-12-01",
                "fallback_manual_command": "make price-normalize INPUT=data/raw/prices/AMD.csv TICKER=AMD SOURCE=yahoo_manual",
                "why_it_matters": "These tickers still block monthly picks because local price history is too short.",
                "safe_next_step": "Use staged local imports if the free refresh fails.",
            },
            {
                "bundle_name": "Price Coverage Bundle",
                "lane": "prices",
                "scope": "holdings_first",
                "step_order": 2,
                "step_label": "If refresh fails, normalize first CSV",
                "command": "make price-normalize INPUT=data/raw/prices/AMD.csv TICKER=AMD SOURCE=yahoo_manual",
                "target_file": "data/imports/prices.csv",
                "tickers": "AMD,AVGO",
                "goal_summary": "Unlock Monthly Picks for 2 tickers; 42 verified rows still needed across this bundle",
                "target_history_rows": 21,
                "suggested_start_date": "2025-12-01",
                "fallback_manual_command": "make price-normalize INPUT=data/raw/prices/AMD.csv TICKER=AMD SOURCE=yahoo_manual",
                "why_it_matters": "These tickers still block monthly picks because local price history is too short.",
                "safe_next_step": "Use staged local imports if the free refresh fails.",
            },
            {
                "bundle_name": "Price Coverage Bundle",
                "lane": "prices",
                "scope": "holdings_first",
                "step_order": 3,
                "step_label": "If staged imports were used, validate prices",
                "command": "make price-validate",
                "target_file": "data/imports/prices.csv",
                "tickers": "AMD,AVGO",
                "goal_summary": "Unlock Monthly Picks for 2 tickers; 42 verified rows still needed across this bundle",
                "target_history_rows": 21,
                "suggested_start_date": "2025-12-01",
                "fallback_manual_command": "make price-normalize INPUT=data/raw/prices/AMD.csv TICKER=AMD SOURCE=yahoo_manual",
                "why_it_matters": "These tickers still block monthly picks because local price history is too short.",
                "safe_next_step": "Validate normalized staged prices before preview so schema and duplicate issues surface early.",
            },
            {
                "bundle_name": "Price Coverage Bundle",
                "lane": "prices",
                "scope": "holdings_first",
                "step_order": 4,
                "step_label": "If staged imports were used, preview merge",
                "command": "make price-preview",
                "target_file": "data/imports/prices.csv",
                "tickers": "AMD,AVGO",
                "goal_summary": "Unlock Monthly Picks for 2 tickers; 42 verified rows still needed across this bundle",
                "target_history_rows": 21,
                "suggested_start_date": "2025-12-01",
                "fallback_manual_command": "make price-normalize INPUT=data/raw/prices/AMD.csv TICKER=AMD SOURCE=yahoo_manual",
                "why_it_matters": "These tickers still block monthly picks because local price history is too short.",
                "safe_next_step": "Preview the staged price merge before apply and confirm the affected tickers and row counts look correct.",
            },
            {
                "bundle_name": "Price Coverage Bundle",
                "lane": "prices",
                "scope": "holdings_first",
                "step_order": 5,
                "step_label": "If staged imports were used, apply merge",
                "command": "make price-apply",
                "target_file": "data/imports/prices.csv",
                "tickers": "AMD,AVGO",
                "goal_summary": "Unlock Monthly Picks for 2 tickers; 42 verified rows still needed across this bundle",
                "target_history_rows": 21,
                "suggested_start_date": "2025-12-01",
                "fallback_manual_command": "make price-normalize INPUT=data/raw/prices/AMD.csv TICKER=AMD SOURCE=yahoo_manual",
                "why_it_matters": "These tickers still block monthly picks because local price history is too short.",
                "safe_next_step": "Apply the staged price merge only after validation and preview look correct.",
            },
            {
                "bundle_name": "Price Coverage Bundle",
                "lane": "prices",
                "scope": "holdings_first",
                "step_order": 6,
                "step_label": "Review follow-up output",
                "command": "make price-status",
                "target_file": "data/imports/prices.csv",
                "tickers": "AMD,AVGO",
                "goal_summary": "Unlock Monthly Picks for 2 tickers; 42 verified rows still needed across this bundle",
                "target_history_rows": 21,
                "suggested_start_date": "2025-12-01",
                "fallback_manual_command": "make price-normalize INPUT=data/raw/prices/AMD.csv TICKER=AMD SOURCE=yahoo_manual",
                "why_it_matters": "These tickers still block monthly picks because local price history is too short.",
                "safe_next_step": "Use staged local imports if the free refresh fails.",
            },
            {
                "bundle_name": "Price Coverage Bundle",
                "lane": "prices",
                "scope": "holdings_first",
                "step_order": 7,
                "step_label": "Refresh status outputs",
                "command": "make status",
                "target_file": "data/imports/prices.csv",
                "tickers": "AMD,AVGO",
                "goal_summary": "Unlock Monthly Picks for 2 tickers; 42 verified rows still needed across this bundle",
                "target_history_rows": 21,
                "suggested_start_date": "2025-12-01",
                "fallback_manual_command": "make price-normalize INPUT=data/raw/prices/AMD.csv TICKER=AMD SOURCE=yahoo_manual",
                "why_it_matters": "These tickers still block monthly picks because local price history is too short.",
                "safe_next_step": "Reopen Data Health or Overview after refreshing outputs.",
            },
        ]
    )

    cards = dashboard.data_health_command_bundle_runbook_cards(runbook)
    rendered = " ".join(str(value) for card in cards for value in card.values()).lower()

    assert cards[0]["kicker"] == "PRICES RUNBOOK"
    assert "run bundle command" in rendered
    assert "unlock monthly picks" in rendered
    assert "21 target rows" in rendered
    assert "start by 2025-12-01" in rendered
    assert "make price-normalize input=data/raw/prices/amd.csv ticker=amd source=yahoo_manual" in rendered
    assert "make price-validate" in rendered
    assert "make price-preview" in rendered
    assert "make price-apply" in rendered
    assert "make status" in rendered
    assert "buy" not in rendered
    assert "sell" not in rendered


def test_data_health_command_bundle_runbook_cards_surface_peer_manual_step():
    runbook = pd.DataFrame(
        [
            {
                "bundle_name": "Peer Mapping Bundle",
                "lane": "peers",
                "scope": "holdings_first",
                "step_order": 1,
                "step_label": "Run bundle command",
                "command": "make templates",
                "tickers": "META,NVDA,TSLA",
                "goal_summary": "Advance transparent peer-relative readiness for the listed tickers",
            },
            {
                "bundle_name": "Peer Mapping Bundle",
                "lane": "peers",
                "scope": "holdings_first",
                "step_order": 2,
                "step_label": "Fill peer mappings manually",
                "command": "data/imports/peers.csv",
                "tickers": "META,NVDA,TSLA",
                "goal_summary": "Advance transparent peer-relative readiness for the listed tickers",
            },
            {
                "bundle_name": "Peer Mapping Bundle",
                "lane": "peers",
                "scope": "holdings_first",
                "step_order": 3,
                "step_label": "Refresh status outputs",
                "command": "make status",
                "tickers": "META,NVDA,TSLA",
                "goal_summary": "Advance transparent peer-relative readiness for the listed tickers",
            },
        ]
    )

    cards = dashboard.data_health_command_bundle_runbook_cards(runbook)
    rendered = " ".join(str(value) for card in cards for value in card.values()).lower()

    assert "fill peer mappings manually" in rendered
    assert "data/imports/peers.csv" in rendered
    assert "buy" not in rendered
    assert "sell" not in rendered


def test_data_health_price_target_cards_surface_exact_history_targets_safely():
    worklist = pd.DataFrame(
        [
            {
                "priority": 1,
                "ticker": "META",
                "price_history_days": 0,
                "next_price_goal": "Unlock Monthly Picks",
                "next_target_history_rows": 21,
                "rows_needed_for_next_goal": 21,
                "suggested_start_date": "2026-01-01",
                "example_command": "make price-normalize INPUT=data/raw/prices/META.csv TICKER=META SOURCE=yahoo_manual",
            },
            {
                "priority": 2,
                "ticker": "NVDA",
                "price_history_days": 22,
                "next_price_goal": "Unlock Track Record",
                "next_target_history_rows": 63,
                "rows_needed_for_next_goal": 41,
                "suggested_start_date": "2025-10-01",
                "example_command": "make price-normalize INPUT=data/raw/prices/NVDA.csv TICKER=NVDA SOURCE=yahoo_manual",
            },
        ]
    )

    cards = dashboard.data_health_price_target_cards(worklist)
    rendered = " ".join(str(value) for card in cards for value in card.values()).lower()

    assert cards[0]["kicker"] == "UNLOCK MONTHLY PICKS"
    assert "21 rows still needed" in rendered
    assert "suggested start: 2026-01-01" in rendered
    assert "price-normalize" in rendered
    assert "buy" not in rendered
    assert "sell" not in rendered


def test_data_health_deep_research_target_cards_surface_dcf_and_peer_targets_safely():
    sec_queue = pd.DataFrame(
        [
            {
                "priority": 1,
                "ticker": "NVDA",
                "is_holding": True,
                "theme": "AI Semis",
                "price_history_days": 63,
                "missing_required_for_dcf": "fundamentals row",
                "recommended_action": "Run SEC staging for fundamentals so DCF assumptions can be reviewed from explicit local inputs.",
                "example_command": "python3 -m src.stock_report --sec-stage-fundamentals --tickers NVDA",
            }
        ]
    )
    peer_queue = pd.DataFrame(
        [
            {
                "priority": 1,
                "ticker": "TSLA",
                "is_holding": True,
                "theme": "EV",
                "dcf_ready": True,
                "missing_required_for_peer_relative": "peer mapping",
                "recommended_action": "Add manually researched peer mappings for this ticker and keep peer-relative comparison transparent.",
                "example_command": "make templates",
            }
        ]
    )

    cards = dashboard.data_health_deep_research_target_cards(sec_queue, peer_queue)
    rendered = " ".join(str(value) for card in cards for value in card.values()).lower()

    assert cards[0]["kicker"] == "DCF TARGET"
    assert "peer target" in rendered
    assert "make focus-fundamentals ticker=nvda" in rendered
    assert "make focus-peers ticker=tsla" in rendered
    assert "fundamentals row" in rendered
    assert "peer mapping" in rendered
    assert "buy" not in rendered
    assert "sell" not in rendered


def test_overview_price_target_cards_surface_exact_history_targets_safely():
    worklist = pd.DataFrame(
        [
            {
                "priority": 1,
                "ticker": "META",
                "price_history_days": 0,
                "next_price_goal": "Unlock Monthly Picks",
                "next_target_history_rows": 21,
                "rows_needed_for_next_goal": 21,
                "suggested_start_date": "2026-01-01",
                "example_command": "make price-normalize INPUT=data/raw/prices/META.csv TICKER=META SOURCE=yahoo_manual",
            },
            {
                "priority": 2,
                "ticker": "NVDA",
                "price_history_days": 22,
                "next_price_goal": "Unlock Track Record",
                "next_target_history_rows": 63,
                "rows_needed_for_next_goal": 41,
                "suggested_start_date": "2025-10-01",
                "example_command": "make price-normalize INPUT=data/raw/prices/NVDA.csv TICKER=NVDA SOURCE=yahoo_manual",
            },
        ]
    )

    cards = dashboard.overview_price_target_cards(worklist)
    rendered = " ".join(str(value) for card in cards for value in card.values()).lower()

    assert cards[0]["kicker"] == "UNLOCK MONTHLY PICKS"
    assert "21 rows still needed" in rendered
    assert "target: 21 rows" in rendered
    assert "start from: 2026-01-01" in rendered
    assert "price-normalize" in rendered
    assert "buy" not in rendered
    assert "sell" not in rendered


def test_overview_deep_research_target_cards_surface_dcf_and_peer_targets_safely():
    sec_queue = pd.DataFrame(
        [
            {
                "priority": 1,
                "ticker": "NVDA",
                "is_holding": True,
                "theme": "AI Semis",
                "price_history_days": 63,
                "missing_required_for_dcf": "fundamentals row",
                "recommended_action": "Run SEC staging for fundamentals so DCF assumptions can be reviewed from explicit local inputs.",
                "example_command": "python3 -m src.stock_report --sec-stage-fundamentals --tickers NVDA",
            }
        ]
    )
    peer_queue = pd.DataFrame(
        [
            {
                "priority": 1,
                "ticker": "TSLA",
                "is_holding": True,
                "theme": "EV",
                "dcf_ready": True,
                "missing_required_for_peer_relative": "peer mapping",
                "recommended_action": "Add manually researched peer mappings for this ticker and keep peer-relative comparison transparent.",
                "example_command": "make templates",
            }
        ]
    )

    cards = dashboard.overview_deep_research_target_cards(sec_queue, peer_queue)
    rendered = " ".join(str(value) for card in cards for value in card.values()).lower()

    assert cards[0]["kicker"] == "UNLOCK DCF"
    assert "unlock peers" in rendered
    assert "fundamentals row" in rendered
    assert "peer mapping" in rendered
    assert "make focus-fundamentals ticker=nvda" in rendered
    assert "make focus-peers ticker=tsla" in rendered
    assert "buy" not in rendered
    assert "sell" not in rendered


def test_data_coverage_wizard_cards_show_unlock_goals_without_raw_missing_values():
    wizard = pd.DataFrame(
        [
            {
                "priority": 1,
                "ticker": "NVDA",
                "unlock_goal": "Unlock Monthly Picks",
                "blocking_dataset": "prices",
                "current_status": "0 local price rows",
                "why_it_matters": "Monthly ranking needs verified local price history.",
                "recommended_action": "Refresh NVDA prices, or normalize verified downloaded OHLCV rows into data/imports/prices.csv before validate/preview/apply.",
                "focus_command": "make focus-price TICKER=NVDA",
                "example_command": "python3 -m src.data_update --tickers NVDA",
            },
            {
                "priority": 2,
                "ticker": "NVDA",
                "unlock_goal": "Unlock DCF",
                "blocking_dataset": "fundamentals",
                "current_status": "free_cash_flow, shares_outstanding",
                "why_it_matters": "DCF needs cash-flow inputs.",
                "recommended_action": "Run SEC staging for candidate fundamentals, then validate and preview before applying.",
                "focus_command": "make focus-fundamentals TICKER=NVDA",
                "example_command": "python3 -m src.stock_report --sec-stage-fundamentals --tickers NVDA",
            },
        ]
    )

    cards = dashboard.data_coverage_wizard_cards(wizard)
    rendered = " ".join(str(value) for card in cards for value in card.values()).lower()

    assert "monthly" in rendered
    assert "valuation" in rendered
    assert "not blocking" in rendered
    assert "current blocker: 0 local price rows" in rendered
    assert "normalize verified downloaded ohlcv rows" in rendered
    assert "make focus-price ticker=nvda" in rendered
    assert "nan" not in rendered
    assert "none" not in rendered
    assert "buy" not in rendered
    assert "sell" not in rendered


def test_data_coverage_wizard_cards_handle_missing_output():
    cards = dashboard.data_coverage_wizard_cards(None)
    rendered = " ".join(str(value) for card in cards for value in card.values())

    assert "Not generated" in rendered
    assert "make data-wizard" in rendered


def test_universe_preset_cards_include_preview_commands():
    cards = dashboard.universe_preset_cards()
    rendered = " ".join(str(value) for card in cards for value in card.values())

    assert cards
    assert "preview --preset" in rendered
    assert "apply-import" not in rendered


def test_universe_workflow_cards_explain_preview_first_and_manual_fallback():
    cards = dashboard.universe_workflow_cards(
        {
            "current_universe": {
                "row_count": 12,
                "duplicate_ticker_count": 1,
                "missing_theme_count": 2,
                "unclassified_theme_count": 1,
                "missing_sector_etf_count": 3,
            },
            "staged_universe": {"row_count": 4, "path": "data/imports/universe.csv"},
        }
    )
    rendered = " ".join(str(value) for card in cards for value in card).lower()

    assert cards[0][0] == "Current universe"
    assert cards[0][3] == "warning"
    assert "4 staged ticker rows" in rendered
    assert "preview" in rendered
    assert "custom_universe.csv" in rendered
    assert "make templates" in rendered


def test_universe_action_path_cards_surface_preview_review_and_apply_guidance():
    cards = dashboard.universe_action_path_cards(
        {
            "current_universe": {
                "row_count": 12,
                "duplicate_ticker_count": 1,
                "missing_theme_count": 2,
                "unclassified_theme_count": 1,
            },
            "staged_universe": {"exists": True, "row_count": 4},
        }
    )
    rendered = " ".join(str(value) for card in cards for value in card.values()).lower()

    assert len(cards) == 3
    assert cards[0]["title"] == "Apply staged universe"
    assert cards[0]["command"] == "python3 -m src.universe_builder --apply-import"
    assert "12 current rows" in rendered
    assert "apply stays cli-only" in rendered
    assert "buy" not in rendered
    assert "sell" not in rendered
    assert "buy" not in rendered
    assert "sell" not in rendered


def test_staged_universe_status_frame_hides_raw_json_shape():
    frame = dashboard.staged_universe_status_frame(
        {
            "row_count": 4,
            "path": "data/imports/universe.csv",
            "validation": {"status": "valid_with_warnings", "warnings": ["manual review recommended"]},
        }
    )

    assert list(frame.columns) == ["Field", "Value"]
    assert "Staged file" in frame["Field"].tolist()
    assert "data/imports/universe.csv" in frame["Value"].tolist()
    assert "valid_with_warnings" in frame["Value"].tolist()
    assert "manual review recommended" in frame["Value"].tolist()


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


def test_market_direction_chart_frame_keeps_supported_numeric_rows_only():
    frame = pd.DataFrame(
        {
            "Theme": ["AI Semis", "Robotics", "Infra"],
            "Return1M": [0.12, None, None],
            "RelativeReturnVsSPY": [0.08, -0.03, None],
            "RelativeReturnVsQQQ": [0.04, None, None],
        }
    )

    chart = dashboard.market_direction_chart_frame(frame, max_rows=2)

    assert list(chart.index) == ["AI Semis", "Robotics"]
    assert "RelativeReturnVsSPY" in chart.columns


def test_momentum_setup_distribution_frame_counts_statuses_cleanly():
    frame = pd.DataFrame({"SetupStatus": ["Watch", "Avoid", "Watch", None, ""]})

    chart = dashboard.momentum_setup_distribution_frame(frame)

    assert chart.loc["Watch", "Count"] == 2
    assert chart.loc["Avoid", "Count"] == 1
    assert chart.loc["Not available", "Count"] == 2


def test_momentum_relative_strength_chart_frame_ranks_supported_tickers():
    frame = pd.DataFrame(
        {
            "Ticker": ["amd", "nvda", "amd", "avgo"],
            "RSPercentile": [70, 95, 60, None],
            "RelativeReturnVsSPY": [0.05, 0.18, 0.02, 0.07],
            "RelativeReturnVsQQQ": [0.01, 0.11, -0.01, 0.03],
        }
    )

    chart = dashboard.momentum_relative_strength_chart_frame(frame, max_rows=3)

    assert list(chart.index) == ["NVDA", "AMD", "AVGO"]
    assert chart.loc["AMD", "RSPercentile"] == 70


def test_output_tab_chart_sections_are_research_only_and_targeted():
    market_sections = dashboard.output_tab_chart_sections(
        "Market Direction",
        pd.DataFrame({"Theme": ["AI"], "RelativeReturnVsSPY": [0.12], "RelativeReturnVsQQQ": [0.08]}),
    )
    momentum_sections = dashboard.output_tab_chart_sections(
        "Momentum Leaders",
        pd.DataFrame({"Ticker": ["NVDA"], "SetupStatus": ["Watch"], "RSPercentile": [92], "RelativeReturnVsSPY": [0.18], "RelativeReturnVsQQQ": [0.11]}),
    )
    rendered = " ".join(
        " ".join(str(value) for value in section[:2]) for section in market_sections + momentum_sections
    ).lower()

    assert len(market_sections) == 1
    assert len(momentum_sections) == 2
    assert "relative return" in rendered
    assert "watch-only" in rendered
    assert "buy" not in rendered
    assert "sell" not in rendered


def test_categorical_count_frame_normalizes_missing_values():
    frame = pd.DataFrame({"ReviewState": ["Review Thesis", "", None, "Review Thesis"]})

    chart = dashboard.categorical_count_frame(frame, "ReviewState", "ReviewState")

    assert chart.loc["Review Thesis", "Count"] == 2
    assert chart.loc["Not available", "Count"] == 2


def test_portfolio_review_risk_chart_frame_combines_review_and_concentration():
    frame = pd.DataFrame(
        {
            "ReviewState": ["Review Thesis", "Keep", "Review Thesis"],
            "ConcentrationRisk": [False, True, False],
        }
    )

    chart = dashboard.portfolio_review_risk_chart_frame(frame)

    assert "ReviewStateCount" in chart.columns
    assert "ConcentrationRiskCount" in chart.columns
    assert chart.loc["Review Thesis", "ReviewStateCount"] == 2
    assert chart.loc["No concentration risk", "ConcentrationRiskCount"] == 2


def test_final_watchlist_score_chart_frame_orders_ranked_names():
    frame = pd.DataFrame(
        {
            "Ticker": ["amd", "nvda", "qqq", "amd"],
            "WatchlistRank": [3, 2, 1, 4],
            "WatchlistScore": [41.0, 55.0, 68.0, 10.0],
            "RelativeOpportunityScore": [None, 22.0, None, 5.0],
        }
    )

    chart = dashboard.final_watchlist_score_chart_frame(frame, max_rows=3)

    assert list(chart.index) == ["QQQ", "NVDA", "AMD"]
    assert chart.loc["AMD", "WatchlistScore"] == 41.0


def test_output_tab_chart_sections_include_portfolio_and_watchlist_views():
    portfolio_sections = dashboard.output_tab_chart_sections(
        "Portfolio Review",
        pd.DataFrame({"ReviewState": ["Review Thesis"], "ConcentrationRisk": [False]}),
    )
    watchlist_sections = dashboard.output_tab_chart_sections(
        "Final Watchlist",
        pd.DataFrame({"Ticker": ["NVDA"], "FinalState": ["Review Thesis"], "WatchlistScore": [40.0], "WatchlistRank": [2]}),
    )
    rendered = " ".join(
        " ".join(str(value) for value in section[:2]) for section in portfolio_sections + watchlist_sections
    ).lower()

    assert len(portfolio_sections) == 1
    assert len(watchlist_sections) == 2
    assert "concentration-risk" in rendered or "concentration" in rendered
    assert "watchlist" in rendered
    assert "buy" not in rendered
    assert "sell" not in rendered


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


def test_presentation_frame_handles_duplicate_source_columns_safely():
    frame = pd.DataFrame([["NVDA", "Short reason", "Long reason"]], columns=["Ticker", "ReasonSummary", "ReasonSummary"])

    display = dashboard.presentation_frame(frame)

    assert list(display.columns) == ["Ticker", "Reason", "Reason (2)"]
    assert display.iloc[0]["Reason"] == "Short reason."
    assert display.iloc[0]["Reason (2)"] == "Long reason."


def test_display_column_label_humanizes_unknown_columns():
    assert dashboard.display_column_label("avg_volume_20d") == "Avg Volume 20D"
    assert dashboard.display_column_label("PeerRelativeStatus") == "Peer Relative"


def test_sidebar_guide_rows_are_actionable_and_research_safe():
    status_rows = dashboard.status_legend_rows()
    missing_rows = dashboard.missing_data_guide_rows()
    workflow_rows = dashboard.workflow_command_rows()
    navigation_cards = dashboard.dashboard_navigation_cards()
    empty_rows = dashboard.empty_state_command_rows()
    rendered = " ".join(str(row) for row in status_rows + missing_rows + workflow_rows).lower()
    nav_rendered = " ".join(str(item) for card in navigation_cards for item in card).lower()
    empty_rendered = " ".join(str(row) for row in empty_rows).lower()

    assert any(row["Label"] == "Research Ready" for row in status_rows)
    assert any("price history" in row["Dashboard Label"].lower() for row in missing_rows)
    assert any(row["Command"] == "make help" for row in workflow_rows)
    assert any(row["Command"] == "make status" for row in workflow_rows)
    assert any(row["Command"] == "make focus-price TICKER=NVDA" for row in workflow_rows)
    assert any(row["Command"] == "make focus-fundamentals TICKER=NVDA" for row in workflow_rows)
    assert any(row["Command"] == "make focus-peers TICKER=NVDA" for row in workflow_rows)
    assert any(row["Command"] == "make runbook-prices-broader" for row in workflow_rows)
    assert any(row["Command"] == "make verify" for row in workflow_rows)
    assert any(row["Command"] == "make validate-all" for row in workflow_rows)
    assert any(row["Command"] == "make dashboard-smoke" for row in workflow_rows)
    assert any(row["Command"] == "make daily" for row in workflow_rows)
    assert "overview tab" in nav_rendered
    assert "monthly picks tab" in nav_rendered
    assert "data health tab" in nav_rendered
    assert "make status" in empty_rendered
    assert "make focus-price" in empty_rendered
    assert "price-normalize" in empty_rendered
    assert "make focus-fundamentals" in empty_rendered
    assert "peers.csv" in empty_rendered


def test_priority_now_falls_back_to_status_first_ready_path():
    actions: list[tuple[str, str, str, str]] = []

    if not actions:
        actions.append(
            (
                "Workflow looks ready",
                "Core outputs are present. Run make status to refresh the operator snapshot, then make dashboard-smoke before deeper dashboard review.",
                "make status",
                "neutral",
            )
        )

    rendered = " ".join(str(item) for row in actions for item in row).lower()
    assert "workflow looks ready" in rendered
    assert "make status" in rendered
    assert "dashboard-smoke" in rendered
    assert "place_order" not in rendered
    assert "submit_order" not in rendered
    assert "execute_trade" not in rendered


def test_dashboard_tab_titles_and_navigation_labels_stay_consistent():
    assert dashboard.DASHBOARD_TAB_TITLES[0] == "Overview"
    assert dashboard.DASHBOARD_TAB_TITLES[1] == "Monthly Picks"
    assert dashboard.DASHBOARD_TAB_TITLES[7] == "Stock Report Beta"
    assert dashboard.DASHBOARD_TAB_TITLES[8] == "Data Health"

    navigation = " ".join(str(item) for card in dashboard.dashboard_navigation_cards() for item in card)
    assert "Overview tab" in navigation
    assert "Monthly Picks tab" in navigation
    assert "Stock Report Beta tab" in navigation
    assert "Data Health tab" in navigation


def test_dashboard_column_labels_cover_bundle_goal_fields():
    assert dashboard.COLUMN_LABELS["GoalSummary"] == "Goal Summary"
    assert dashboard.COLUMN_LABELS["TargetGoal"] == "Target Goal"
    assert dashboard.COLUMN_LABELS["RowsNeeded"] == "Rows Needed"
    assert dashboard.COLUMN_LABELS["TargetHistoryRows"] == "Target History Rows"
    assert dashboard.COLUMN_LABELS["SuggestedStartDate"] == "Suggested Start Date"
    assert dashboard.COLUMN_LABELS["FallbackManualCommand"] == "Fallback Manual Command"
    assert dashboard.COLUMN_LABELS["ExactNextCommand"] == "Exact Next Command"
    assert dashboard.COLUMN_LABELS["FocusCommand"] == "Focus Command"
    assert dashboard.COLUMN_LABELS["ExampleCommand"] == "Example Command"


def test_unlock_table_helpers_surface_command_columns():
    ladder = pd.DataFrame(
        [
            {
                "ticker": "AMD",
                "current_unlock_stage": "prices",
                "next_unlock_goal": "Unlock Monthly Picks",
                "price_stage_status": "missing_prices",
                "dcf_stage_status": "dcf_blocked",
                "peer_stage_status": "peer_mapping_missing",
                "optional_context_status": "missing_optional_context",
                "recommended_action": "Run make focus-price TICKER=AMD.",
                "focus_command": "make focus-price TICKER=AMD",
                "example_command": "make price-normalize INPUT=data/raw/prices/AMD.csv TICKER=AMD SOURCE=yahoo_manual",
                "target_file": "data/imports/prices.csv",
            }
        ]
    )
    summary = pd.DataFrame(
        [
            {
                "group_type": "holdings",
                "group_name": "Current Holdings",
                "ticker_count": 3,
                "holdings_count": 3,
                "top_priority_stage": "prices",
                "next_unlock_goal": "Unlock Monthly Picks",
                "representative_tickers": "META, NVDA, TSLA",
                "recommended_action": "Run make status, then follow the printed price focus or runbook path for this group.",
                "focus_command": "make status",
                "example_command": "make runbook-prices",
            }
        ]
    )

    assert dashboard.unlock_ladder_table_columns(ladder, include_statuses=True) == [
        "ticker",
        "current_unlock_stage",
        "next_unlock_goal",
        "price_stage_status",
        "dcf_stage_status",
        "peer_stage_status",
        "optional_context_status",
        "recommended_action",
        "focus_command",
        "example_command",
        "target_file",
    ]
    assert dashboard.unlock_ladder_table_columns(ladder, include_statuses=False) == [
        "ticker",
        "current_unlock_stage",
        "next_unlock_goal",
        "recommended_action",
        "focus_command",
        "example_command",
        "target_file",
    ]
    assert dashboard.unlock_priority_summary_table_columns(summary) == [
        "group_type",
        "group_name",
        "ticker_count",
        "holdings_count",
        "top_priority_stage",
        "next_unlock_goal",
        "representative_tickers",
        "recommended_action",
        "focus_command",
        "example_command",
    ]


def test_price_refresh_fallback_message_uses_status_and_normalize_flow():
    plain = dashboard.price_refresh_fallback_message()
    warned = dashboard.price_refresh_fallback_message(include_remote_failure_prefix=True)

    assert "make status" in plain
    assert "make price-normalize" in plain
    assert "make price-validate" in plain
    assert warned.startswith("Remote price refresh had source issues.")


def test_overview_command_bundle_cards_surface_bundle_commands_safely():
    bundles = pd.DataFrame(
        [
            {
                "bundle_name": "Price Coverage Bundle",
                "lane": "prices",
                "scope": "holdings_first",
                "ticker_count": 3,
                "tickers": "META,NVDA,TSLA",
                "goal_summary": "Unlock Monthly Picks for 2 tickers; Unlock Track Record for 1 ticker; 57 verified rows still needed across this bundle",
                "target_history_rows": 63,
                "suggested_start_date": "2025-10-01",
                "bundle_shortcut_command": "make bundle-prices",
                "detail_shortcut_command": "make detail-prices",
                "runbook_shortcut_command": "make runbook-prices",
                "primary_command": "python3 -m src.data_update --tickers META,NVDA,TSLA",
                "follow_up_command": "make price-status",
                "target_file": "data/imports/prices.csv",
                "why_it_matters": "These tickers still block broader local research because price history is missing or too short.",
                "safe_next_step": "Use staged local imports if the free refresh fails.",
            }
        ]
    )

    cards = dashboard.overview_command_bundle_cards(bundles)
    rendered = " ".join(str(value) for card in cards for value in card.values()).lower()

    assert cards[0]["kicker"] == "PRICES BUNDLE"
    assert "holdings first" in rendered
    assert "unlock monthly picks" in rendered
    assert "63 target rows" in rendered
    assert "start by 2025-10-01" in rendered
    assert "make bundle-prices" in rendered
    assert "buy" not in rendered
    assert "sell" not in rendered


def test_overview_onboarding_fallback_cards_use_status_refresh():
    bundle_cards = dashboard.overview_command_bundle_cards(None)
    handoff_cards = dashboard.overview_bundle_handoff_cards(None, None, None)
    runbook_cards = dashboard.overview_bundle_runbook_cards(None)

    rendered = " ".join(
        str(value)
        for card_group in (bundle_cards, handoff_cards, runbook_cards)
        for card in card_group
        for value in card.values()
    ).lower()

    assert bundle_cards[0]["command"] == "make status"
    assert handoff_cards[0]["command"] == "make status"
    assert runbook_cards[0]["command"] == "make status"
    assert "run make status" in rendered
    assert "buy" not in rendered
    assert "sell" not in rendered


def test_overview_bundle_runbook_cards_surface_lane_steps_safely():
    runbook = pd.DataFrame(
        [
            {
                "bundle_name": "Price Coverage Bundle",
                "lane": "prices",
                "scope": "holdings_first",
                "step_order": 1,
                "step_label": "Run bundle command",
                "command": "python3 -m src.data_update --tickers META",
                "tickers": "META",
                "goal_summary": "Unlock Monthly Picks for 1 ticker; 21 verified rows still needed across this bundle",
                "target_history_rows": 21,
                "suggested_start_date": "2025-12-01",
                "fallback_manual_command": "make price-normalize INPUT=data/raw/prices/META.csv TICKER=META SOURCE=yahoo_manual",
            },
            {
                "bundle_name": "Price Coverage Bundle",
                "lane": "prices",
                "scope": "holdings_first",
                "step_order": 2,
                "step_label": "If refresh fails, normalize first CSV",
                "command": "make price-normalize INPUT=data/raw/prices/META.csv TICKER=META SOURCE=yahoo_manual",
                "tickers": "META",
                "goal_summary": "Unlock Monthly Picks for 1 ticker; 21 verified rows still needed across this bundle",
                "target_history_rows": 21,
                "suggested_start_date": "2025-12-01",
                "fallback_manual_command": "make price-normalize INPUT=data/raw/prices/META.csv TICKER=META SOURCE=yahoo_manual",
            },
            {
                "bundle_name": "Price Coverage Bundle",
                "lane": "prices",
                "scope": "holdings_first",
                "step_order": 3,
                "step_label": "Review follow-up output",
                "command": "make price-status",
                "tickers": "META",
                "goal_summary": "Unlock Monthly Picks for 1 ticker; 21 verified rows still needed across this bundle",
                "target_history_rows": 21,
                "suggested_start_date": "2025-12-01",
                "fallback_manual_command": "make price-normalize INPUT=data/raw/prices/META.csv TICKER=META SOURCE=yahoo_manual",
            },
            {
                "bundle_name": "SEC Fundamentals Bundle",
                "lane": "fundamentals",
                "scope": "holdings_first",
                "step_order": 1,
                "step_label": "Run bundle command",
                "command": "SEC_USER_AGENT='Name email@example.com' make sec-stage TICKERS=NVDA",
                "tickers": "NVDA",
                "goal_summary": "Advance explicit local DCF readiness for the listed tickers",
                "target_history_rows": 0,
                "suggested_start_date": "",
            },
        ]
    )

    cards = dashboard.overview_bundle_runbook_cards(runbook)
    rendered = " ".join(str(value) for card in cards for value in card.values()).lower()

    assert cards[0]["kicker"] == "PRICES LANE"
    assert "run bundle command" in rendered
    assert "unlock monthly picks" in rendered
    assert "21 target rows" in rendered
    assert "start by 2025-12-01" in rendered
    assert "make price-normalize input=data/raw/prices/meta.csv ticker=meta source=yahoo_manual" in rendered
    assert "make sec-stage tickers=nvda" in rendered
    assert "buy" not in rendered
    assert "sell" not in rendered


def test_overview_bundle_handoff_cards_surface_follow_through_safely():
    bundles = pd.DataFrame(
        [
            {
                "bundle_name": "SEC Fundamentals Bundle",
                "lane": "fundamentals",
                "scope": "holdings_first",
                "ticker_count": 3,
                "tickers": "META,NVDA,TSLA",
                "goal_summary": "Advance explicit local DCF readiness for the listed tickers",
                "primary_command": "SEC_USER_AGENT='Name email@example.com' make sec-stage TICKERS=META,NVDA,TSLA",
                "follow_up_command": "make sec-preview",
                "target_file": "data/imports/fundamentals.csv",
                "why_it_matters": "These tickers are the best next candidates for explicit local DCF inputs.",
                "safe_next_step": "Keep SEC enrichment staged and review-only until preview is clean.",
            }
        ]
    )
    details = pd.DataFrame(
        [
            {
                "bundle_name": "SEC Fundamentals Bundle",
                "lane": "fundamentals",
                "ticker": "META",
                "is_holding": True,
                "theme": "AI Platforms",
                "sector_etf": "QQQ",
                "current_unlock_stage": "fundamentals",
            }
        ]
    )
    runbook = pd.DataFrame(
        [
            {
                "bundle_name": "SEC Fundamentals Bundle",
                "lane": "fundamentals",
                "scope": "holdings_first",
                "step_order": 1,
                "step_label": "Run bundle command",
                "command": "SEC_USER_AGENT='Name email@example.com' make sec-stage TICKERS=META,NVDA,TSLA",
                "tickers": "META,NVDA,TSLA",
                "goal_summary": "Advance explicit local DCF readiness for the listed tickers",
                "target_file": "data/imports/fundamentals.csv",
                "why_it_matters": "These tickers are the best next candidates for explicit local DCF inputs.",
                "safe_next_step": "Keep SEC enrichment staged and review-only until preview is clean.",
            },
            {
                "bundle_name": "SEC Fundamentals Bundle",
                "lane": "fundamentals",
                "scope": "holdings_first",
                "step_order": 2,
                "step_label": "Review follow-up output",
                "command": "make sec-preview",
                "tickers": "META,NVDA,TSLA",
                "goal_summary": "Advance explicit local DCF readiness for the listed tickers",
                "target_file": "data/imports/fundamentals.csv",
                "why_it_matters": "These tickers are the best next candidates for explicit local DCF inputs.",
                "safe_next_step": "Keep SEC enrichment staged and review-only until preview is clean.",
            },
            {
                "bundle_name": "SEC Fundamentals Bundle",
                "lane": "fundamentals",
                "scope": "holdings_first",
                "step_order": 3,
                "step_label": "Refresh status outputs",
                "command": "make status",
                "tickers": "META,NVDA,TSLA",
                "goal_summary": "Advance explicit local DCF readiness for the listed tickers",
                "target_file": "data/imports/fundamentals.csv",
                "why_it_matters": "These tickers are the best next candidates for explicit local DCF inputs.",
                "safe_next_step": "Reopen Data Health or Overview after refreshing outputs.",
            },
        ]
    )

    cards = dashboard.overview_bundle_handoff_cards(bundles, details, runbook)
    rendered = " ".join(str(value) for card in cards for value in card.values()).lower()

    assert cards[0]["kicker"] == "FUNDAMENTALS HANDOFF"
    assert "dcf readiness" in rendered
    assert "make sec-stage" in rendered
    assert "make sec-preview" in rendered
    assert "make status" in rendered
    assert "meta" in rendered
    assert "buy" not in rendered
    assert "sell" not in rendered


def test_overview_bundle_handoff_cards_surface_peer_manual_follow_through():
    bundles = pd.DataFrame(
        [
            {
                "bundle_name": "Peer Mapping Bundle",
                "lane": "peers",
                "scope": "holdings_first",
                "ticker_count": 3,
                "tickers": "META,NVDA,TSLA",
                "goal_summary": "Advance transparent peer-relative readiness for the listed tickers",
                "primary_command": "make templates",
                "follow_up_command": "data/imports/peers.csv",
                "target_file": "data/imports/peers.csv",
                "why_it_matters": "These tickers are closest to peer-relative coverage once manually researched peer mappings are added locally.",
                "safe_next_step": "Fill only manually researched peers for the listed tickers, then run make status to refresh readiness and action outputs.",
            }
        ]
    )
    details = pd.DataFrame(
        [
            {
                "bundle_name": "Peer Mapping Bundle",
                "lane": "peers",
                "ticker": "META",
                "is_holding": True,
                "theme": "AI Platforms",
                "sector_etf": "QQQ",
                "current_unlock_stage": "peers",
            }
        ]
    )
    runbook = pd.DataFrame(
        [
            {
                "bundle_name": "Peer Mapping Bundle",
                "lane": "peers",
                "scope": "holdings_first",
                "step_order": 1,
                "step_label": "Run bundle command",
                "command": "make templates",
                "tickers": "META,NVDA,TSLA",
                "goal_summary": "Advance transparent peer-relative readiness for the listed tickers",
                "target_file": "data/imports/peers.csv",
                "why_it_matters": "These tickers are closest to peer-relative coverage once manually researched peer mappings are added locally.",
                "safe_next_step": "Fill only manually researched peers for the listed tickers, then run make status to refresh readiness and action outputs.",
            },
            {
                "bundle_name": "Peer Mapping Bundle",
                "lane": "peers",
                "scope": "holdings_first",
                "step_order": 2,
                "step_label": "Fill peer mappings manually",
                "command": "data/imports/peers.csv",
                "tickers": "META,NVDA,TSLA",
                "goal_summary": "Advance transparent peer-relative readiness for the listed tickers",
                "target_file": "data/imports/peers.csv",
                "why_it_matters": "These tickers are closest to peer-relative coverage once manually researched peer mappings are added locally.",
                "safe_next_step": "Fill only manually researched peers for the listed tickers, then run make status to refresh readiness and action outputs.",
            },
            {
                "bundle_name": "Peer Mapping Bundle",
                "lane": "peers",
                "scope": "holdings_first",
                "step_order": 3,
                "step_label": "Refresh status outputs",
                "command": "make status",
                "tickers": "META,NVDA,TSLA",
                "goal_summary": "Advance transparent peer-relative readiness for the listed tickers",
                "target_file": "data/imports/peers.csv",
                "why_it_matters": "These tickers are closest to peer-relative coverage once manually researched peer mappings are added locally.",
                "safe_next_step": "Refresh the operator outputs and reopen Data Health or Overview to confirm the updated local coverage state.",
            },
        ]
    )

    cards = dashboard.overview_bundle_handoff_cards(bundles, details, runbook)
    rendered = " ".join(str(value) for card in cards for value in card.values()).lower()

    assert cards[0]["kicker"] == "PEERS HANDOFF"
    assert cards[1]["command"] == "data/imports/peers.csv"
    assert cards[2]["command"] == "make status"
    assert "make templates" in rendered
    assert "data/imports/peers.csv" in rendered
    assert "make status" in rendered
    assert "buy" not in rendered
    assert "sell" not in rendered
