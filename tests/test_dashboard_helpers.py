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

    action_rows = dashboard.clean_display_frame(
        pd.DataFrame(
            {
                "recommended_action": [
                    "Run make imports-validate, then make imports-preview, then make imports-apply, then make status to confirm the live staged fundamentals."
                ]
            }
        )
    )
    assert "make status-check TOP_N=5" in action_rows.iloc[0]["recommended_action"]


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


def test_load_output_missing_message_uses_verify(tmp_path):
    frame, message = dashboard.load_output(tmp_path / "final_watchlist.csv")

    assert frame is None
    assert "make verify" in message
    assert "report_generator" not in message


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


def test_monthly_outputs_loader_regenerates_missing_monthly_outputs(tmp_path):
    old_base = dashboard.BASE_DIR
    old_outputs = dashboard.OUTPUTS_DIR
    try:
        dashboard.BASE_DIR = Path("/Users/yjian070/Documents/New project")
        dashboard.OUTPUTS_DIR = tmp_path
        tables = dashboard.load_monthly_outputs(tmp_path)
    finally:
        dashboard.BASE_DIR = old_base
        dashboard.OUTPUTS_DIR = old_outputs

    for filename in dashboard.MONTHLY_FILES:
        frame, _message = tables[filename]
        assert frame is not None

    assert (tmp_path / "monthly_research_picks.csv").exists()
    assert (tmp_path / "monthly_picks_track_record.csv").exists()
    assert (tmp_path / "monthly_picks_equity_curve.csv").exists()


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


def test_data_source_status_tables_refresh_stale_example_commands(tmp_path):
    outputs_dir = tmp_path
    pd.DataFrame(
        [
            {
                "dataset": "fundamentals",
                "ticker": "",
                "status": "partial",
                "reason": "old",
                "required_for": "valuation",
                "recommended_action": "Start with make status, then follow the printed fundamentals focus or runbook path.",
                "target_file": "data/imports/fundamentals.csv",
                "focus_command": "make status",
                "example_command": "make status",
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
                "fallback_action": "Start with make status, then follow the printed fundamentals focus or runbook path.",
                "target_file": "data/imports/fundamentals.csv",
                "focus_command": "make status",
                "example_command": "make status",
                "notes": "old",
                "local_file": "data/fundamentals.csv",
                "row_count": 6,
                "available_columns": "ticker,revenue,fcf",
                "validation_warnings": "as_of_date missing",
            }
        ]
    ).to_csv(outputs_dir / "data_source_status.csv", index=False)

    old_base = dashboard.BASE_DIR
    try:
        dashboard.BASE_DIR = Path("/Users/yjian070/Documents/New project")
        tables = dashboard.load_data_source_status_tables(outputs_dir)
    finally:
        dashboard.BASE_DIR = old_base

    source_frame, _ = tables["data_source_status.csv"]
    gap_frame, _ = tables["data_gap_report.csv"]
    assert source_frame is not None
    assert gap_frame is not None
    assert source_frame.loc[source_frame["dataset"] == "fundamentals", "example_command"].iloc[0] == "make imports-preview"
    assert gap_frame.loc[gap_frame["dataset"] == "fundamentals", "example_command"].iloc[0] == "make imports-preview"


def test_data_source_status_tables_refresh_stale_action_text(tmp_path):
    outputs_dir = tmp_path
    pd.DataFrame(
        [
            {
                "dataset": "fundamentals",
                "ticker": "",
                "status": "partial",
                "reason": "old",
                "required_for": "valuation",
                "recommended_action": "Stage fundamentals manually, then apply them later.",
                "target_file": "data/imports/fundamentals.csv",
                "focus_command": "make imports-validate",
                "example_command": "make imports-preview",
                "local_file": "data/imports/fundamentals.csv",
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
                "fallback_action": "Stage fundamentals manually, then apply them later.",
                "target_file": "data/imports/fundamentals.csv",
                "focus_command": "make imports-validate",
                "example_command": "make imports-preview",
                "notes": "old",
                "local_file": "data/imports/fundamentals.csv",
                "row_count": 6,
                "available_columns": "ticker,revenue,fcf",
                "validation_warnings": "as_of_date missing",
            }
        ]
    ).to_csv(outputs_dir / "data_source_status.csv", index=False)

    old_base = dashboard.BASE_DIR
    try:
        dashboard.BASE_DIR = Path("/Users/yjian070/Documents/New project")
        tables = dashboard.load_data_source_status_tables(outputs_dir)
    finally:
        dashboard.BASE_DIR = old_base

    source_frame, _ = tables["data_source_status.csv"]
    gap_frame, _ = tables["data_gap_report.csv"]
    assert source_frame is not None
    assert gap_frame is not None
    refreshed_source_action = source_frame.loc[source_frame["dataset"] == "fundamentals", "fallback_action"].iloc[0]
    refreshed_gap_action = gap_frame.loc[gap_frame["dataset"] == "fundamentals", "recommended_action"].iloc[0]
    assert "make imports-validate" in refreshed_source_action
    assert "make imports-preview" in refreshed_source_action
    assert "make imports-validate" in refreshed_gap_action
    assert "make imports-preview" in refreshed_gap_action


def test_price_update_status_helpers_handle_missing_and_counts(tmp_path):
    frame, message = dashboard.load_price_update_status(tmp_path)

    assert frame is None
    assert "price_update_status.csv" in message
    assert "make runbook-prices-broader" in message
    assert "make focus-price" in message
    assert "make price-normalize" in message
    assert "make price-validate" in message
    assert "make price-preview" in message
    assert "make price-apply" in message

    counts = dashboard.summarize_price_update_status(
        pd.DataFrame({"status": ["fetched", "parse_error", "parse_error", "source_unavailable"]})
    )

    assert counts["fetched"] == 1
    assert counts["parse_error"] == 2


def test_load_price_update_status_enriches_legacy_command_fields(tmp_path):
    path = tmp_path / "price_update_status.csv"
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
    ).to_csv(path, index=False)

    frame, message = dashboard.load_price_update_status(tmp_path)

    assert message is None
    assert frame is not None
    assert frame.iloc[0]["recommended_action"].startswith("Run make focus-price TICKER=AMD")
    assert frame.iloc[0]["focus_command"] == "make focus-price TICKER=AMD"
    assert frame.iloc[0]["example_command"] == "make price-normalize INPUT=data/raw/prices/AMD.csv TICKER=AMD SOURCE=yahoo_manual"
    assert frame.iloc[0]["target_file"] == "data/imports/prices.csv"
    rewritten = pd.read_csv(path)
    assert rewritten.iloc[0]["recommended_action"].startswith("Run make focus-price TICKER=AMD")
    assert rewritten.iloc[0]["focus_command"] == "make focus-price TICKER=AMD"
    assert rewritten.iloc[0]["example_command"] == "make price-normalize INPUT=data/raw/prices/AMD.csv TICKER=AMD SOURCE=yahoo_manual"
    assert rewritten.iloc[0]["target_file"] == "data/imports/prices.csv"


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


def test_load_action_queue_refreshes_stale_price_action_text_even_with_current_command_fields(tmp_path):
    pd.DataFrame(
        [
            {
                "priority": 1,
                "urgency": "critical",
                "action_type": "prices",
                "ticker": "AMD",
                "title": "Fix price coverage",
                "status": "parse_error",
                "recommended_action": "Run make focus-price TICKER=AMD, or run python3 -m src.data_update --tickers AMD and normalize verified downloaded OHLCV files into data/imports/prices.csv.",
                "focus_command": "make focus-price TICKER=AMD",
                "example_command": "make price-normalize INPUT=data/raw/prices/AMD.csv TICKER=AMD SOURCE=yahoo_manual",
                "target_file": "data/imports/prices.csv",
                "source_file": "data/imports/prices.csv",
                "source_artifact": "outputs/data_quality_wizard.csv",
                "reason": "AMD has 0 local price rows.",
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
    amd_row = frame.loc[(frame["action_type"].astype(str).str.strip() == "prices") & (frame["ticker"].astype(str).str.strip() == "AMD")].iloc[0]
    assert "make price-refresh TICKERS=AMD" in str(amd_row["recommended_action"])
    assert amd_row["focus_command"] == "make focus-price TICKER=AMD"
    assert amd_row["example_command"] == "make price-normalize INPUT=data/raw/prices/AMD.csv TICKER=AMD SOURCE=yahoo_manual"


def test_load_action_queue_refreshes_stale_staged_fundamentals_queue_artifact(tmp_path):
    pd.DataFrame(
        [
            {
                "priority": 2,
                "urgency": "high",
                "action_type": "fundamentals",
                "ticker": "",
                "title": "Resolve fundamentals gap",
                "status": "partial",
                "recommended_action": "Run make imports-validate, then make imports-preview, then make imports-apply, then make status to confirm the live local fundamentals and DCF inputs.",
                "focus_command": "make imports-validate",
                "example_command": "make imports-preview",
                "target_file": "data/imports/fundamentals.csv",
                "source_file": "data/imports/fundamentals.csv",
                "source_artifact": "outputs/data_gap_report.csv",
                "reason": "as_of_date column is unavailable, so freshness is file-based only.",
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
    staged_rows = frame.loc[frame["focus_command"].astype(str).str.strip().eq("make imports-validate")]
    assert not staged_rows.empty
    assert staged_rows.iloc[0]["title"] == "Advance staged fundamentals import"
    assert "data/imports/fundamentals.csv" in str(staged_rows.iloc[0]["reason"])


def test_load_action_queue_refreshes_stale_staged_peer_queue_artifact(tmp_path):
    data_dir = tmp_path / "data"
    outputs_dir = tmp_path / "outputs"
    imports_dir = data_dir / "imports"
    data_dir.mkdir()
    outputs_dir.mkdir()
    imports_dir.mkdir()
    (tmp_path / "config.yaml").write_text(Path("config.yaml").read_text(encoding="utf-8"), encoding="utf-8")
    (data_dir / "prices.csv").write_text(
        "date,ticker,adj_close,volume\n"
        "2026-01-02,NVDA,100,1000\n",
        encoding="utf-8",
    )
    (data_dir / "fundamentals.csv").write_text(
        "ticker,theme,sector,pe_ratio,revenue_growth,profit_margin,debt_to_equity\n"
        "NVDA,AI,Semis,30,0.2,0.3,0.4\n",
        encoding="utf-8",
    )
    (data_dir / "universe.csv").write_text(
        "ticker,theme,sectoretf,defaultpurpose,marketcapbucket,notes\n"
        "NVDA,AI,SMH,Momentum Leader,Large,fixture\n",
        encoding="utf-8",
    )
    (data_dir / "holdings.csv").write_text(
        "ticker,primarypurpose\n"
        "NVDA,Momentum Leader\n",
        encoding="utf-8",
    )
    (imports_dir / "peers.csv").write_text(
        "ticker,peer_ticker,peer_group,source,as_of_date\n"
        "NVDA,AMD,ai_semis,manual,2026-05-22\n",
        encoding="utf-8",
    )
    pd.DataFrame(
        [
            {
                "priority": 2,
                "urgency": "high",
                "action_type": "peers",
                "ticker": "",
                "title": "Resolve peers gap",
                "status": "partial",
                "recommended_action": "Run make imports-validate, then make imports-preview, then make imports-apply, then make status to confirm the live local peer inputs.",
                "focus_command": "make imports-validate",
                "example_command": "make imports-preview",
                "target_file": "data/imports/peers.csv",
                "source_file": "data/imports/peers.csv",
                "source_artifact": "outputs/data_gap_report.csv",
                "reason": "as_of_date column is unavailable, so freshness is file-based only.",
            }
        ]
    ).to_csv(outputs_dir / "research_action_queue.csv", index=False)

    old_base = dashboard.BASE_DIR
    try:
        dashboard.BASE_DIR = tmp_path
        frame, message = dashboard.load_action_queue(outputs_dir)
    finally:
        dashboard.BASE_DIR = old_base

    assert message is None
    assert frame is not None
    staged_rows = frame.loc[
        frame["focus_command"].astype(str).str.strip().eq("make imports-validate")
        & frame["action_type"].astype(str).str.strip().eq("peers")
    ]
    assert not staged_rows.empty
    assert staged_rows.iloc[0]["title"] == "Advance staged peer import"
    assert staged_rows.iloc[0]["target_file"] == "data/imports/peers.csv"
    assert "staged import rows are present" in str(staged_rows.iloc[0]["reason"]).lower()


def test_load_action_queue_refreshes_stale_manual_peer_queue_artifact(tmp_path):
    data_dir = tmp_path / "data"
    outputs_dir = tmp_path / "outputs"
    data_dir.mkdir()
    outputs_dir.mkdir()
    (tmp_path / "config.yaml").write_text(Path("config.yaml").read_text(encoding="utf-8"), encoding="utf-8")
    pd.DataFrame(
        [
            {"ticker": "AMD", "theme": "AI", "sectoretf": "SMH", "defaultpurpose": "Momentum Leader"},
        ]
    ).to_csv(data_dir / "universe.csv", index=False)
    pd.DataFrame(columns=["ticker", "shares", "primarypurpose"]).to_csv(data_dir / "holdings.csv", index=False)
    pd.DataFrame(
        [
            {
                "priority": 3,
                "urgency": "high",
                "action_type": "peers",
                "ticker": "AMD",
                "title": "Improve peers coverage for AMD",
                "status": "manual_input_needed",
                "recommended_action": "Add peer mappings manually to data/imports/peers.csv.",
                "focus_command": "make templates",
                "example_command": "make templates",
                "target_file": "data/imports/peers.csv",
                "source_file": "data/imports/peers.csv",
                "source_artifact": "outputs/data_onboarding_actions.csv",
                "reason": "No local peer mapping is configured for this ticker.",
            }
        ]
    ).to_csv(outputs_dir / "research_action_queue.csv", index=False)

    old_base = dashboard.BASE_DIR
    try:
        dashboard.BASE_DIR = tmp_path
        frame, message = dashboard.load_action_queue(outputs_dir)
    finally:
        dashboard.BASE_DIR = old_base

    assert message is None
    assert frame is not None
    peer_rows = frame.loc[frame["action_type"].astype(str).str.strip().eq("peers")]
    assert not peer_rows.empty
    assert peer_rows.iloc[0]["focus_command"] == "make focus-peers TICKER=AMD"
    assert "make focus-peers TICKER=AMD" in str(peer_rows.iloc[0]["recommended_action"])


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
    assert "make focus-price TICKER=AMD" in amd_row["NextBestAction"]
    assert "make price-refresh tickers=amd" in amd_row["NextBestAction"].lower()


def test_load_research_health_tables_refreshes_stale_enrichment_wizard_actions(tmp_path):
    pd.DataFrame(
        [
            {
                "Ticker": "NVDA",
                "DataQualityScore": 65,
                "ReadinessStatus": "Needs Enrichment",
                "MomentumReady": True,
                "MonthlyPicksReady": True,
                "DCFReady": False,
                "PeerReady": False,
                "EarningsAvailable": False,
                "AnalystEstimatesAvailable": False,
                "PriceHistoryDays": 80,
                "MissingDataFields": "DCF inputs, peer mapping",
                "NextBestAction": "Run make focus-fundamentals TICKER=NVDA, or stage explicit local fundamentals with make sec-stage TICKERS=NVDA.",
                "FocusCommand": "make focus-fundamentals TICKER=NVDA",
                "ExampleCommand": "make onboarding",
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
    nvda_row = frame.loc[frame["Ticker"] == "NVDA"].iloc[0]
    assert nvda_row["FocusCommand"] == "make focus-fundamentals TICKER=NVDA"
    assert "make sec-stage TICKERS=NVDA" in nvda_row["ExampleCommand"]
    assert "make focus-fundamentals TICKER=NVDA" in nvda_row["NextBestAction"]


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


def test_load_data_onboarding_tables_refreshes_stale_coverage_wizard_actions(tmp_path):
    old_base = dashboard.BASE_DIR
    try:
        dashboard.BASE_DIR = Path("/Users/yjian070/Documents/New project")
        dashboard.write_onboarding_outputs(dashboard.BASE_DIR, output_dir=tmp_path)

        pd.DataFrame(
            [
                {
                    "priority": 1,
                    "ticker": "AMD",
                    "unlock_goal": "Unlock Monthly Picks",
                    "blocking_dataset": "prices",
                    "current_status": "0 local price rows",
                    "why_it_matters": "old",
                    "recommended_action": "Run make focus-price TICKER=AMD, or run python3 -m src.data_update --tickers AMD and normalize verified downloaded OHLCV files into data/imports/prices.csv.",
                    "target_file": "data/imports/prices.csv",
                    "focus_command": "make focus-price TICKER=AMD",
                    "example_command": "make price-normalize INPUT=data/raw/prices/AMD.csv TICKER=AMD SOURCE=yahoo_manual",
                    "safe_next_step": "old",
                },
                {
                    "priority": 2,
                    "ticker": "NVDA",
                    "unlock_goal": "Unlock DCF",
                    "blocking_dataset": "fundamentals",
                    "current_status": "DCF inputs incomplete",
                    "why_it_matters": "old",
                    "recommended_action": "Run make focus-fundamentals TICKER=NVDA, or stage explicit local fundamentals with make sec-stage TICKERS=NVDA.",
                    "target_file": "data/imports/fundamentals.csv",
                    "focus_command": "make focus-fundamentals TICKER=NVDA",
                    "example_command": "make onboarding",
                    "safe_next_step": "old",
                },
                {
                    "priority": 3,
                    "ticker": "META",
                    "unlock_goal": "Unlock Peer Relative",
                    "blocking_dataset": "peers",
                    "current_status": "Peer-relative inputs incomplete",
                    "why_it_matters": "old",
                    "recommended_action": "Run make focus-peers TICKER=META, or run make templates, then fill data/imports/peers.csv manually with transparent peer mappings.",
                    "target_file": "data/imports/peers.csv",
                    "focus_command": "make focus-peers TICKER=META",
                    "example_command": "make onboarding",
                    "safe_next_step": "old",
                },
            ]
        ).to_csv(tmp_path / "data_coverage_wizard.csv", index=False)

        tables = dashboard.load_data_onboarding_tables(tmp_path)
    finally:
        dashboard.BASE_DIR = old_base

    frame, message = tables["data_coverage_wizard.csv"]
    assert message is None
    assert frame is not None

    amd_row = frame.loc[(frame["ticker"] == "AMD") & (frame["blocking_dataset"] == "prices")].iloc[0]
    nvda_row = frame.loc[(frame["ticker"] == "NVDA") & (frame["blocking_dataset"] == "fundamentals")].iloc[0]
    meta_row = frame.loc[(frame["ticker"] == "META") & (frame["blocking_dataset"] == "peers")].iloc[0]

    assert "make focus-price TICKER=AMD" in str(amd_row["recommended_action"])
    assert "make price-refresh TICKERS=AMD" in str(amd_row["recommended_action"])
    assert amd_row["focus_command"] == "make focus-price TICKER=AMD"
    assert "make price-normalize INPUT=data/raw/prices/AMD.csv TICKER=AMD SOURCE=yahoo_manual" == amd_row["example_command"]
    assert "make focus-fundamentals TICKER=NVDA" in str(nvda_row["recommended_action"])
    assert nvda_row["focus_command"] == "make focus-fundamentals TICKER=NVDA"
    assert "make sec-stage TICKERS=NVDA" == nvda_row["example_command"]
    assert "make focus-peers TICKER=META" in str(meta_row["recommended_action"])
    assert meta_row["focus_command"] == "make focus-peers TICKER=META"
    assert meta_row["example_command"] == "make templates"


def test_load_data_onboarding_tables_refreshes_stale_bundle_artifacts(tmp_path):
    old_base = dashboard.BASE_DIR
    try:
        dashboard.BASE_DIR = Path("/Users/yjian070/Documents/New project")
        dashboard.write_onboarding_outputs(dashboard.BASE_DIR, output_dir=tmp_path)

        pd.DataFrame(
            [
                {
                    "bundle_name": "Price Coverage Bundle",
                    "lane": "prices",
                    "scope": "holdings_first",
                    "ticker_count": 2,
                    "tickers": "AMD,AVGO",
                    "goal_summary": "old",
                    "target_history_rows": 21,
                    "suggested_start_date": "2025-12-01",
                    "bundle_shortcut_command": "make bundle-prices",
                    "detail_shortcut_command": "make detail-prices",
                    "runbook_shortcut_command": "make runbook-prices",
                    "primary_command": "python3 -m src.data_update --tickers AMD,AVGO",
                    "follow_up_command": "make price-status",
                    "target_file": "data/imports/prices.csv",
                    "why_it_matters": "old",
                    "safe_next_step": "old",
                }
            ]
        ).to_csv(tmp_path / "command_bundles.csv", index=False)
        pd.DataFrame(
            [
                {
                    "bundle_name": "Price Coverage Bundle",
                    "lane": "prices",
                    "ticker": "AMD",
                    "is_holding": True,
                    "theme": "AI Infra",
                    "sector_etf": "SMH",
                    "current_unlock_stage": "prices",
                    "target_goal": "Unlock Monthly Picks",
                    "rows_needed": 21,
                    "target_history_rows": 21,
                    "suggested_start_date": "2025-12-01",
                    "fallback_manual_command": "make price-normalize INPUT=data/raw/prices/AMD.csv TICKER=AMD SOURCE=yahoo_manual",
                    "exact_next_command": "python3 -m src.data_update --tickers AMD",
                    "recommended_action": "old",
                    "primary_command": "python3 -m src.data_update --tickers AMD,AVGO",
                    "follow_up_command": "make price-status",
                    "target_file": "data/imports/prices.csv",
                    "safe_next_step": "old",
                }
            ]
        ).to_csv(tmp_path / "command_bundle_details.csv", index=False)
        pd.DataFrame(
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
                    "goal_summary": "old",
                    "target_history_rows": 21,
                    "suggested_start_date": "2025-12-01",
                    "fallback_manual_command": "make price-normalize INPUT=data/raw/prices/AMD.csv TICKER=AMD SOURCE=yahoo_manual",
                    "why_it_matters": "old",
                    "safe_next_step": "old",
                }
            ]
        ).to_csv(tmp_path / "command_bundle_runbook.csv", index=False)

        tables = dashboard.load_data_onboarding_tables(tmp_path)
    finally:
        dashboard.BASE_DIR = old_base

    bundle_frame, bundle_message = tables["command_bundles.csv"]
    detail_frame, detail_message = tables["command_bundle_details.csv"]
    runbook_frame, runbook_message = tables["command_bundle_runbook.csv"]

    assert bundle_message is None
    assert detail_message is None
    assert runbook_message is None
    assert bundle_frame is not None
    assert detail_frame is not None
    assert runbook_frame is not None
    assert not bundle_frame["primary_command"].astype(str).str.startswith("python3 -m src.data_update --tickers ").any()
    assert not detail_frame["exact_next_command"].astype(str).str.startswith("python3 -m src.data_update --tickers ").any()
    assert not runbook_frame["command"].astype(str).str.startswith("python3 -m src.data_update --tickers ").any()
    assert bundle_frame["primary_command"].astype(str).str.startswith("make price-refresh TICKERS=").any()
    assert "make focus-price TICKER=AMD" in set(detail_frame["exact_next_command"])


def test_load_data_onboarding_tables_refreshes_env_prefixed_sec_bundle_commands(tmp_path):
    old_base = dashboard.BASE_DIR
    try:
        dashboard.BASE_DIR = Path("/Users/yjian070/Documents/New project")
        dashboard.write_onboarding_outputs(dashboard.BASE_DIR, output_dir=tmp_path)

        pd.DataFrame(
            [
                {
                    "bundle_name": "Fundamentals Bundle",
                    "lane": "fundamentals",
                    "scope": "holdings_first",
                    "ticker_count": 1,
                    "tickers": "NVDA",
                    "goal_summary": "old",
                    "target_history_rows": 0,
                    "suggested_start_date": "",
                    "bundle_shortcut_command": "make bundle-fundamentals",
                    "detail_shortcut_command": "make detail-fundamentals",
                    "runbook_shortcut_command": "make runbook-fundamentals",
                    "primary_command": "SEC_USER_AGENT='Name email@example.com' make sec-stage TICKERS=NVDA",
                    "follow_up_command": "make imports-validate",
                    "target_file": "data/imports/fundamentals.csv",
                    "why_it_matters": "old",
                    "safe_next_step": "old",
                }
            ]
        ).to_csv(tmp_path / "command_bundles.csv", index=False)

        tables = dashboard.load_data_onboarding_tables(tmp_path)
    finally:
        dashboard.BASE_DIR = old_base

    bundle_frame, bundle_message = tables["command_bundles.csv"]
    assert bundle_message is None
    assert bundle_frame is not None
    assert not bundle_frame["primary_command"].astype(str).str.startswith("SEC_USER_AGENT=").any()
    assert bundle_frame["primary_command"].astype(str).str.startswith("make sec-stage TICKERS=").any()


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
            "peer_ready": [False, False, False],
            "focus_command": ["make focus-peers TICKER=NVDA", "make imports-validate", "make focus-peers TICKER=TSLA"],
            "target_file": ["data/imports/peers.csv", "data/imports/peers.csv", "data/imports/peers.csv"],
        }
    )

    summary = dashboard.summarize_peer_mapping_queue(worklist)

    assert summary["priority_1"] == 1
    assert summary["priority_2"] == 1
    assert summary["holdings"] == 2
    assert summary["missing_peer_mapping"] == 2
    assert summary["mapped_peer_follow_through"] == 1
    assert summary["staged_peer_import"] == 1


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
            {"priority": 1, "urgency": "critical", "action_type": "prices", "ticker": "AMD", "title": "Repair prices", "reason": "No local prices.", "recommended_action": "Normalize verified downloaded OHLCV rows, then run make price-validate, make price-preview, and make price-apply.", "focus_command": "make focus-price TICKER=AMD", "example_command": "make price-refresh"},
        ]
    )

    signals = dashboard.top_priority_signals(queue, limit=2)

    assert signals[0]["title"] == "make focus-price TICKER=AMD"
    assert "P1" in signals[0]["badges"]
    assert signals[0]["command"] == "make focus-price TICKER=AMD"
    assert "normalize verified downloaded ohlcv rows" in signals[0]["body"].lower()
    assert signals[1]["title"] == "make focus-fundamentals TICKER=NVDA"


def test_top_priority_signals_use_lane_front_doors_when_commands_are_missing():
    queue = pd.DataFrame(
        [
            {
                "priority": 1,
                "urgency": "critical",
                "action_type": "peers",
                "ticker": "AMD",
                "title": "Research peers",
                "reason": "Peer mappings are missing.",
                "recommended_action": "Add manually researched mappings through the staged imports flow.",
                "focus_command": "",
                "example_command": "",
            },
            {
                "priority": 2,
                "urgency": "high",
                "action_type": "unknown",
                "ticker": "",
                "title": "Review queue",
                "reason": "A portfolio-wide workflow step is still pending.",
                "recommended_action": "",
                "focus_command": "",
                "example_command": "",
            },
        ]
    )

    signals = dashboard.top_priority_signals(queue, limit=2)

    assert signals[0]["title"] == "make focus-peers TICKER=AMD"
    assert signals[0]["command"] == "make focus-peers TICKER=AMD"
    assert signals[1]["title"] == "make action-queue-check TOP_N=10"
    assert signals[1]["command"] == "make action-queue-check TOP_N=10"


def test_top_priority_signals_use_review_fallback_when_row_copy_is_missing():
    queue = pd.DataFrame(
        [
            {
                "priority": 1,
                "urgency": "critical",
                "action_type": "prices",
                "ticker": "AMD",
                "title": "Repair prices",
                "reason": "",
                "recommended_action": "",
                "focus_command": "",
                "example_command": "",
            }
        ]
    )

    signals = dashboard.top_priority_signals(queue, limit=1)

    assert signals[0]["title"] == "make focus-price TICKER=AMD"
    assert "review price path." in signals[0]["body"].lower()
    assert "not available" not in signals[0]["body"].lower()


def test_top_priority_signals_use_command_family_fallbacks_when_row_copy_is_missing():
    queue = pd.DataFrame(
        [
            {
                "priority": 1,
                "urgency": "critical",
                "action_type": "fundamentals",
                "ticker": "NVDA",
                "title": "Advance staged fundamentals",
                "reason": "",
                "recommended_action": "",
                "focus_command": "make imports-validate",
                "example_command": "",
            },
            {
                "priority": 2,
                "urgency": "high",
                "action_type": "peers",
                "ticker": "",
                "title": "Run peer bundle",
                "reason": "",
                "recommended_action": "",
                "focus_command": "make bundle-peers",
                "example_command": "",
            },
            {
                "priority": 3,
                "urgency": "high",
                "action_type": "peers",
                "ticker": "TSLA",
                "title": "Open peer runbook",
                "reason": "",
                "recommended_action": "",
                "focus_command": "make runbook-peers",
                "example_command": "",
            },
        ]
    )

    signals = dashboard.top_priority_signals(queue, limit=3)

    assert signals[0]["title"] == "make imports-validate"
    assert "staged local workflow next" in signals[0]["body"].lower()
    assert signals[1]["title"] == "make bundle-peers"
    assert "highest-leverage local bundle first" in signals[1]["body"].lower()
    assert signals[2]["title"] == "make runbook-peers"
    assert "staged local workflow next" in signals[2]["body"].lower()
    assert "not available" not in " ".join(signal["body"] for signal in signals).lower()


def test_top_priority_signals_keep_staged_follow_through_visible():
    queue = pd.DataFrame(
        [
            {
                "priority": 1,
                "urgency": "critical",
                "action_type": "fundamentals",
                "ticker": "NVDA",
                "reason": "",
                "recommended_action": "Use staged local imports if the free refresh fails.",
                "focus_command": "make imports-validate",
                "example_command": "",
                "target_file": "data/imports/fundamentals.csv",
            },
            {
                "priority": 2,
                "urgency": "high",
                "action_type": "peers",
                "ticker": "TSLA",
                "reason": "",
                "recommended_action": "Use staged local imports if the free refresh fails.",
                "focus_command": "make imports-validate",
                "example_command": "",
                "target_file": "data/imports/peers.csv",
            },
            {
                "priority": 3,
                "urgency": "high",
                "action_type": "prices",
                "ticker": "AMD",
                "reason": "",
                "recommended_action": "Use staged local imports if the free refresh fails.",
                "focus_command": "make price-validate",
                "example_command": "",
                "target_file": "data/imports/prices.csv",
            },
        ]
    )

    signals = dashboard.top_priority_signals(queue, limit=3)

    assert signals[0]["command"] == "make imports-validate"
    assert "make imports-preview" in signals[0]["body"].lower()
    assert "make imports-apply" in signals[0]["body"].lower()
    assert signals[1]["command"] == "make imports-validate"
    assert "make imports-preview" in signals[1]["body"].lower()
    assert "make imports-apply" in signals[1]["body"].lower()
    assert signals[2]["command"] == "make price-validate"
    assert "make price-preview" in signals[2]["body"].lower()
    assert "make price-apply" in signals[2]["body"].lower()
    assert "use staged local imports if the free refresh fails" not in " ".join(signal["body"] for signal in signals).lower()


def test_operator_summary_helpers_normalize_legacy_status_copy():
    queue = pd.DataFrame(
        [
            {
                "priority": 1,
                "urgency": "critical",
                "action_type": "fundamentals",
                "ticker": "NVDA",
                "reason": "Run make imports-validate, then make imports-preview, then make imports-apply, then make status to confirm the live staged fundamentals.",
                "recommended_action": "",
            }
        ]
    )
    payload = {
        "top_onboarding_actions": [
            {
                "priority": 1,
                "dataset": "fundamentals",
                "ticker": "NVDA",
                "reason": "Run make imports-validate, then make imports-preview, then make imports-apply, then make status to confirm the live staged fundamentals.",
                "recommended_action": "",
            }
        ]
    }
    actions = pd.DataFrame(
        [
            {
                "priority": 1,
                "dataset": "fundamentals",
                "ticker": "NVDA",
                "reason": "Run make imports-validate, then make imports-preview, then make imports-apply, then make status to confirm the live staged fundamentals.",
                "recommended_action": "",
            }
        ]
    )

    signals = dashboard.top_priority_signals(queue, limit=1)
    status_actions = dashboard.project_status_action_cards(payload)
    action_cards = dashboard.data_health_action_path_cards(actions, queue)

    assert "make status-check TOP_N=5" in signals[0]["body"]
    assert "make status-check TOP_N=5" in status_actions[0][1]
    assert "make status-check TOP_N=5" in action_cards[1]["body"]


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
                "recommended_action": "Normalize verified downloaded OHLCV rows, then run make price-validate, make price-preview, and make price-apply.",
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
    assert commands[0]["Command"] == "make status-check TOP_N=5"


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


def test_project_status_read_only_fallbacks_use_status_check():
    actions = dashboard.project_status_action_cards(None)
    html = dashboard.project_status_cockpit_html(None, 0, "Unknown")

    assert actions[0][0] == "Project status unavailable"
    assert actions[0][2] == "make status-check TOP_N=5"
    assert "read-only status command" in actions[0][1].lower()
    assert "make status-check top_n=5" in html.lower()
    assert "buy" not in html.lower()
    assert "sell" not in html.lower()


def test_project_status_action_cards_use_lane_front_doors_when_commands_are_missing():
    payload = {
        "top_onboarding_actions": [
            {
                "priority": 1,
                "dataset": "fundamentals",
                "ticker": "AMD",
                "reason": "DCF inputs are still missing.",
                "recommended_action": "Stage candidate fundamentals and preview them before apply.",
                "focus_command": "",
                "example_command": "",
            }
        ]
    }

    actions = dashboard.project_status_action_cards(payload)

    assert actions[0][0] == "P1 fundamentals - AMD"
    assert actions[0][2] == "make focus-fundamentals TICKER=AMD"


def test_project_status_action_cards_use_review_fallback_when_row_copy_is_missing():
    payload = {
        "top_onboarding_actions": [
            {
                "priority": 1,
                "dataset": "peers",
                "ticker": "TSLA",
                "reason": "",
                "recommended_action": "",
                "focus_command": "",
                "example_command": "",
            }
        ]
    }

    actions = dashboard.project_status_action_cards(payload)

    assert actions[0][0] == "P1 peers - TSLA"
    assert actions[0][2] == "make focus-peers TICKER=TSLA"
    assert "review peer path." in actions[0][1].lower()
    assert "not available" not in actions[0][1].lower()


def test_project_status_action_cards_use_command_family_fallbacks_when_row_copy_is_missing():
    payload = {
        "top_onboarding_actions": [
            {
                "priority": 1,
                "dataset": "fundamentals",
                "ticker": "NVDA",
                "reason": "",
                "recommended_action": "",
                "focus_command": "make imports-validate",
                "example_command": "",
            },
            {
                "priority": 2,
                "dataset": "peers",
                "ticker": "",
                "reason": "",
                "recommended_action": "",
                "focus_command": "make bundle-peers",
                "example_command": "",
            },
            {
                "priority": 3,
                "dataset": "peers",
                "ticker": "TSLA",
                "reason": "",
                "recommended_action": "",
                "focus_command": "make runbook-peers",
                "example_command": "",
            },
        ]
    }

    actions = dashboard.project_status_action_cards(payload)

    assert actions[0][2] == "make imports-validate"
    assert "staged local workflow next" in actions[0][1].lower()
    assert actions[1][2] == "make bundle-peers"
    assert "highest-leverage local bundle first" in actions[1][1].lower()
    assert actions[2][2] == "make runbook-peers"
    assert "staged local workflow next" in actions[2][1].lower()
    assert "not available" not in " ".join(action[1] for action in actions).lower()


def test_project_status_action_cards_keep_staged_import_follow_through_visible():
    payload = {
        "top_onboarding_actions": [
            {
                "priority": 1,
                "dataset": "fundamentals",
                "ticker": "NVDA",
                "reason": "",
                "recommended_action": "Use staged local imports if the free refresh fails.",
                "focus_command": "make imports-validate",
                "example_command": "",
                "target_file": "data/imports/fundamentals.csv",
            },
            {
                "priority": 2,
                "dataset": "peers",
                "ticker": "TSLA",
                "reason": "",
                "recommended_action": "Use staged local imports if the free refresh fails.",
                "focus_command": "make imports-validate",
                "example_command": "",
                "target_file": "data/imports/peers.csv",
            },
            {
                "priority": 3,
                "dataset": "prices",
                "ticker": "AMD",
                "reason": "",
                "recommended_action": "Use staged local imports if the free refresh fails.",
                "focus_command": "make price-validate",
                "example_command": "",
                "target_file": "data/imports/prices.csv",
            },
        ]
    }

    actions = dashboard.project_status_action_cards(payload)

    assert actions[0][2] == "make imports-validate"
    assert "make imports-preview" in actions[0][1].lower()
    assert "make imports-apply" in actions[0][1].lower()
    assert actions[1][2] == "make imports-validate"
    assert "make imports-preview" in actions[1][1].lower()
    assert "make imports-apply" in actions[1][1].lower()
    assert actions[2][2] == "make price-validate"
    assert "make price-preview" in actions[2][1].lower()
    assert "make price-apply" in actions[2][1].lower()
    assert "use staged local imports if the free refresh fails" not in " ".join(action[1] for action in actions).lower()


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


def test_project_status_command_rows_use_status_check_when_structured_command_is_missing():
    payload = {
        "recommended_next_command_rows": [
            {
                "Step": "Read-only status snapshot",
                "Command": "",
                "Reason": "Rebuild the local status snapshot before choosing a deeper workflow path.",
            }
        ]
    }

    rows = dashboard.project_status_command_rows(payload)

    assert rows[0]["Step"] == "Read-only status snapshot"
    assert rows[0]["Command"] == "make status-check TOP_N=5"
    assert rows[0]["Reason"] == "Rebuild the local status snapshot before choosing a deeper workflow path."


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
    assert cards[0]["command"] == "make monthly"
    assert cards[1]["command"] == "make runbook-prices-broader"
    assert cards[2]["command"] == "make runbook-fundamentals-broader"
    assert cards[3]["command"] == "make action-queue-check TOP_N=10"
    assert "make action-queue-check top_n=10" in rendered
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
    assert "make onboarding" in rendered
    assert cards[0]["command"] == "make onboarding"
    assert "buy" not in rendered


def test_holdings_unlock_cards_use_review_fallback_when_action_is_missing():
    holdings = pd.DataFrame([{"Ticker": "AMD", "PrimaryPurpose": "Core Compounder"}])
    ladder = pd.DataFrame(
        [
            {
                "ticker": "AMD",
                "current_unlock_stage": "fundamentals",
                "next_unlock_goal": "Unlock DCF",
                "recommended_action": "",
                "focus_command": "",
                "example_command": "",
                "price_stage_status": "momentum_ready_short_history",
            }
        ]
    )

    cards = dashboard.holdings_unlock_cards(holdings, ladder, None, limit=1)

    assert cards[0]["kicker"] == "AMD"
    assert "review fundamentals path." in cards[0]["body"].lower()
    assert "not available" not in cards[0]["body"].lower()


def test_holdings_unlock_cards_use_runbook_fallback_when_action_is_missing():
    holdings = pd.DataFrame([{"Ticker": "AMD", "PrimaryPurpose": "Core Compounder"}])
    ladder = pd.DataFrame(
        [
            {
                "ticker": "AMD",
                "current_unlock_stage": "peers",
                "next_unlock_goal": "Unlock Peer Relative",
                "recommended_action": "",
                "focus_command": "",
                "example_command": "make runbook-peers",
                "price_stage_status": "momentum_ready_short_history",
            }
        ]
    )

    cards = dashboard.holdings_unlock_cards(holdings, ladder, None, limit=1)

    assert cards[0]["kicker"] == "AMD"
    assert cards[0]["command"] == "make runbook-peers"
    assert "staged local workflow next" in cards[0]["body"].lower()
    assert "not available" not in cards[0]["body"].lower()


def test_holdings_unlock_cards_keep_staged_import_front_doors_when_target_files_are_present():
    holdings = pd.DataFrame(
        [
            {"Ticker": "AMD", "PrimaryPurpose": "Core Compounder"},
            {"Ticker": "NVDA", "PrimaryPurpose": "Momentum Leader"},
            {"Ticker": "TSLA", "PrimaryPurpose": "Speculative Optionality"},
        ]
    )
    ladder = pd.DataFrame(
        [
            {
                "ticker": "AMD",
                "current_unlock_stage": "prices",
                "next_unlock_goal": "Unlock Monthly Picks",
                "recommended_action": "",
                "focus_command": "",
                "example_command": "",
                "target_file": "data/imports/prices.csv",
                "price_stage_status": "partial_price_history",
            },
            {
                "ticker": "NVDA",
                "current_unlock_stage": "fundamentals",
                "next_unlock_goal": "Unlock DCF",
                "recommended_action": "",
                "focus_command": "",
                "example_command": "",
                "target_file": "data/imports/fundamentals.csv",
                "price_stage_status": "momentum_ready_short_history",
            },
            {
                "ticker": "TSLA",
                "current_unlock_stage": "peers",
                "next_unlock_goal": "Unlock Peer Relative",
                "recommended_action": "",
                "focus_command": "",
                "example_command": "",
                "target_file": "data/imports/peers.csv",
                "price_stage_status": "momentum_ready_short_history",
            },
        ]
    )

    cards = dashboard.holdings_unlock_cards(holdings, ladder, None, limit=3)
    price_card = next(card for card in cards if card["kicker"] == "AMD")
    fundamentals_card = next(card for card in cards if card["kicker"] == "NVDA")
    peer_card = next(card for card in cards if card["kicker"] == "TSLA")

    assert price_card["command"] == "make price-validate"
    assert "make price-preview" in price_card["body"].lower()
    assert "make price-apply" in price_card["body"].lower()
    assert fundamentals_card["command"] == "make imports-validate"
    assert "staged fundamentals import" in fundamentals_card["body"].lower()
    assert peer_card["command"] == "make imports-validate"
    assert "staged peer import" in peer_card["body"].lower()


def test_holdings_unlock_cards_upgrade_generic_staged_price_note_to_explicit_follow_through():
    holdings = pd.DataFrame([{"Ticker": "AMD", "PrimaryPurpose": "Core Compounder"}])
    ladder = pd.DataFrame(
        [
            {
                "ticker": "AMD",
                "current_unlock_stage": "prices",
                "next_unlock_goal": "Unlock Monthly Picks",
                "recommended_action": "Use staged local imports if the free refresh fails.",
                "focus_command": "",
                "example_command": "",
                "target_file": "data/imports/prices.csv",
                "price_stage_status": "partial_price_history",
            }
        ]
    )

    cards = dashboard.holdings_unlock_cards(holdings, ladder, None, limit=1)

    assert cards[0]["command"] == "make price-validate"
    assert "make price-preview" in cards[0]["body"].lower()
    assert "make price-apply" in cards[0]["body"].lower()
    assert "use staged local imports if the free refresh fails" not in cards[0]["body"].lower()


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
                "example_command": "make sec-stage TICKERS=NVDA",
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


def test_holdings_deep_research_cards_use_lane_front_doors_when_commands_are_missing():
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
                "focus_command": "",
                "example_command": "",
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
                "focus_command": "",
                "example_command": "",
            }
        ]
    )

    cards = dashboard.holdings_deep_research_cards(holdings, sec_queue, peer_queue, limit=4)
    dcf_card = next(card for card in cards if card["title"] == "Unlock DCF")
    peer_card = next(card for card in cards if card["title"] == "Unlock Peer Relative")

    assert dcf_card["command"] == "make focus-fundamentals TICKER=NVDA"
    assert peer_card["command"] == "make focus-peers TICKER=TSLA"


def test_holdings_deep_research_cards_handle_missing_inputs_gracefully():
    cards = dashboard.holdings_deep_research_cards(None, None, None)
    rendered = " ".join(str(value) for card in cards for value in card.values()).lower()

    assert "no holdings deep-research board yet" in rendered
    assert cards[0]["command"] == "make onboarding"
    assert "make onboarding" in rendered
    assert "buy" not in rendered


def test_holdings_deep_research_cards_fall_back_to_onboarding_when_queues_are_missing():
    holdings = pd.DataFrame(
        [
            {"Ticker": "NVDA", "PrimaryPurpose": "Momentum Leader"},
            {"Ticker": "TSLA", "PrimaryPurpose": "Speculative Optionality"},
        ]
    )

    cards = dashboard.holdings_deep_research_cards(holdings, None, None)
    rendered = " ".join(str(value) for card in cards for value in card.values()).lower()

    assert len(cards) == 1
    assert cards[0]["title"] == "No holdings DCF / peer queue yet"
    assert cards[0]["command"] == "make onboarding"
    assert "make onboarding" in rendered
    assert "buy" not in rendered
    assert "sell" not in rendered


def test_holdings_deep_research_cards_use_review_fallback_when_action_is_missing():
    holdings = pd.DataFrame([{"Ticker": "AMD", "PrimaryPurpose": "Core Compounder"}])
    sec_queue = pd.DataFrame(
        [
            {
                "priority": 1,
                "ticker": "AMD",
                "theme": "Semis",
                "price_history_days": 84,
                "recommended_action": "",
            }
        ]
    )

    cards = dashboard.holdings_deep_research_cards(holdings, sec_queue, None, limit=1)

    assert cards[0]["kicker"] == "AMD"
    assert "review fundamentals path." in cards[0]["body"].lower()
    assert "not available" not in cards[0]["body"].lower()


def test_holdings_deep_research_cards_use_runbook_fallback_when_action_is_missing():
    holdings = pd.DataFrame([{"Ticker": "AMD", "PrimaryPurpose": "Core Compounder"}])
    sec_queue = pd.DataFrame(
        [
            {
                "priority": 1,
                "ticker": "AMD",
                "theme": "Semis",
                "price_history_days": 84,
                "recommended_action": "",
                "focus_command": "make runbook-fundamentals",
            }
        ]
    )

    cards = dashboard.holdings_deep_research_cards(holdings, sec_queue, None, limit=1)

    assert cards[0]["kicker"] == "AMD"
    assert cards[0]["command"] == "make runbook-fundamentals"
    assert "staged local workflow next" in cards[0]["body"].lower()
    assert "not available" not in cards[0]["body"].lower()


def test_holdings_deep_research_cards_use_peer_review_fallback_when_action_is_missing():
    holdings = pd.DataFrame([{"Ticker": "TSLA", "PrimaryPurpose": "Speculative Optionality"}])
    peer_queue = pd.DataFrame(
        [
            {
                "priority": 1,
                "ticker": "TSLA",
                "theme": "EV",
                "recommended_action": "",
            }
        ]
    )

    cards = dashboard.holdings_deep_research_cards(holdings, None, peer_queue, limit=1)

    assert cards[0]["kicker"] == "TSLA"
    assert "review peer path." in cards[0]["body"].lower()
    assert "not available" not in cards[0]["body"].lower()


def test_holdings_deep_research_cards_use_peer_runbook_fallback_when_action_is_missing():
    holdings = pd.DataFrame([{"Ticker": "TSLA", "PrimaryPurpose": "Speculative Optionality"}])
    peer_queue = pd.DataFrame(
        [
            {
                "priority": 1,
                "ticker": "TSLA",
                "theme": "EV",
                "recommended_action": "",
                "focus_command": "make runbook-peers",
            }
        ]
    )

    cards = dashboard.holdings_deep_research_cards(holdings, None, peer_queue, limit=1)

    assert cards[0]["kicker"] == "TSLA"
    assert cards[0]["command"] == "make runbook-peers"
    assert "staged local workflow next" in cards[0]["body"].lower()
    assert "not available" not in cards[0]["body"].lower()


def test_holdings_deep_research_cards_keep_staged_import_front_doors_when_commands_are_missing():
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
                "recommended_action": "",
                "focus_command": "",
                "example_command": "",
                "target_file": "data/imports/fundamentals.csv",
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
                "recommended_action": "",
                "focus_command": "",
                "example_command": "",
                "target_file": "data/imports/peers.csv",
            }
        ]
    )

    cards = dashboard.holdings_deep_research_cards(holdings, sec_queue, peer_queue, limit=4)
    fundamentals_card = next(card for card in cards if card["kicker"] == "NVDA")
    peer_card = next(card for card in cards if card["kicker"] == "TSLA")

    assert fundamentals_card["title"] == "Advance staged fundamentals import"
    assert fundamentals_card["command"] == "make imports-validate"
    assert "staged fundamentals" in fundamentals_card["body"].lower()
    assert peer_card["title"] == "Advance staged peer import"


def test_holdings_deep_research_cards_upgrade_generic_staged_notes_to_explicit_follow_through():
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
                "recommended_action": "Use staged local imports if the free refresh fails.",
                "focus_command": "make imports-validate",
                "example_command": "",
                "target_file": "data/imports/fundamentals.csv",
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
                "recommended_action": "Use staged local imports if the free refresh fails.",
                "focus_command": "make imports-validate",
                "example_command": "",
                "target_file": "data/imports/peers.csv",
            }
        ]
    )

    cards = dashboard.holdings_deep_research_cards(holdings, sec_queue, peer_queue, limit=4)
    fundamentals_card = next(card for card in cards if card["kicker"] == "NVDA")
    peer_card = next(card for card in cards if card["kicker"] == "TSLA")

    assert "make imports-preview" in fundamentals_card["body"].lower()
    assert "make imports-apply" in fundamentals_card["body"].lower()
    assert "use staged local imports if the free refresh fails" not in fundamentals_card["body"].lower()
    assert "make imports-preview" in peer_card["body"].lower()
    assert "make imports-apply" in peer_card["body"].lower()
    assert "use staged local imports if the free refresh fails" not in peer_card["body"].lower()
    assert peer_card["command"] == "make imports-validate"
    assert "staged peer import ready" in peer_card["body"].lower()


def test_holdings_unlock_cards_handle_missing_inputs_gracefully():
    cards = dashboard.holdings_unlock_cards(None, None, None)
    rendered = " ".join(str(value) for card in cards for value in card.values()).lower()

    assert "no holdings unlock board yet" in rendered
    assert cards[0]["command"] == "make onboarding"
    assert "make onboarding" in rendered
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
    assert cards[0]["command"] == "make onboarding"
    assert "make onboarding" in rendered
    assert "buy" not in rendered


def test_theme_unlock_cards_fall_back_to_universe_preview_when_only_holdings_context_exists():
    summary = pd.DataFrame(
        [
            {
                "group_type": "holdings",
                "group_name": "Current Holdings",
                "ticker_count": 2,
                "holdings_count": 2,
                "top_priority_stage": "fundamentals",
                "next_unlock_goal": "Unlock DCF",
                "recommended_action": "Run make status, then follow the printed fundamentals focus or runbook path for this group.",
                "focus_command": "make status",
                "example_command": "make runbook-fundamentals",
            }
        ]
    )

    cards = dashboard.theme_unlock_cards(summary)
    rendered = " ".join(str(value) for card in cards for value in card.values()).lower()

    assert len(cards) == 1
    assert cards[0]["title"] == "No grouped theme unlocks yet"
    assert cards[0]["command"] == "make universe-preview"
    assert "make universe-preview" in rendered
    assert "buy" not in rendered
    assert "sell" not in rendered


def test_theme_unlock_cards_use_review_fallback_when_action_is_missing():
    summary = pd.DataFrame(
        [
            {
                "group_type": "theme",
                "group_name": "AI Semiconductors",
                "ticker_count": 3,
                "holdings_count": 1,
                "top_priority_stage": "peers",
                "next_unlock_goal": "Unlock Peer Relative",
                "recommended_action": "",
                "focus_command": "",
                "example_command": "",
            }
        ]
    )

    cards = dashboard.theme_unlock_cards(summary, limit=1)

    assert cards[1]["kicker"] == "AI Semiconductors"
    assert cards[1]["command"] == "make runbook-peers-broader"
    assert "staged local workflow next" in cards[1]["body"].lower()
    assert "not available" not in cards[1]["body"].lower()


def test_theme_unlock_cards_use_runbook_fallback_when_action_is_missing():
    summary = pd.DataFrame(
        [
            {
                "group_type": "theme",
                "group_name": "AI Semiconductors",
                "ticker_count": 3,
                "holdings_count": 1,
                "top_priority_stage": "peers",
                "next_unlock_goal": "Unlock Peer Relative",
                "recommended_action": "",
                "focus_command": "",
                "example_command": "make runbook-peers",
            }
        ]
    )

    cards = dashboard.theme_unlock_cards(summary, limit=1)

    assert cards[1]["kicker"] == "AI Semiconductors"
    assert cards[1]["command"] == "make runbook-peers"
    assert "staged local workflow next" in cards[1]["body"].lower()


def test_theme_unlock_cards_keep_staged_import_front_doors_when_target_files_are_present():
    summary = pd.DataFrame(
        [
            {
                "group_type": "theme",
                "group_name": "AI Semiconductors",
                "ticker_count": 3,
                "holdings_count": 1,
                "top_priority_stage": "prices",
                "next_unlock_goal": "Unlock Monthly Picks",
                "recommended_action": "",
                "focus_command": "",
                "example_command": "",
                "target_file": "data/imports/prices.csv",
            },
            {
                "group_type": "sector_etf",
                "group_name": "SMH",
                "ticker_count": 8,
                "holdings_count": 1,
                "top_priority_stage": "fundamentals",
                "next_unlock_goal": "Unlock DCF",
                "recommended_action": "",
                "focus_command": "",
                "example_command": "",
                "target_file": "data/imports/fundamentals.csv",
            },
            {
                "group_type": "theme",
                "group_name": "EV Leaders",
                "ticker_count": 4,
                "holdings_count": 1,
                "top_priority_stage": "peers",
                "next_unlock_goal": "Unlock Peer Relative",
                "recommended_action": "",
                "focus_command": "",
                "example_command": "",
                "target_file": "data/imports/peers.csv",
            },
        ]
    )

    cards = dashboard.theme_unlock_cards(summary, limit=3)
    price_card = next(card for card in cards if card["kicker"] == "AI Semiconductors")
    fundamentals_card = next(card for card in cards if card["kicker"] == "SMH")
    peer_card = next(card for card in cards if card["kicker"] == "EV Leaders")

    assert price_card["command"] == "make price-validate"
    assert "make price-preview" in price_card["body"].lower()
    assert "make price-apply" in price_card["body"].lower()
    assert fundamentals_card["command"] == "make imports-validate"
    assert "staged fundamentals import" in fundamentals_card["body"].lower()
    assert peer_card["command"] == "make imports-validate"
    assert "staged peer import" in peer_card["body"].lower()


def test_theme_unlock_cards_upgrade_generic_staged_price_note_to_explicit_follow_through():
    summary = pd.DataFrame(
        [
            {
                "group_type": "theme",
                "group_name": "AI Semiconductors",
                "ticker_count": 3,
                "holdings_count": 1,
                "top_priority_stage": "prices",
                "next_unlock_goal": "Unlock Monthly Picks",
                "recommended_action": "Use staged local imports if the free refresh fails.",
                "focus_command": "",
                "example_command": "",
                "target_file": "data/imports/prices.csv",
            }
        ]
    )

    cards = dashboard.theme_unlock_cards(summary, limit=1)

    assert cards[1]["command"] == "make price-validate"
    assert "make price-preview" in cards[1]["body"].lower()
    assert "make price-apply" in cards[1]["body"].lower()
    assert "use staged local imports if the free refresh fails" not in cards[1]["body"].lower()
    assert "not available" not in cards[1]["body"].lower()


def test_unlock_cards_use_stage_front_doors_when_commands_are_missing():
    holdings = pd.DataFrame(
        [
            {"Ticker": "NVDA", "PrimaryPurpose": "Momentum Leader"},
        ]
    )
    ladder = pd.DataFrame(
        [
            {
                "ticker": "NVDA",
                "current_unlock_stage": "fundamentals",
                "next_unlock_goal": "Unlock DCF",
                "recommended_action": "Stage verified fundamentals.",
                "focus_command": "",
                "example_command": "",
                "price_stage_status": "momentum_ready_short_history",
            },
        ]
    )
    holdings_summary = pd.DataFrame(
        [
            {
                "group_type": "holdings",
                "group_name": "Current Holdings",
                "ticker_count": 1,
                "holdings_count": 1,
                "top_priority_stage": "fundamentals",
                "next_unlock_goal": "Unlock DCF",
                "representative_tickers": "NVDA",
                "focus_command": "",
                "example_command": "",
            }
        ]
    )
    theme_summary = pd.DataFrame(
        [
            {
                "group_type": "theme",
                "group_name": "AI Semiconductors",
                "ticker_count": 3,
                "holdings_count": 1,
                "top_priority_stage": "peers",
                "next_unlock_goal": "Unlock Peer Relative",
                "recommended_action": "Build transparent peer context.",
                "focus_command": "",
                "example_command": "",
            }
        ]
    )

    holding_cards = dashboard.holdings_unlock_cards(holdings, ladder, holdings_summary, limit=2)
    theme_cards = dashboard.theme_unlock_cards(theme_summary, limit=2)

    assert holding_cards[0]["command"] == "make runbook-fundamentals-broader"
    assert any(card.get("command") == "make focus-fundamentals TICKER=NVDA" for card in holding_cards)
    assert theme_cards[0]["command"] == "make runbook-peers-broader"
    assert any(card.get("command") == "make runbook-peers-broader" for card in theme_cards)


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
    assert any(card.get("command") == "make focus-fundamentals TICKER=NVDA" for card in cards)
    assert any(card.get("command") == "make focus-peers TICKER=SMH" for card in cards)
    assert "ai semiconductors" in rendered
    assert "semiconductor etf" in rendered
    assert "buy" not in rendered
    assert "sell" not in rendered


def test_theme_deep_research_cards_handle_missing_inputs_gracefully():
    cards = dashboard.theme_deep_research_cards(None, None)
    rendered = " ".join(str(value) for card in cards for value in card.values()).lower()

    assert "no theme deep-research board yet" in rendered
    assert cards[0]["command"] == "make onboarding"
    assert "make onboarding" in rendered
    assert "buy" not in rendered


def test_theme_deep_research_cards_use_review_fallback_when_action_is_missing():
    sec_queue = pd.DataFrame(
        [
            {
                "priority": 1,
                "ticker": "AMD",
                "theme": "Semis",
                "is_holding": False,
                "recommended_action": "",
            }
        ]
    )

    cards = dashboard.theme_deep_research_cards(sec_queue, None, limit=1)

    assert cards[0]["kicker"] == "Semis"
    assert "review fundamentals path." in cards[0]["body"].lower()
    assert "not available" not in cards[0]["body"].lower()


def test_theme_deep_research_cards_use_runbook_fallback_when_action_is_missing():
    sec_queue = pd.DataFrame(
        [
            {
                "priority": 1,
                "ticker": "AMD",
                "theme": "Semis",
                "is_holding": False,
                "recommended_action": "",
                "focus_command": "make runbook-fundamentals",
            }
        ]
    )

    cards = dashboard.theme_deep_research_cards(sec_queue, None, limit=1)

    assert cards[0]["kicker"] == "Semis"
    assert cards[0]["command"] == "make runbook-fundamentals"
    assert "staged local workflow next" in cards[0]["body"].lower()
    assert "not available" not in cards[0]["body"].lower()


def test_theme_deep_research_cards_use_peer_review_fallback_when_action_is_missing():
    peer_queue = pd.DataFrame(
        [
            {
                "priority": 1,
                "ticker": "SMH",
                "theme": "Semiconductor ETF",
                "is_holding": False,
                "recommended_action": "",
            }
        ]
    )

    cards = dashboard.theme_deep_research_cards(None, peer_queue, limit=1)

    assert cards[0]["kicker"] == "Semiconductor ETF"
    assert "review peer path." in cards[0]["body"].lower()
    assert "not available" not in cards[0]["body"].lower()


def test_theme_deep_research_cards_use_peer_runbook_fallback_when_action_is_missing():
    peer_queue = pd.DataFrame(
        [
            {
                "priority": 1,
                "ticker": "SMH",
                "theme": "Semiconductor ETF",
                "is_holding": False,
                "recommended_action": "",
                "focus_command": "make runbook-peers",
            }
        ]
    )

    cards = dashboard.theme_deep_research_cards(None, peer_queue, limit=1)

    assert cards[0]["kicker"] == "Semiconductor ETF"
    assert cards[0]["command"] == "make runbook-peers"
    assert "staged local workflow next" in cards[0]["body"].lower()
    assert "not available" not in cards[0]["body"].lower()


def test_theme_deep_research_cards_keep_staged_import_front_doors_when_commands_are_missing():
    sec_queue = pd.DataFrame(
        [
            {
                "priority": 1,
                "ticker": "NVDA",
                "theme": "AI Semiconductors",
                "is_holding": True,
                "recommended_action": "",
                "focus_command": "",
                "example_command": "",
                "target_file": "data/imports/fundamentals.csv",
            }
        ]
    )
    peer_queue = pd.DataFrame(
        [
            {
                "priority": 1,
                "ticker": "SMH",
                "theme": "Semiconductor ETF",
                "is_holding": False,
                "recommended_action": "",
                "focus_command": "",
                "example_command": "",
                "target_file": "data/imports/peers.csv",
            }
        ]
    )

    cards = dashboard.theme_deep_research_cards(sec_queue, peer_queue, limit=4)
    fundamentals_card = next(card for card in cards if card["kicker"] == "AI Semiconductors")
    peer_card = next(card for card in cards if card["kicker"] == "Semiconductor ETF")

    assert fundamentals_card["title"] == "Advance staged fundamentals import"
    assert fundamentals_card["command"] == "make imports-validate"
    assert "staged fundamentals import" in fundamentals_card["body"].lower()
    assert "make imports-preview" in fundamentals_card["body"].lower()
    assert "make imports-apply" in fundamentals_card["body"].lower()
    assert peer_card["title"] == "Advance staged peer import"
    assert peer_card["command"] == "make imports-validate"
    assert "staged peers import" in peer_card["body"].lower()
    assert "make imports-preview" in peer_card["body"].lower()
    assert "make imports-apply" in peer_card["body"].lower()


def test_theme_deep_research_cards_upgrade_generic_staged_notes_to_explicit_follow_through():
    sec_queue = pd.DataFrame(
        [
            {
                "priority": 1,
                "ticker": "NVDA",
                "theme": "AI Semiconductors",
                "is_holding": True,
                "recommended_action": "Use staged local imports if the free refresh fails.",
                "focus_command": "make imports-validate",
                "example_command": "",
                "target_file": "data/imports/fundamentals.csv",
            }
        ]
    )
    peer_queue = pd.DataFrame(
        [
            {
                "priority": 1,
                "ticker": "SMH",
                "theme": "Semiconductor ETF",
                "is_holding": False,
                "recommended_action": "Use staged local imports if the free refresh fails.",
                "focus_command": "make imports-validate",
                "example_command": "",
                "target_file": "data/imports/peers.csv",
            }
        ]
    )

    cards = dashboard.theme_deep_research_cards(sec_queue, peer_queue, limit=4)
    fundamentals_card = next(card for card in cards if card["kicker"] == "AI Semiconductors")
    peer_card = next(card for card in cards if card["kicker"] == "Semiconductor ETF")

    assert "make imports-preview" in fundamentals_card["body"].lower()
    assert "make imports-apply" in fundamentals_card["body"].lower()
    assert "use staged local imports if the free refresh fails" not in fundamentals_card["body"].lower()
    assert "make imports-preview" in peer_card["body"].lower()
    assert "make imports-apply" in peer_card["body"].lower()
    assert "use staged local imports if the free refresh fails" not in peer_card["body"].lower()


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
            "peer_ready": [False, False, False],
            "focus_command": ["make focus-peers TICKER=NVDA", "make imports-validate", "make focus-peers TICKER=TSLA"],
            "target_file": ["data/imports/peers.csv", "data/imports/peers.csv", "data/imports/peers.csv"],
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
    assert cards[0]["command"] == "make runbook-prices-broader"
    assert cards[1]["command"] == "make runbook-fundamentals-broader"
    assert cards[2]["command"] == "make runbook-peers-broader"
    assert "2 urgent price gaps" in rendered
    assert "1 holdings-first dcf unlocks" in rendered
    assert "2 missing peer mappings" in rendered
    assert "1 mapped follow-through" in rendered
    assert "1 staged peer import already need make imports-validate, make imports-preview, and make imports-apply" in rendered
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


def test_overview_deep_research_leverage_cards_use_lane_front_doors_when_commands_are_missing():
    holdings = pd.DataFrame([{"Ticker": "NVDA"}, {"Ticker": "TSLA"}])
    sec_queue = pd.DataFrame(
        [
            {
                "priority": 1,
                "ticker": "NVDA",
                "theme": "AI Semiconductors",
                "recommended_action": "Stage or add richer verified fundamentals to close the remaining DCF input gaps.",
                "focus_command": "",
                "example_command": "",
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
                "focus_command": "",
                "example_command": "",
            }
        ]
    )

    cards = dashboard.overview_deep_research_leverage_cards(holdings, sec_queue, peer_queue)
    dcf_card = next(card for card in cards if card["kicker"] == "DCF LEVERAGE")
    peer_card = next(card for card in cards if card["kicker"] == "PEER LEVERAGE")

    assert cards[0]["command"] == "make focus-fundamentals TICKER=NVDA"
    assert dcf_card["command"] == "make focus-fundamentals TICKER=NVDA"
    assert peer_card["command"] == "make focus-peers TICKER=TSLA"


def test_overview_deep_research_leverage_cards_use_staged_peer_import_title_when_queue_is_staged():
    holdings = pd.DataFrame([{"Ticker": "TSLA"}])
    sec_queue = pd.DataFrame(
        [
            {
                "priority": 2,
                "ticker": "NVDA",
                "theme": "AI Semiconductors",
                "recommended_action": "Stage or add richer verified fundamentals to close the remaining DCF input gaps.",
            }
        ]
    )
    peer_queue = pd.DataFrame(
        [
            {
                "priority": 1,
                "ticker": "TSLA",
                "theme": "EV",
                "has_peer_mapping": True,
                "peer_ready": False,
                "recommended_action": "Run make imports-validate, then make imports-preview, then make imports-apply, then make status to confirm the live local peer inputs.",
                "focus_command": "make imports-validate",
                "example_command": "make imports-preview",
                "target_file": "data/imports/peers.csv",
            }
        ]
    )

    cards = dashboard.overview_deep_research_leverage_cards(holdings, sec_queue, peer_queue)
    rendered = " ".join(str(value) for card in cards for value in card.values()).lower()

    assert "staged peer import path" in rendered
    assert "make imports-validate" in rendered
    assert "staged import" in rendered
    assert "buy" not in rendered
    assert "sell" not in rendered


def test_overview_deep_research_leverage_cards_handle_missing_inputs_gracefully():
    cards = dashboard.overview_deep_research_leverage_cards(None, None, None)
    rendered = " ".join(str(value) for card in cards for value in card.values()).lower()

    assert len(cards) == 1
    assert "no deep-research leverage view yet" in rendered
    assert cards[0]["command"] == "make onboarding"
    assert "make onboarding" in rendered


def test_overview_deep_research_leverage_cards_use_review_fallback_when_action_is_missing():
    holdings = pd.DataFrame([{"Ticker": "NVDA"}])
    sec_queue = pd.DataFrame(
        [
            {
                "priority": 1,
                "ticker": "NVDA",
                "theme": "AI Semiconductors",
                "recommended_action": "",
            }
        ]
    )

    cards = dashboard.overview_deep_research_leverage_cards(holdings, sec_queue, None)
    rendered = " ".join(str(value) for card in cards for value in card.values()).lower()
    dcf_card = next(card for card in cards if card["kicker"] == "DCF LEVERAGE")

    assert "review fundamentals path." in dcf_card["body"].lower()
    assert "not available" not in dcf_card["body"].lower()
    assert "buy" not in rendered
    assert "sell" not in rendered


def test_overview_deep_research_leverage_cards_use_runbook_fallback_when_action_is_missing():
    holdings = pd.DataFrame([{"Ticker": "NVDA"}])
    sec_queue = pd.DataFrame(
        [
            {
                "priority": 1,
                "ticker": "NVDA",
                "theme": "AI Semiconductors",
                "recommended_action": "",
                "focus_command": "make runbook-fundamentals",
            }
        ]
    )

    cards = dashboard.overview_deep_research_leverage_cards(holdings, sec_queue, None)
    dcf_card = next(card for card in cards if card["kicker"] == "DCF LEVERAGE")

    assert dcf_card["command"] == "make runbook-fundamentals"
    assert "staged local workflow next" in dcf_card["body"].lower()
    assert "not available" not in dcf_card["body"].lower()


def test_overview_deep_research_leverage_cards_use_peer_review_fallback_when_action_is_missing():
    holdings = pd.DataFrame([{"Ticker": "TSLA"}])
    peer_queue = pd.DataFrame(
        [
            {
                "priority": 1,
                "ticker": "TSLA",
                "theme": "EV",
                "recommended_action": "",
            }
        ]
    )

    cards = dashboard.overview_deep_research_leverage_cards(holdings, None, peer_queue)
    rendered = " ".join(str(value) for card in cards for value in card.values()).lower()
    peer_card = next(card for card in cards if card["kicker"] == "PEER LEVERAGE")

    assert "review peer path." in peer_card["body"].lower()
    assert "not available" not in peer_card["body"].lower()
    assert "buy" not in rendered
    assert "sell" not in rendered


def test_overview_deep_research_leverage_cards_use_peer_runbook_fallback_when_action_is_missing():
    holdings = pd.DataFrame([{"Ticker": "TSLA"}])
    peer_queue = pd.DataFrame(
        [
            {
                "priority": 1,
                "ticker": "TSLA",
                "theme": "EV",
                "recommended_action": "",
                "focus_command": "make runbook-peers",
            }
        ]
    )

    cards = dashboard.overview_deep_research_leverage_cards(holdings, None, peer_queue)
    peer_card = next(card for card in cards if card["kicker"] == "PEER LEVERAGE")

    assert peer_card["command"] == "make runbook-peers"
    assert "staged local workflow next" in peer_card["body"].lower()
    assert "not available" not in peer_card["body"].lower()


def test_overview_deep_research_leverage_cards_keep_staged_import_paths_when_commands_are_missing():
    holdings = pd.DataFrame([{"Ticker": "NVDA"}, {"Ticker": "TSLA"}])
    sec_queue = pd.DataFrame(
        [
            {
                "priority": 1,
                "ticker": "NVDA",
                "theme": "AI Semiconductors",
                "recommended_action": "",
                "focus_command": "",
                "example_command": "",
                "target_file": "data/imports/fundamentals.csv",
            }
        ]
    )
    peer_queue = pd.DataFrame(
        [
            {
                "priority": 1,
                "ticker": "TSLA",
                "theme": "EV",
                "recommended_action": "",
                "focus_command": "",
                "example_command": "",
                "target_file": "data/imports/peers.csv",
            }
        ]
    )

    cards = dashboard.overview_deep_research_leverage_cards(holdings, sec_queue, peer_queue)
    fundamentals_card = next(card for card in cards if card["kicker"] == "DCF LEVERAGE")
    peer_card = next(card for card in cards if card["kicker"] == "PEER LEVERAGE")

    assert fundamentals_card["title"] == "Staged fundamentals import path"
    assert fundamentals_card["command"] == "make imports-validate"
    assert "staged fundamentals import" in fundamentals_card["body"].lower()
    assert "make imports-preview" in fundamentals_card["body"].lower()
    assert "make imports-apply" in fundamentals_card["body"].lower()
    assert peer_card["title"] == "Staged peer import path"
    assert peer_card["command"] == "make imports-validate"
    assert "staged peer import" in peer_card["body"].lower()
    assert "make imports-preview" in peer_card["body"].lower()
    assert "make imports-apply" in peer_card["body"].lower()


def test_overview_deep_research_leverage_cards_upgrade_generic_staged_notes_to_explicit_follow_through():
    holdings = pd.DataFrame([{"Ticker": "NVDA"}, {"Ticker": "TSLA"}])
    sec_queue = pd.DataFrame(
        [
            {
                "priority": 1,
                "ticker": "NVDA",
                "theme": "AI Semiconductors",
                "recommended_action": "Use staged local imports if the free refresh fails.",
                "focus_command": "make imports-validate",
                "example_command": "",
                "target_file": "data/imports/fundamentals.csv",
            }
        ]
    )
    peer_queue = pd.DataFrame(
        [
            {
                "priority": 1,
                "ticker": "TSLA",
                "theme": "EV",
                "recommended_action": "Use staged local imports if the free refresh fails.",
                "focus_command": "make imports-validate",
                "example_command": "",
                "target_file": "data/imports/peers.csv",
            }
        ]
    )

    cards = dashboard.overview_deep_research_leverage_cards(holdings, sec_queue, peer_queue)
    fundamentals_card = next(card for card in cards if card["kicker"] == "DCF LEVERAGE")
    peer_card = next(card for card in cards if card["kicker"] == "PEER LEVERAGE")

    assert "make imports-preview" in fundamentals_card["body"].lower()
    assert "make imports-apply" in fundamentals_card["body"].lower()
    assert "use staged local imports if the free refresh fails" not in fundamentals_card["body"].lower()
    assert "make imports-preview" in peer_card["body"].lower()
    assert "make imports-apply" in peer_card["body"].lower()
    assert "use staged local imports if the free refresh fails" not in peer_card["body"].lower()


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
    assert cards[0]["command"] == "make focus-fundamentals TICKER=NVDA"
    assert "current holding" in rendered
    assert "buy" not in rendered
    assert "sell" not in rendered


def test_overview_deep_research_priority_bridge_cards_keep_staged_peer_command_when_present():
    holdings = pd.DataFrame([{"Ticker": "TSLA"}])
    peer_queue = pd.DataFrame(
        [
            {
                "priority": 1,
                "ticker": "TSLA",
                "theme": "EV",
                "has_peer_mapping": True,
                "peer_ready": False,
                "recommended_action": "Run make imports-validate, then make imports-preview, then make imports-apply, then make status to confirm the live local peer inputs.",
                "focus_command": "make imports-validate",
                "example_command": "make imports-preview",
                "target_file": "data/imports/peers.csv",
            }
        ]
    )

    cards = dashboard.overview_deep_research_priority_bridge_cards(holdings, None, peer_queue, limit=1)
    rendered = " ".join(str(value) for card in cards for value in card.values()).lower()

    assert cards[0]["kicker"] == "TSLA"
    assert cards[0]["title"] == "Advance staged peer import"
    assert cards[0]["command"] == "make imports-validate"
    assert "advance staged peer import" in rendered
    assert "make imports-preview" in rendered
    assert "make imports-apply" in rendered
    assert "buy" not in rendered
    assert "sell" not in rendered


def test_overview_deep_research_priority_bridge_cards_use_review_fallback_when_action_is_missing():
    holdings = pd.DataFrame([{"Ticker": "AMD"}])
    sec_queue = pd.DataFrame(
        [
            {
                "priority": 1,
                "ticker": "AMD",
                "theme": "Semis",
                "recommended_action": "",
            }
        ]
    )

    cards = dashboard.overview_deep_research_priority_bridge_cards(holdings, sec_queue, None, limit=1)

    assert cards[0]["kicker"] == "AMD"
    assert "review fundamentals path." in cards[0]["body"].lower()
    assert cards[0]["command_reason"].lower() == "review fundamentals path."
    assert "not available" not in cards[0]["body"].lower()


def test_overview_deep_research_priority_bridge_cards_use_runbook_fallback_when_action_is_missing():
    holdings = pd.DataFrame([{"Ticker": "AMD"}])
    sec_queue = pd.DataFrame(
        [
            {
                "priority": 1,
                "ticker": "AMD",
                "theme": "Semis",
                "recommended_action": "",
                "focus_command": "make runbook-fundamentals",
            }
        ]
    )

    cards = dashboard.overview_deep_research_priority_bridge_cards(holdings, sec_queue, None, limit=1)

    assert cards[0]["kicker"] == "AMD"
    assert cards[0]["command"] == "make runbook-fundamentals"
    assert "staged local workflow next" in cards[0]["body"].lower()
    assert "staged local workflow next" in cards[0]["command_reason"].lower()
    assert "not available" not in cards[0]["body"].lower()


def test_overview_deep_research_priority_bridge_cards_use_peer_review_fallback_when_action_is_missing():
    holdings = pd.DataFrame([{"Ticker": "TSLA"}])
    peer_queue = pd.DataFrame(
        [
            {
                "priority": 1,
                "ticker": "TSLA",
                "theme": "EV",
                "recommended_action": "",
            }
        ]
    )

    cards = dashboard.overview_deep_research_priority_bridge_cards(holdings, None, peer_queue, limit=1)

    assert cards[0]["kicker"] == "TSLA"
    assert "review peer path." in cards[0]["body"].lower()
    assert cards[0]["command_reason"].lower() == "review peer path."
    assert "not available" not in cards[0]["body"].lower()


def test_overview_deep_research_priority_bridge_cards_use_peer_runbook_fallback_when_action_is_missing():
    holdings = pd.DataFrame([{"Ticker": "TSLA"}])
    peer_queue = pd.DataFrame(
        [
            {
                "priority": 1,
                "ticker": "TSLA",
                "theme": "EV",
                "recommended_action": "",
                "focus_command": "make runbook-peers",
            }
        ]
    )

    cards = dashboard.overview_deep_research_priority_bridge_cards(holdings, None, peer_queue, limit=1)

    assert cards[0]["kicker"] == "TSLA"
    assert cards[0]["command"] == "make runbook-peers"
    assert "staged local workflow next" in cards[0]["body"].lower()
    assert "staged local workflow next" in cards[0]["command_reason"].lower()
    assert "not available" not in cards[0]["body"].lower()


def test_overview_deep_research_priority_bridge_cards_keep_staged_import_paths_when_commands_are_missing():
    holdings = pd.DataFrame([{"Ticker": "NVDA"}, {"Ticker": "TSLA"}])
    sec_queue = pd.DataFrame(
        [
            {
                "priority": 1,
                "ticker": "NVDA",
                "theme": "AI Semiconductors",
                "recommended_action": "",
                "focus_command": "",
                "example_command": "",
                "target_file": "data/imports/fundamentals.csv",
            }
        ]
    )
    peer_queue = pd.DataFrame(
        [
            {
                "priority": 1,
                "ticker": "TSLA",
                "theme": "EV",
                "recommended_action": "",
                "focus_command": "",
                "example_command": "",
                "target_file": "data/imports/peers.csv",
            }
        ]
    )

    cards = dashboard.overview_deep_research_priority_bridge_cards(holdings, sec_queue, peer_queue, limit=3)
    fundamentals_card = next(card for card in cards if card["kicker"] == "NVDA")
    peer_card = next(card for card in cards if card["kicker"] == "TSLA")

    assert fundamentals_card["title"] == "Advance staged fundamentals import"
    assert fundamentals_card["command"] == "make imports-validate"
    assert "staged fundamentals import" in fundamentals_card["body"].lower()
    assert "make imports-preview" in fundamentals_card["command_reason"].lower()
    assert peer_card["title"] == "Advance staged peer import"
    assert peer_card["command"] == "make imports-validate"
    assert "staged peer import" in peer_card["body"].lower()


def test_overview_deep_research_priority_bridge_cards_upgrade_generic_staged_notes_to_explicit_follow_through():
    holdings = pd.DataFrame([{"Ticker": "NVDA"}, {"Ticker": "TSLA"}])
    sec_queue = pd.DataFrame(
        [
            {
                "priority": 1,
                "ticker": "NVDA",
                "theme": "AI Semiconductors",
                "recommended_action": "Use staged local imports if the free refresh fails.",
                "focus_command": "make imports-validate",
                "example_command": "",
                "target_file": "data/imports/fundamentals.csv",
            }
        ]
    )
    peer_queue = pd.DataFrame(
        [
            {
                "priority": 1,
                "ticker": "TSLA",
                "theme": "EV",
                "recommended_action": "Use staged local imports if the free refresh fails.",
                "focus_command": "make imports-validate",
                "example_command": "",
                "target_file": "data/imports/peers.csv",
            }
        ]
    )

    cards = dashboard.overview_deep_research_priority_bridge_cards(holdings, sec_queue, peer_queue, limit=3)
    fundamentals_card = next(card for card in cards if card["kicker"] == "NVDA")
    peer_card = next(card for card in cards if card["kicker"] == "TSLA")

    assert "make imports-preview" in fundamentals_card["body"].lower()
    assert "make imports-apply" in fundamentals_card["body"].lower()
    assert "use staged local imports if the free refresh fails" not in fundamentals_card["body"].lower()
    assert "make imports-preview" in fundamentals_card["command_reason"].lower()
    assert "make imports-preview" in peer_card["body"].lower()
    assert "make imports-apply" in peer_card["body"].lower()
    assert "use staged local imports if the free refresh fails" not in peer_card["body"].lower()
    assert "make imports-preview" in peer_card["command_reason"].lower()
    assert "make imports-preview" in peer_card["command_reason"].lower()


def test_overview_deep_research_priority_bridge_cards_handle_missing_inputs_gracefully():
    cards = dashboard.overview_deep_research_priority_bridge_cards(None, None, None)
    rendered = " ".join(str(value) for card in cards for value in card.values()).lower()

    assert len(cards) == 1
    assert "no deep-research shortlist yet" in rendered
    assert cards[0]["command"] == "make onboarding"
    assert "make onboarding" in rendered
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
                "example_command": "make sec-stage TICKERS=NVDA",
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
    assert cards[0]["command"] == "make sec-stage TICKERS=NVDA"
    assert "make sec-stage tickers=nvda" in rendered
    assert "stage or add richer verified fundamentals" in rendered
    assert cards[2]["title"] == "Data Health"
    assert "stock report beta" in rendered
    assert "buy" not in rendered
    assert "sell" not in rendered


def test_overview_deep_research_handoff_cards_keep_staged_peer_reason_and_command():
    holdings = pd.DataFrame([{"Ticker": "TSLA"}])
    peer_queue = pd.DataFrame(
        [
            {
                "priority": 1,
                "ticker": "TSLA",
                "theme": "EV",
                "has_peer_mapping": True,
                "peer_ready": False,
                "recommended_action": "Run make imports-validate, then make imports-preview, then make imports-apply, then make status to confirm the live local peer inputs.",
                "focus_command": "make imports-validate",
                "example_command": "make imports-preview",
                "target_file": "data/imports/peers.csv",
            }
        ]
    )
    payload = {"recommended_next_commands": ["make status", "make verify", "make dashboard-smoke"]}

    cards = dashboard.overview_deep_research_handoff_cards(holdings, None, peer_queue, payload, None)
    rendered = " ".join(str(value) for card in cards for value in card.values()).lower()

    assert cards[0]["title"] == "TSLA"
    assert cards[0]["command"] == "make imports-validate"
    assert cards[1]["title"] == "make imports-validate"
    assert "make imports-preview" in rendered
    assert "make imports-apply" in rendered
    assert "make status-check top_n=5" in rendered
    assert "buy" not in rendered
    assert "sell" not in rendered


def test_overview_deep_research_handoff_cards_keep_staged_fundamentals_reason_and_command_when_commands_are_missing():
    holdings = pd.DataFrame([{"Ticker": "NVDA"}])
    sec_queue = pd.DataFrame(
        [
            {
                "priority": 1,
                "ticker": "NVDA",
                "theme": "AI Semiconductors",
                "recommended_action": "",
                "focus_command": "",
                "example_command": "",
                "target_file": "data/imports/fundamentals.csv",
            }
        ]
    )
    payload = {"recommended_next_commands": ["make status", "make verify", "make dashboard-smoke"]}

    cards = dashboard.overview_deep_research_handoff_cards(holdings, sec_queue, None, payload, None)
    rendered = " ".join(str(value) for card in cards for value in card.values()).lower()

    assert cards[0]["title"] == "NVDA"
    assert cards[0]["command"] == "make imports-validate"
    assert cards[1]["title"] == "make imports-validate"
    assert "staged fundamentals import" in cards[1]["body"].lower()
    assert "make imports-preview" in rendered
    assert "make imports-apply" in rendered
    assert "buy" not in rendered
    assert "sell" not in rendered


def test_overview_deep_research_handoff_cards_keep_runbook_fundamentals_reason_and_command():
    holdings = pd.DataFrame([{"Ticker": "NVDA"}])
    sec_queue = pd.DataFrame(
        [
            {
                "priority": 1,
                "ticker": "NVDA",
                "theme": "AI Semiconductors",
                "recommended_action": "",
                "focus_command": "make runbook-fundamentals",
                "example_command": "",
            }
        ]
    )
    payload = {"recommended_next_commands": ["make status", "make verify", "make dashboard-smoke"]}

    cards = dashboard.overview_deep_research_handoff_cards(holdings, sec_queue, None, payload, None)
    rendered = " ".join(str(value) for card in cards for value in card.values()).lower()

    assert cards[0]["title"] == "NVDA"
    assert cards[0]["command"] == "make runbook-fundamentals"
    assert cards[1]["title"] == "make runbook-fundamentals"
    assert "staged local workflow next" in cards[1]["body"].lower()
    assert "buy" not in rendered
    assert "sell" not in rendered


def test_overview_deep_research_handoff_cards_keep_runbook_peer_reason_and_command():
    holdings = pd.DataFrame([{"Ticker": "TSLA"}])
    peer_queue = pd.DataFrame(
        [
            {
                "priority": 1,
                "ticker": "TSLA",
                "theme": "EV",
                "recommended_action": "",
                "focus_command": "make runbook-peers",
                "example_command": "",
            }
        ]
    )
    payload = {"recommended_next_commands": ["make status", "make verify", "make dashboard-smoke"]}

    cards = dashboard.overview_deep_research_handoff_cards(holdings, None, peer_queue, payload, None)
    rendered = " ".join(str(value) for card in cards for value in card.values()).lower()

    assert cards[0]["title"] == "TSLA"
    assert cards[0]["command"] == "make runbook-peers"
    assert cards[1]["title"] == "make runbook-peers"
    assert "staged local workflow next" in cards[1]["body"].lower()
    assert "buy" not in rendered
    assert "sell" not in rendered


def test_overview_deep_research_handoff_cards_fall_back_to_safe_command():
    cards = dashboard.overview_deep_research_handoff_cards(None, None, None, None, None)
    rendered = " ".join(str(value) for card in cards for value in card.values()).lower()

    assert len(cards) == 3
    assert cards[0]["title"] == "No deep-research shortlist yet"
    assert cards[0]["command"] == "make onboarding"
    assert cards[1]["title"] == "make onboarding"
    assert cards[2]["title"] == "Data Health"
    assert "refresh the onboarding outputs" in rendered
    assert "sec stage and peer-mapping queues" in rendered
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
    assert cards[0]["command"] == "make monthly"
    assert cards[1]["command"] == "make runbook-prices-broader"
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
    assert cards[0]["command"] == "make onboarding"
    assert "make onboarding" in rendered
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
    assert cards[0]["command"] == "make verify"
    assert cards[1]["title"] == "Monthly Picks"
    assert cards[1]["command"] == "make monthly"
    assert "holding" in rendered
    assert "deeper single-name review" in rendered
    assert "buy" not in rendered
    assert "sell" not in rendered


def test_overview_best_current_name_cards_handle_missing_inputs_gracefully():
    cards = dashboard.overview_best_current_name_cards(None, None)
    rendered = " ".join(str(value) for card in cards for value in card.values()).lower()

    assert cards[0]["kicker"] == "READY NAME STATUS"
    assert "no current ready names yet" in rendered
    assert cards[0]["command"] == "make onboarding"
    assert "make onboarding" in rendered
    assert "buy" not in rendered


def test_overview_best_current_name_cards_use_actionable_empty_state_when_no_names_are_ready():
    coverage = pd.DataFrame(
        [
            {"ticker": "TSLA", "usable_for_momentum": False, "dcf_ready": False, "peer_ready": False},
            {"ticker": "AMD", "usable_for_momentum": False, "dcf_ready": False, "peer_ready": False},
        ]
    )

    cards = dashboard.overview_best_current_name_cards(coverage, None)
    rendered = " ".join(str(value) for card in cards for value in card.values()).lower()

    assert len(cards) == 1
    assert cards[0]["kicker"] == "READY NAME STATUS"
    assert cards[0]["title"] == "No current ready names yet"
    assert cards[0]["command"] == "make onboarding"
    assert "refresh local coverage" in rendered
    assert "price-ready names" in rendered
    assert "buy" not in rendered
    assert "sell" not in rendered


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
    assert cards[0]["command"] == "make verify"
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
    assert cards[0]["command"] == "make monthly"
    assert cards[1]["title"] == "make monthly"
    assert cards[2]["title"] == "Monthly Picks"
    assert "monthly picks" in rendered
    assert "buy" not in rendered
    assert "sell" not in rendered


def test_overview_ready_name_handoff_cards_use_monthly_front_door_without_queue_guidance():
    coverage = pd.DataFrame(
        [
            {"ticker": "TSLA", "usable_for_momentum": True, "dcf_ready": False, "peer_ready": False},
            {"ticker": "AMD", "usable_for_momentum": False, "dcf_ready": False, "peer_ready": False},
        ]
    )

    cards = dashboard.overview_ready_name_handoff_cards(coverage, None, None, None)

    assert cards[0]["title"] == "TSLA"
    assert cards[0]["command"] == "make monthly"
    assert cards[1]["title"] == "make monthly"
    assert cards[2]["title"] == "Monthly Picks"


def test_overview_ready_name_handoff_cards_handle_missing_inputs_gracefully():
    cards = dashboard.overview_ready_name_handoff_cards(None, None, None, None)
    rendered = " ".join(str(value) for card in cards for value in card.values()).lower()

    assert len(cards) == 3
    assert cards[0]["kicker"] == "READY NAME"
    assert cards[0]["title"] == "No current ready names yet"
    assert cards[1]["title"] == "make onboarding"
    assert cards[2]["title"] == "Data Health"
    assert "no locally ready name yet" in cards[0]["body"].lower()
    assert "clear blockers before treating any name as ready" in cards[0]["body"].lower()
    assert "next read matches the current local workflow state" in cards[2]["body"].lower()
    assert "for no current ready names yet" not in cards[2]["body"].lower()
    assert "refresh local coverage and onboarding outputs" in rendered
    assert "buy" not in rendered
    assert "sell" not in rendered


def test_overview_ready_name_handoff_cards_use_runbook_fallback_when_no_ready_name_exists():
    coverage = pd.DataFrame(
        [
            {"ticker": "TSLA", "usable_for_momentum": False, "dcf_ready": False, "peer_ready": False},
            {"ticker": "AMD", "usable_for_momentum": False, "dcf_ready": False, "peer_ready": False},
        ]
    )
    payload = {
        "recommended_next_command_rows": [
            {
                "Step": "Open peer runbook",
                "Command": "make runbook-peers",
                "Reason": "",
            }
        ]
    }

    cards = dashboard.overview_ready_name_handoff_cards(coverage, None, payload, None)
    rendered = " ".join(str(value) for card in cards for value in card.values()).lower()

    assert cards[0]["title"] == "No current ready names yet"
    assert cards[1]["title"] == "make onboarding"
    assert cards[2]["title"] == "Data Health"
    assert "no locally ready name yet" in cards[0]["body"].lower()
    assert "clear blockers before treating any name as ready" in cards[0]["body"].lower()
    assert "refresh local coverage and onboarding outputs" in rendered
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
                "example_command": "make sec-stage TICKERS=NVDA",
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
                "recommended_action": "Normalize verified downloaded OHLCV rows, then run make price-validate, make price-preview, and make price-apply.",
                "example_command": "make price-worklist",
            }
        ]
    )

    cards = dashboard.overview_current_top_surfaces_cards(coverage, holdings, sec_queue, peer_queue, payload, queue)
    rendered = " ".join(str(value) for card in cards for value in card.values()).lower()

    assert len(cards) == 4
    assert cards[0]["title"] == "NVDA"
    assert cards[0]["command"] == "make verify"
    assert cards[1]["title"] == "NVDA"
    assert cards[1]["command"] == "make sec-stage TICKERS=NVDA"
    assert cards[2]["title"] == "make verify"
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
    assert cards[0]["command"] == "make onboarding"
    assert cards[1]["title"] == "No deep-research shortlist yet"
    assert cards[1]["command"] == "make onboarding"
    assert cards[2]["title"] == "make onboarding"
    assert cards[3]["title"] == "Data Health"
    assert "no locally ready name yet" in cards[0]["body"].lower()
    assert "no deep-research shortlist yet" in cards[1]["body"].lower()
    assert "refresh the sec stage and peer-mapping queues" in cards[1]["body"].lower()
    assert "highest-leverage blocker" in cards[0]["body"].lower()
    assert "next read matches the current local workflow state" in cards[3]["body"].lower()
    assert "for no current ready names yet" not in cards[3]["body"].lower()
    assert "buy" not in rendered
    assert "sell" not in rendered


def test_overview_current_top_surfaces_cards_use_monthly_front_door_for_monthly_tab():
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

    cards = dashboard.overview_current_top_surfaces_cards(coverage, None, None, None, None, queue)
    rendered = " ".join(str(value) for card in cards for value in card.values()).lower()

    assert cards[0]["title"] == "TSLA"
    assert cards[0]["command"] == "make monthly"
    assert cards[2]["title"] == "make monthly"
    assert cards[3]["title"] == "Monthly Picks"
    assert "make monthly" in rendered
    assert "buy" not in rendered
    assert "sell" not in rendered


def test_overview_current_top_surfaces_cards_use_monthly_front_door_without_queue_guidance():
    coverage = pd.DataFrame(
        [
            {"ticker": "TSLA", "usable_for_momentum": True, "dcf_ready": False, "peer_ready": False},
            {"ticker": "AMD", "usable_for_momentum": False, "dcf_ready": False, "peer_ready": False},
        ]
    )

    cards = dashboard.overview_current_top_surfaces_cards(coverage, None, None, None, None, None)

    assert cards[0]["title"] == "TSLA"
    assert cards[0]["command"] == "make monthly"
    assert cards[2]["title"] == "make monthly"
    assert cards[3]["title"] == "Monthly Picks"


def test_overview_current_top_surfaces_cards_prefer_staged_peer_handoff_reason():
    coverage = pd.DataFrame(
        [
            {"ticker": "NVDA", "usable_for_momentum": True, "dcf_ready": True, "peer_ready": False},
            {"ticker": "TSLA", "usable_for_momentum": True, "dcf_ready": False, "peer_ready": False},
        ]
    )
    holdings = pd.DataFrame([{"Ticker": "NVDA"}, {"Ticker": "TSLA"}])
    peer_queue = pd.DataFrame(
        [
            {
                "priority": 1,
                "ticker": "TSLA",
                "theme": "EV",
                "has_peer_mapping": True,
                "peer_ready": False,
                "recommended_action": "Run make imports-validate, then make imports-preview, then make imports-apply, then make status to confirm the live local peer inputs.",
                "focus_command": "make imports-validate",
                "example_command": "make imports-preview",
                "target_file": "data/imports/peers.csv",
            }
        ]
    )
    payload = {
        "recommended_next_command_rows": [
            {
                "Step": "Refresh local snapshot",
                "Command": "make status",
                "Reason": "Repo-native next step from the current read-only project status snapshot.",
            }
        ]
    }

    cards = dashboard.overview_current_top_surfaces_cards(coverage, holdings, None, peer_queue, payload, None)
    rendered = " ".join(str(value) for card in cards for value in card.values()).lower()

    assert cards[2]["title"] == "make verify"
    assert cards[1]["command"] == "make imports-validate"
    assert "make imports-preview" in rendered
    assert "make imports-apply" in rendered
    assert "make status-check top_n=5" in rendered


def test_overview_current_top_surfaces_cards_prefer_ready_name_reason_without_queue_guidance():
    coverage = pd.DataFrame(
        [
            {"ticker": "NVDA", "usable_for_momentum": True, "dcf_ready": True, "peer_ready": False},
            {"ticker": "AMD", "usable_for_momentum": True, "dcf_ready": False, "peer_ready": False},
        ]
    )
    holdings = pd.DataFrame([{"Ticker": "NVDA"}, {"Ticker": "AMD"}])
    sec_queue = pd.DataFrame(
        [
            {
                "priority": 1,
                "ticker": "AMD",
                "theme": "Semiconductors",
                "recommended_action": "Run make imports-validate, then make imports-preview, then make imports-apply, then make status to confirm the live staged fundamentals.",
                "focus_command": "make imports-validate",
                "example_command": "make imports-preview",
                "target_file": "data/imports/fundamentals.csv",
            }
        ]
    )
    payload = {
        "recommended_next_command_rows": [
            {
                "Step": "Refresh local snapshot",
                "Command": "make status",
                "Reason": "Repo-native next step from the current read-only project status snapshot.",
            }
        ]
    }

    cards = dashboard.overview_current_top_surfaces_cards(coverage, holdings, sec_queue, None, payload, None)
    rendered = " ".join(str(value) for card in cards for value in card.values()).lower()

    assert cards[2]["title"] == "make verify"
    assert cards[0]["command"] == "make verify"
    assert "run deterministic verification first" in cards[2]["body"].lower()
    assert "stock report beta" in cards[2]["body"].lower()
    assert "make imports-apply" in rendered
    assert "buy" not in rendered
    assert "sell" not in rendered


def test_overview_current_top_surfaces_cards_keep_staged_fundamentals_context_in_blocked_and_tab_cards():
    coverage = pd.DataFrame(
        [
            {"ticker": "NVDA", "usable_for_momentum": True, "dcf_ready": True, "peer_ready": False},
            {"ticker": "AMD", "usable_for_momentum": True, "dcf_ready": False, "peer_ready": False},
        ]
    )
    holdings = pd.DataFrame([{"Ticker": "NVDA"}, {"Ticker": "AMD"}])
    sec_queue = pd.DataFrame(
        [
            {
                "priority": 1,
                "ticker": "AMD",
                "theme": "Semiconductors",
                "recommended_action": "Run make imports-validate, then make imports-preview, then make imports-apply, then make status to confirm the live staged fundamentals.",
                "focus_command": "make imports-validate",
                "example_command": "make imports-preview",
                "target_file": "data/imports/fundamentals.csv",
            }
        ]
    )
    payload = {
        "recommended_next_command_rows": [
            {
                "Step": "Refresh local snapshot",
                "Command": "make status",
                "Reason": "Repo-native next step from the current read-only project status snapshot.",
            }
        ]
    }

    cards = dashboard.overview_current_top_surfaces_cards(coverage, holdings, sec_queue, None, payload, None)
    rendered = " ".join(str(value) for card in cards for value in card.values()).lower()

    assert cards[1]["title"] == "AMD"
    assert cards[1]["command"] == "make imports-validate"
    assert "advance staged fundamentals import" in cards[1]["body"].lower()
    assert "make imports-apply" in cards[1]["body"].lower()
    assert "make status-check top_n=5" in rendered
    assert cards[3]["title"] == "Stock Report Beta"
    assert "open stock report beta after the command step" in cards[3]["body"].lower()
    assert "nvda" in cards[3]["body"].lower()
    assert "live staged" in rendered
    assert "buy" not in rendered
    assert "sell" not in rendered


def test_overview_current_top_surfaces_cards_use_runbook_fallback_when_no_ready_name_exists():
    coverage = pd.DataFrame(
        [
            {"ticker": "TSLA", "usable_for_momentum": False, "dcf_ready": False, "peer_ready": False},
            {"ticker": "AMD", "usable_for_momentum": False, "dcf_ready": False, "peer_ready": False},
        ]
    )
    payload = {
        "recommended_next_command_rows": [
            {
                "Step": "Open peer runbook",
                "Command": "make runbook-peers",
                "Reason": "",
            }
        ]
    }

    cards = dashboard.overview_current_top_surfaces_cards(coverage, None, None, None, payload, None)
    rendered = " ".join(str(value) for card in cards for value in card.values()).lower()

    assert cards[0]["title"] == "No current ready names yet"
    assert cards[0]["command"] == "make onboarding"
    assert cards[1]["command"] == "make runbook-peers"
    assert cards[2]["title"] == "make runbook-peers"
    assert cards[3]["title"] == "Data Health"
    assert "ordered lane runbook" in rendered
    assert "staged local workflow" in rendered
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
    assert cards[0]["command"] == "make pipeline"
    assert cards[1]["command"] == "make pipeline"
    assert "strong rotation" in rendered
    assert "ai semiconductors" in rendered
    assert "vs spy 9.0%" in rendered
    assert "buy" not in rendered
    assert "sell" not in rendered


def test_overview_market_context_cards_handle_missing_inputs_gracefully():
    cards = dashboard.overview_market_context_cards(None)
    rendered = " ".join(str(value) for card in cards for value in card.values()).lower()

    assert "no local market direction context yet" in rendered
    assert cards[0]["command"] == "make pipeline"
    assert "make pipeline" in rendered
    assert "buy" not in rendered


def test_overview_market_context_cards_keep_pipeline_visible_when_theme_rows_are_unusable():
    market_direction = pd.DataFrame(
        [
            {
                "Theme": "AI Semiconductors",
                "ETF": "SMH",
                "ThemeStatus": "Strong Rotation",
                "Return1M": None,
                "RelativeReturnVsSPY": None,
                "RelativeReturnVsQQQ": None,
            }
        ]
    )

    cards = dashboard.overview_market_context_cards(market_direction)
    rendered = " ".join(str(value) for card in cards for value in card.values()).lower()

    assert cards[0]["title"] == "Insufficient local theme performance"
    assert cards[0]["command"] == "make pipeline"
    assert "make pipeline" in rendered


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
    assert cards[0]["command"] == "make runbook-prices-broader"
    assert cards[1]["command"] == "make pipeline"
    assert "missing local prices" in rendered
    assert "9/12" in rendered
    assert "ai semiconductors" in rendered
    assert "9.0%" in rendered
    assert "buy" not in rendered
    assert "sell" not in rendered


def test_overview_benchmark_pressure_cards_keep_price_status_visible_when_prices_are_present():
    market_direction = pd.DataFrame(
        [
            {
                "Theme": "AI Semiconductors",
                "RelativeReturnVsSPY": 0.09,
            }
        ]
    )
    price_status = pd.DataFrame({"status": ["fetched", "fetched"]})
    payload = {"summary": {"tickers_total": 12, "tickers_with_prices": 12}}

    cards = dashboard.overview_benchmark_pressure_cards(market_direction, price_status, payload)
    rendered = " ".join(str(value) for card in cards for value in card.values()).lower()

    assert cards[0]["title"] == "Local prices present"
    assert cards[0]["command"] == "make price-status TOP_N=10"
    assert cards[1]["command"] == "make pipeline"
    assert "make price-status top_n=10" in rendered
    assert "buy" not in rendered
    assert "sell" not in rendered


def test_overview_benchmark_pressure_cards_handle_missing_inputs_gracefully():
    cards = dashboard.overview_benchmark_pressure_cards(None, None, None)
    rendered = " ".join(str(value) for card in cards for value in card.values()).lower()

    assert "local prices present" in rendered or "ticker coverage is not available yet" in rendered
    assert cards[0]["command"] == "make runbook-prices-broader"
    assert cards[1]["command"] == "make pipeline"
    assert "make runbook-prices-broader" in rendered
    assert "make pipeline" in rendered
    assert "buy" not in rendered


def test_onboarding_notice_copy_uses_onboarding_front_door_for_generated_artifacts():
    bundle_body, bundle_command = dashboard.onboarding_notice_copy("command_bundles")
    price_body, price_command = dashboard.onboarding_notice_copy("price_worklist")
    unlock_body, unlock_command = dashboard.onboarding_notice_copy("unlock_priority_summary")

    assert bundle_command == "make onboarding"
    assert "generate holdings-first local command bundles" in bundle_body.lower()
    assert price_command == "make onboarding"
    assert "safe manual-import path" in price_body.lower()
    assert unlock_command == "make onboarding"
    assert "grouped unlock priorities by holdings, theme, and sector etf" in unlock_body.lower()


def test_artifact_notice_copy_uses_narrow_front_doors_for_specific_artifacts():
    action_body, action_command = dashboard.artifact_notice_copy("action_queue")
    health_body, health_command = dashboard.artifact_notice_copy("research_health")
    sources_body, sources_command = dashboard.artifact_notice_copy("data_source_status")

    assert action_command == "make action-queue"
    assert "research action queue" in action_body.lower()
    assert health_command == "make research-health"
    assert "research health outputs are not available yet" in health_body.lower()
    assert sources_command == "make data-sources"
    assert "local source registry" in sources_body.lower()


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
    assert cards[0]["title"] == "make status-check TOP_N=5"
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


def test_overview_next_command_cards_use_command_family_fallback_when_reason_is_missing():
    payload = {
        "recommended_next_command_rows": [
            {
                "Step": "Fix top peers blocker (TSLA)",
                "Command": "make focus-peers TICKER=TSLA",
                "Reason": "",
            }
        ]
    }

    cards = dashboard.overview_next_command_cards(payload, None, limit=1)

    assert cards[0]["title"] == "make focus-peers TICKER=TSLA"
    assert "single-name shortcut" in cards[0]["body"].lower()
    assert "not available" not in cards[0]["body"].lower()


def test_overview_next_command_cards_use_bundle_and_import_fallbacks_when_reasons_are_missing():
    payload = {
        "recommended_next_command_rows": [
            {
                "Step": "Advance staged fundamentals import",
                "Command": "make imports-validate",
                "Reason": "",
            },
            {
                "Step": "Run highest-leverage price bundle",
                "Command": "make bundle-prices",
                "Reason": "",
            },
        ]
    }

    cards = dashboard.overview_next_command_cards(payload, None, limit=2)

    assert cards[0]["title"] == "make imports-validate"
    assert "staged flow" in [badge.lower() for badge in cards[0]["badges"]]
    assert "make imports-preview" in cards[0]["body"].lower()
    assert "make imports-apply" in cards[0]["body"].lower()
    assert cards[1]["title"] == "make bundle-prices"
    assert "bundle first" in [badge.lower() for badge in cards[1]["badges"]]
    assert "highest-leverage local bundle first" in cards[1]["body"].lower()
    assert "not available" not in cards[1]["body"].lower()


def test_overview_next_command_cards_keep_staged_follow_through_visible_when_reasons_are_generic():
    payload = {
        "recommended_next_command_rows": [
            {
                "Step": "Advance staged fundamentals import",
                "Command": "make imports-validate",
                "Reason": "Use staged local imports if the free refresh fails.",
            },
            {
                "Step": "Advance staged price import",
                "Command": "make price-validate",
                "Reason": "Use staged local imports if the free refresh fails.",
            },
        ]
    }

    cards = dashboard.overview_next_command_cards(payload, None, limit=2)

    assert cards[0]["title"] == "make imports-validate"
    assert "make imports-preview" in cards[0]["body"].lower()
    assert "make imports-apply" in cards[0]["body"].lower()
    assert cards[1]["title"] == "make price-validate"
    assert "make price-preview" in cards[1]["body"].lower()
    assert "make price-apply" in cards[1]["body"].lower()
    assert "use staged local imports if the free refresh fails" not in " ".join(card["body"] for card in cards).lower()


def test_overview_next_command_cards_use_runbook_fallback_when_reason_is_missing():
    payload = {
        "recommended_next_command_rows": [
            {
                "Step": "Run broader peer workflow",
                "Command": "make runbook-peers-broader",
                "Reason": "",
            }
        ]
    }

    cards = dashboard.overview_next_command_cards(payload, None, limit=1)

    assert cards[0]["title"] == "make runbook-peers-broader"
    assert "runbook" in [badge.lower() for badge in cards[0]["badges"]]
    assert "use the ordered lane runbook" in cards[0]["body"].lower()
    assert "not available" not in cards[0]["body"].lower()


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
                "recommended_action": "Normalize verified downloaded OHLCV rows, then run make price-validate, make price-preview, and make price-apply.",
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


def test_overview_next_command_cards_use_onboarding_front_door_without_guidance():
    cards = dashboard.overview_next_command_cards(None, None, limit=1)
    rendered = " ".join(str(value) for card in cards for value in card.values()).lower()

    assert cards[0]["title"] == "make onboarding"
    assert cards[0]["command"] == "make onboarding"
    assert "refresh local coverage, onboarding outputs, and operator guidance" in rendered
    assert "buy" not in rendered
    assert "sell" not in rendered


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


def test_overview_workflow_path_cards_use_runbook_fallback_when_action_queue_drives_step_one():
    queue = pd.DataFrame(
        [
            {
                "priority": 1,
                "urgency": "critical",
                "action_type": "peers",
                "ticker": "TSLA",
                "title": "Open peer runbook",
                "reason": "",
                "recommended_action": "",
                "focus_command": "make runbook-peers",
                "example_command": "",
            }
        ]
    )

    cards = dashboard.overview_workflow_path_cards(None, queue)

    assert cards[0]["title"] == "make runbook-peers"
    assert "staged flow" in [badge.lower() for badge in cards[0]["badges"]]
    assert "ordered lane runbook" in cards[0]["body"].lower()
    assert "not available" not in cards[0]["body"].lower()


def test_overview_workflow_path_cards_use_imports_and_bundle_fallbacks_when_action_queue_drives_step_one():
    imports_queue = pd.DataFrame(
        [
            {
                "priority": 1,
                "urgency": "critical",
                "action_type": "fundamentals",
                "ticker": "NVDA",
                "title": "Advance staged fundamentals",
                "reason": "",
                "recommended_action": "",
                "focus_command": "make imports-validate",
                "example_command": "",
            }
        ]
    )
    bundle_queue = pd.DataFrame(
        [
            {
                "priority": 1,
                "urgency": "critical",
                "action_type": "peers",
                "ticker": "",
                "title": "Run peer bundle",
                "reason": "",
                "recommended_action": "",
                "focus_command": "make bundle-peers",
                "example_command": "",
            }
        ]
    )

    imports_cards = dashboard.overview_workflow_path_cards(None, imports_queue)
    bundle_cards = dashboard.overview_workflow_path_cards(None, bundle_queue)

    assert imports_cards[0]["title"] == "make imports-validate"
    assert "staged flow" in [badge.lower() for badge in imports_cards[0]["badges"]]
    assert "use the staged local workflow next" in imports_cards[0]["body"].lower()
    assert bundle_cards[0]["title"] == "make bundle-peers"
    assert "bundle first" in [badge.lower() for badge in bundle_cards[0]["badges"]]
    assert "highest-leverage local bundle first" in bundle_cards[0]["body"].lower()
    assert "not available" not in " ".join(str(value) for card in imports_cards + bundle_cards for value in card.values()).lower()


def test_overview_workflow_path_cards_surface_top_staged_follow_through_when_queue_row_has_target_file():
    fundamentals_queue = pd.DataFrame(
        [
            {
                "priority": 1,
                "urgency": "critical",
                "action_type": "fundamentals",
                "ticker": "NVDA",
                "title": "Advance staged fundamentals",
                "reason": "",
                "recommended_action": "Use staged local imports if the free refresh fails.",
                "focus_command": "make imports-validate",
                "example_command": "",
                "target_file": "data/imports/fundamentals.csv",
            }
        ]
    )
    prices_queue = pd.DataFrame(
        [
            {
                "priority": 1,
                "urgency": "critical",
                "action_type": "prices",
                "ticker": "AMD",
                "title": "Advance staged prices",
                "reason": "",
                "recommended_action": "Use staged local imports if the free refresh fails.",
                "focus_command": "make price-validate",
                "example_command": "",
                "target_file": "data/imports/prices.csv",
            }
        ]
    )

    fundamentals_cards = dashboard.overview_workflow_path_cards(None, fundamentals_queue)
    prices_cards = dashboard.overview_workflow_path_cards(None, prices_queue)

    assert fundamentals_cards[0]["title"] == "make imports-validate"
    assert "make imports-preview" in fundamentals_cards[0]["body"].lower()
    assert "make imports-apply" in fundamentals_cards[0]["body"].lower()
    assert prices_cards[0]["title"] == "make price-validate"
    assert "make price-preview" in prices_cards[0]["body"].lower()
    assert "make price-apply" in prices_cards[0]["body"].lower()
    assert "use staged local imports if the free refresh fails" not in " ".join(
        str(value) for card in fundamentals_cards + prices_cards for value in card.values()
    ).lower()


def test_overview_workflow_path_cards_use_structured_project_status_steps():
    payload = {
        "recommended_next_command_rows": [
            {
                "Step": "Fix top prices blocker (META)",
                "Command": "make focus-price TICKER=META",
                "Reason": "Provider rows could not be parsed cleanly, so price coverage is still the top blocker.",
            },
            {
                "Step": "Advance staged fundamentals import",
                "Command": "make imports-validate",
                "Reason": "Staged fundamentals already exist in data/imports/fundamentals.csv and should be validated before preview/apply.",
            },
            {
                "Step": "Deterministic verification",
                "Command": "make verify",
                "Reason": "Confirm local outputs still pass after the staged fundamentals follow-through.",
            },
        ]
    }
    queue = pd.DataFrame(
        [
            {
                "priority": 1,
                "urgency": "critical",
                "action_type": "prices",
                "ticker": "META",
                "title": "Repair prices",
                "reason": "Need more local rows.",
                "example_command": "make price-worklist",
            }
        ]
    )

    cards = dashboard.overview_workflow_path_cards(payload, queue)
    rendered = " ".join(str(value) for card in cards for value in card.values()).lower()

    assert len(cards) == 3
    assert cards[0]["title"] == "make focus-price TICKER=META"
    assert cards[1]["title"] == "make imports-validate"
    assert cards[2]["title"] == "make verify"
    assert "make imports-preview" in rendered
    assert "make imports-apply" in rendered
    assert "buy" not in rendered
    assert "sell" not in rendered


def test_overview_workflow_path_cards_use_command_family_fallback_when_reason_is_missing():
    payload = {
        "recommended_next_command_rows": [
            {
                "Step": "Advance staged peers import",
                "Command": "make imports-validate",
                "Reason": "",
            }
        ]
    }

    cards = dashboard.overview_workflow_path_cards(payload, None)

    assert cards[0]["title"] == "make imports-validate"
    assert "staged flow" in [badge.lower() for badge in cards[0]["badges"]]
    assert "make imports-preview" in cards[0]["body"].lower()
    assert "make imports-apply" in cards[0]["body"].lower()
    assert "not available" not in cards[0]["body"].lower()


def test_overview_workflow_path_cards_keep_structured_staged_follow_through_visible_when_reason_is_generic():
    payload = {
        "recommended_next_command_rows": [
            {
                "Step": "Advance staged fundamentals import",
                "Command": "make imports-validate",
                "Reason": "Use staged local imports if the free refresh fails.",
            },
            {
                "Step": "Advance staged price import",
                "Command": "make price-validate",
                "Reason": "Use staged local imports if the free refresh fails.",
            },
        ]
    }

    cards = dashboard.overview_workflow_path_cards(payload, None)

    assert cards[0]["title"] == "make imports-validate"
    assert "make imports-preview" in cards[0]["body"].lower()
    assert "make imports-apply" in cards[0]["body"].lower()
    assert cards[1]["title"] == "make price-validate"
    assert "make price-preview" in cards[1]["body"].lower()
    assert "make price-apply" in cards[1]["body"].lower()
    assert "use staged local imports if the free refresh fails" not in " ".join(
        card["body"] for card in cards[:2]
    ).lower()


def test_overview_workflow_path_cards_use_bundle_fallback_when_reason_is_missing():
    payload = {
        "recommended_next_command_rows": [
            {
                "Step": "Run highest-leverage price bundle",
                "Command": "make bundle-prices",
                "Reason": "",
            }
        ]
    }

    cards = dashboard.overview_workflow_path_cards(payload, None)

    assert cards[0]["title"] == "make bundle-prices"
    assert "bundle first" in [badge.lower() for badge in cards[0]["badges"]]
    assert "highest-leverage local bundle first" in cards[0]["body"].lower()
    assert "not available" not in cards[0]["body"].lower()


def test_overview_workflow_path_cards_use_runbook_fallback_when_reason_is_missing():
    payload = {
        "recommended_next_command_rows": [
            {
                "Step": "Open peer runbook",
                "Command": "make runbook-peers",
                "Reason": "",
            }
        ]
    }

    cards = dashboard.overview_workflow_path_cards(payload, None)

    assert cards[0]["title"] == "make runbook-peers"
    assert "staged flow" in [badge.lower() for badge in cards[0]["badges"]]
    assert "ordered lane runbook" in cards[0]["body"].lower()
    assert "not available" not in cards[0]["body"].lower()


def test_overview_workflow_path_cards_use_status_check_when_structured_command_is_missing():
    payload = {
        "recommended_next_command_rows": [
            {
                "Step": "Read-only status snapshot",
                "Command": "",
                "Reason": "Rebuild the local status snapshot before choosing a deeper workflow path.",
            }
        ]
    }

    cards = dashboard.overview_workflow_path_cards(payload, None)

    assert cards[0]["title"] == "make status-check TOP_N=5"
    assert cards[0]["command"] == "make status-check TOP_N=5"
    assert "local status snapshot" in cards[0]["body"].lower()


def test_overview_workflow_path_cards_fall_back_to_safe_defaults():
    cards = dashboard.overview_workflow_path_cards(None, None)
    rendered = " ".join(str(value) for card in cards for value in card.values()).lower()

    assert cards[0]["title"] == "make status-check TOP_N=5"
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
                "recommended_action": "Normalize verified downloaded OHLCV rows, then run make price-validate, make price-preview, and make price-apply.",
                "example_command": "make price-worklist",
            }
        ]
    )

    card = dashboard.overview_workflow_reason_card(None, queue)
    rendered = " ".join(str(value) for value in card.values()).lower()

    assert card["title"] == "make price-worklist"
    assert "nvda" in rendered
    assert "normalize verified downloaded ohlcv rows" in rendered
    assert "make price-validate" in rendered
    assert "make price-preview" in rendered
    assert "make price-apply" in rendered
    assert "buy" not in rendered
    assert "sell" not in rendered


def test_overview_workflow_reason_card_uses_review_fallback_when_queue_copy_is_missing():
    queue = pd.DataFrame(
        [
            {
                "priority": 1,
                "urgency": "critical",
                "action_type": "peers",
                "ticker": "TSLA",
                "title": "Research peers",
                "reason": "",
                "recommended_action": "",
                "example_command": "",
            }
        ]
    )

    card = dashboard.overview_workflow_reason_card(None, queue)
    rendered = " ".join(str(value) for value in card.values()).lower()

    assert card["title"] == "make focus-peers TICKER=TSLA"
    assert "tsla" in rendered
    assert "review peer path." in rendered
    assert "not available" not in rendered


def test_overview_workflow_reason_card_uses_imports_and_bundle_fallbacks_when_queue_copy_is_missing():
    imports_queue = pd.DataFrame(
        [
            {
                "priority": 1,
                "urgency": "critical",
                "action_type": "fundamentals",
                "ticker": "NVDA",
                "title": "Advance staged fundamentals",
                "reason": "",
                "recommended_action": "",
                "focus_command": "make imports-validate",
                "example_command": "",
            }
        ]
    )
    bundle_queue = pd.DataFrame(
        [
            {
                "priority": 1,
                "urgency": "critical",
                "action_type": "peers",
                "ticker": "",
                "title": "Run peer bundle",
                "reason": "",
                "recommended_action": "",
                "focus_command": "make bundle-peers",
                "example_command": "",
            }
        ]
    )

    imports_card = dashboard.overview_workflow_reason_card(None, imports_queue)
    bundle_card = dashboard.overview_workflow_reason_card(None, bundle_queue)

    assert imports_card["title"] == "make imports-validate"
    assert "nvda" in " ".join(str(value) for value in imports_card.values()).lower()
    assert "staged local workflow next" in " ".join(str(value) for value in imports_card.values()).lower()
    assert bundle_card["title"] == "make bundle-peers"
    assert "highest-leverage local bundle first" in " ".join(str(value) for value in bundle_card.values()).lower()
    assert "not available" not in " ".join(str(value) for value in imports_card.values()).lower()
    assert "not available" not in " ".join(str(value) for value in bundle_card.values()).lower()


def test_overview_workflow_reason_card_uses_runbook_fallback_when_queue_copy_is_missing():
    queue = pd.DataFrame(
        [
            {
                "priority": 1,
                "urgency": "critical",
                "action_type": "peers",
                "ticker": "TSLA",
                "title": "Open peer runbook",
                "reason": "",
                "recommended_action": "",
                "focus_command": "make runbook-peers",
                "example_command": "",
            }
        ]
    )

    card = dashboard.overview_workflow_reason_card(None, queue)
    rendered = " ".join(str(value) for value in card.values()).lower()

    assert card["title"] == "make runbook-peers"
    assert "tsla" in rendered
    assert "staged local workflow next" in rendered
    assert "not available" not in rendered


def test_overview_workflow_reason_card_falls_back_to_status_snapshot():
    payload = {"summary": {"data_gaps": 12, "critical_actions": 4}}

    card = dashboard.overview_workflow_reason_card(payload, None)
    rendered = " ".join(str(value) for value in card.values()).lower()

    assert card["title"] == "make status-check TOP_N=5"
    assert "4 critical actions" in rendered
    assert "12 visible data gaps" in rendered
    assert "buy" not in rendered


def test_overview_workflow_reason_card_uses_actionable_empty_state_copy():
    card = dashboard.overview_workflow_reason_card(None, None)
    rendered = " ".join(str(value) for value in card.values()).lower()

    assert card["title"] == "make status-check TOP_N=5"
    assert "run make status-check top_n=5 first" in rendered
    assert "local blocker triage" in rendered
    assert "verification and ui review" in rendered
    assert "buy" not in rendered
    assert "sell" not in rendered


def test_overview_workflow_reason_card_uses_bundle_fallback_when_structured_summary_is_thin():
    payload = {
        "summary": {"data_gaps": 0, "critical_actions": 0},
        "recommended_next_command_rows": [
            {
                "Step": "Run highest-leverage price bundle",
                "Command": "make bundle-prices",
                "Reason": "",
            }
        ],
    }

    card = dashboard.overview_workflow_reason_card(payload, None)
    rendered = " ".join(str(value) for value in card.values()).lower()

    assert card["title"] == "make bundle-prices"
    assert "bundle first" in [badge.lower() for badge in card["badges"]]
    assert "highest-leverage local bundle first" in rendered
    assert "not available" not in rendered


def test_overview_workflow_reason_card_uses_runbook_fallback_when_structured_summary_is_thin():
    payload = {
        "summary": {"data_gaps": 0, "critical_actions": 0},
        "recommended_next_command_rows": [
            {
                "Step": "Open peer runbook",
                "Command": "make runbook-peers",
                "Reason": "",
            }
        ],
    }

    card = dashboard.overview_workflow_reason_card(payload, None)
    rendered = " ".join(str(value) for value in card.values()).lower()

    assert card["title"] == "make runbook-peers"
    assert "staged local workflow" in rendered
    assert "not available" not in rendered


def test_overview_handoff_cards_link_to_deeper_tabs_without_trade_language():
    cards = dashboard.overview_handoff_cards()
    rendered = " ".join(str(value) for card in cards for value in card.values()).lower()

    assert len(cards) == 3
    assert cards[0]["title"] == "Data Health"
    assert cards[0]["command"] == "make onboarding"
    assert cards[1]["title"] == "Stock Report Beta"
    assert cards[1]["command"] == "make verify"
    assert cards[2]["title"] == "Monthly Picks"
    assert cards[2]["command"] == "make monthly"
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
                "recommended_action": "Normalize verified downloaded OHLCV rows, then run make price-validate, make price-preview, and make price-apply.",
                "example_command": "make price-worklist",
            }
        ]
    )

    cards = dashboard.overview_best_local_research_path_cards(coverage, holdings, payload, queue)
    rendered = " ".join(str(value) for card in cards for value in card.values()).lower()

    assert len(cards) == 3
    assert cards[0]["title"] == "NVDA"
    assert cards[1]["title"] == "make verify"
    assert cards[2]["title"] == "Stock Report Beta"
    assert "best current name" in rendered
    assert "next command" in rendered
    assert "next tab" in rendered
    assert "deterministic verification" in rendered or "verification first" in rendered
    assert "buy" not in rendered
    assert "sell" not in rendered


def test_overview_best_local_research_path_cards_use_monthly_front_door_for_monthly_tab():
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

    cards = dashboard.overview_best_local_research_path_cards(coverage, None, None, queue)
    rendered = " ".join(str(value) for card in cards for value in card.values()).lower()

    assert cards[0]["title"] == "TSLA"
    assert cards[1]["title"] == "make monthly"
    assert cards[2]["title"] == "Monthly Picks"
    assert "make monthly" in rendered
    assert "buy" not in rendered
    assert "sell" not in rendered


def test_overview_best_local_research_path_cards_use_monthly_front_door_without_queue_guidance():
    coverage = pd.DataFrame(
        [
            {"ticker": "TSLA", "usable_for_momentum": True, "dcf_ready": False, "peer_ready": False},
            {"ticker": "AMD", "usable_for_momentum": False, "dcf_ready": False, "peer_ready": False},
        ]
    )

    cards = dashboard.overview_best_local_research_path_cards(coverage, None, None, None)

    assert cards[0]["title"] == "TSLA"
    assert cards[1]["title"] == "make monthly"
    assert cards[2]["title"] == "Monthly Picks"


def test_overview_best_local_research_path_cards_fall_back_gracefully():
    cards = dashboard.overview_best_local_research_path_cards(None, None, None, None)
    rendered = " ".join(str(value) for card in cards for value in card.values()).lower()

    assert len(cards) == 3
    assert cards[0]["title"] == "No current ready names yet"
    assert cards[0]["command"] == "make onboarding"
    assert cards[1]["title"] == "make onboarding"
    assert cards[2]["title"] == "Data Health"
    assert "no locally ready name yet" in cards[0]["body"].lower()
    assert "clear the highest-leverage blocker" in cards[0]["body"].lower()
    assert "no current ready names yet" in rendered
    assert "buy" not in rendered
    assert "sell" not in rendered


def test_overview_best_local_research_path_cards_use_runbook_fallback_when_no_ready_name_exists():
    coverage = pd.DataFrame(
        [
            {"ticker": "TSLA", "usable_for_momentum": False, "dcf_ready": False, "peer_ready": False},
            {"ticker": "AMD", "usable_for_momentum": False, "dcf_ready": False, "peer_ready": False},
        ]
    )
    payload = {
        "recommended_next_command_rows": [
            {
                "Step": "Open peer runbook",
                "Command": "make runbook-peers",
                "Reason": "",
            }
        ]
    }

    cards = dashboard.overview_best_local_research_path_cards(coverage, None, payload, None)
    rendered = " ".join(str(value) for card in cards for value in card.values()).lower()

    assert cards[0]["title"] == "No current ready names yet"
    assert cards[0]["command"] == "make runbook-peers"
    assert cards[1]["title"] == "make runbook-peers"
    assert cards[2]["title"] == "Data Health"
    assert "ordered lane runbook" in rendered
    assert "staged local workflow" in rendered
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
    assert card["command"] == "make status-check TOP_N=5"
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
    assert card["command"] == "make onboarding"
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
    assert card["command"] == "make dashboard-smoke"
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
    assert cards[0]["command"] == "make runbook-prices-broader"
    assert any(card["title"] == "Fundamentals" for card in cards)
    assert any(card.get("command") == "make runbook-fundamentals-broader" for card in cards)
    assert any(card["title"] == "Peers" for card in cards)
    assert any(card.get("command") == "make runbook-peers-broader" for card in cards)
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
    assert cards[0]["command"] == "make action-queue"
    assert "make action-queue" in rendered
    assert "prices, fundamentals, peers, or optional context" in rendered


def test_overview_coverage_hotspot_cards_use_onboarding_for_optional_context():
    queue = pd.DataFrame(
        [
            {"priority": 1, "action_type": "earnings", "ticker": "AVGO"},
            {"priority": 2, "action_type": "analyst_estimates", "ticker": "AMD"},
        ]
    )

    cards = dashboard.overview_coverage_hotspot_cards(queue)

    assert cards[0]["title"] == "Earnings"
    assert cards[0]["command"] == "make onboarding"
    assert cards[1]["title"] == "Analyst Estimates"
    assert cards[1]["command"] == "make onboarding"


def test_overview_coverage_hotspot_cards_use_action_queue_check_for_unknown_action_type():
    queue = pd.DataFrame(
        [
            {"priority": 1, "action_type": "source_registry", "ticker": ""},
        ]
    )

    cards = dashboard.overview_coverage_hotspot_cards(queue)
    rendered = " ".join(str(value) for card in cards for value in card.values()).lower()

    assert cards[0]["title"] == "Source Registry"
    assert cards[0]["command"] == "make action-queue-check TOP_N=10"
    assert "visible local workflow pressure" in rendered


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
    assert cards[0]["title"] == "Refresh monthly context"
    assert cards[0]["command"] == "make monthly"
    assert "make monthly" in cards[0]["body"]

    picks = pd.DataFrame([{"Month": "2026-05", "MissingDataFields": "Return3M"}] * 4)
    cards = dashboard.monthly_picks_next_step_cards(picks, None, None, 5, queue)
    assert cards[0]["title"] == "Improve candidate coverage"
    assert "make price-worklist" in cards[0]["body"]

    full_picks = pd.DataFrame([{"Month": "2026-05", "MissingDataFields": ""}] * 5)
    cards = dashboard.monthly_picks_next_step_cards(full_picks, None, None, 5, queue)
    assert cards[0]["title"] == "Improve track-record coverage"
    assert cards[0]["command"] == "make price-worklist"

    track = pd.DataFrame([{"Month": "2026-04"}])
    equity = pd.DataFrame([{"Month": "2026-04", "PicksEquity": 1.0, "BenchmarkEquity": 1.0}])
    cards = dashboard.monthly_picks_next_step_cards(full_picks, track, equity, 5, queue)
    assert cards[0]["title"] == "Review current candidates"
    assert cards[0]["command"] == "make dashboard-smoke"
    assert "dashboard-smoke" in cards[0]["body"]


def test_monthly_picks_track_record_gap_points_to_blocker_command():
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
    full_picks = pd.DataFrame([{"Month": "2026-05", "MissingDataFields": ""}] * 5)

    cards = dashboard.monthly_picks_next_step_cards(full_picks, None, None, 5, queue)
    rendered = " ".join(str(value) for card in cards for value in card.values()).lower()

    assert "improve track-record coverage" in rendered
    assert "make price-worklist" in rendered


def test_monthly_picks_track_record_gap_uses_track_record_front_door_without_blocker_queue():
    full_picks = pd.DataFrame([{"Month": "2026-05", "MissingDataFields": ""}] * 5)

    cards = dashboard.monthly_picks_next_step_cards(full_picks, None, None, 5, None)
    rendered = " ".join(str(value) for card in cards for value in card.values()).lower()

    assert cards[0]["title"] == "Improve track-record coverage"
    assert cards[0]["command"] == "make track-record"
    assert "make track-record" in rendered
    assert "buy" not in rendered
    assert "sell" not in rendered


def test_monthly_picks_coverage_gap_uses_data_wizard_without_blocker_queue():
    picks = pd.DataFrame([{"Month": "2026-05", "MissingDataFields": "Return3M"}] * 4)

    cards = dashboard.monthly_picks_next_step_cards(picks, None, None, 5, None)
    rendered = " ".join(str(value) for card in cards for value in card.values()).lower()

    assert cards[0]["title"] == "Improve candidate coverage"
    assert cards[0]["command"] == "make data-wizard TOP_N=10"
    assert "make data-wizard top_n=10" in rendered
    assert "buy" not in rendered
    assert "sell" not in rendered


def test_monthly_picks_coverage_gap_uses_data_wizard_with_empty_queue():
    picks = pd.DataFrame([{"Month": "2026-05", "MissingDataFields": "Return3M"}] * 4)

    cards = dashboard.monthly_picks_next_step_cards(picks, None, None, 5, pd.DataFrame())

    assert cards[0]["title"] == "Improve candidate coverage"
    assert cards[0]["command"] == "make data-wizard TOP_N=10"


def test_monthly_picks_track_record_gap_uses_track_record_front_door_with_empty_queue():
    full_picks = pd.DataFrame([{"Month": "2026-05", "MissingDataFields": ""}] * 5)

    cards = dashboard.monthly_picks_next_step_cards(full_picks, None, None, 5, pd.DataFrame())

    assert cards[0]["title"] == "Improve track-record coverage"
    assert cards[0]["command"] == "make track-record"


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
    assert "peer fundamentals or peer price/market-cap context" in html
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


def test_stock_report_local_context_cards_show_staged_peer_import_state():
    coverage = pd.DataFrame(
        [
            {
                "dataset": "peers",
                "ticker_present": True,
                "validation_status": "valid",
                "focus_command": "make imports-validate",
                "example_command": "make imports-preview",
                "target_file": "data/imports/peers.csv",
            }
        ]
    )
    peer_summary = {
        "peer_dataset_present": False,
        "peer_count": 2,
        "peer_fundamentals_available": 0,
        "peer_market_context_available": 0,
    }

    cards = dashboard.stock_report_local_context_cards(coverage, peer_summary)
    rendered = " ".join(str(value) for card in cards for value in card.values()).lower()

    assert "staged" in rendered
    assert "make imports-validate" in rendered
    assert "make imports-preview" in rendered
    assert "make imports-apply" in rendered
    peer_mapping_card = next(card for card in cards if card["kicker"] == "PEER MAPPING")
    assert peer_mapping_card["command"] == "make imports-validate"
    assert "buy" not in rendered
    assert "sell" not in rendered


def test_stock_report_local_context_cards_use_peer_front_door_when_commands_are_missing():
    coverage = pd.DataFrame(
        [
            {
                "dataset": "peers",
                "ticker": "NVDA",
                "ticker_present": False,
                "validation_status": "valid_with_warnings",
                "focus_command": "",
                "example_command": "",
            }
        ]
    )
    peer_summary = {
        "peer_dataset_present": False,
        "peer_count": 0,
        "peer_fundamentals_available": 0,
        "peer_market_context_available": 0,
    }

    cards = dashboard.stock_report_local_context_cards(coverage, peer_summary)
    peer_mapping_card = next(card for card in cards if card["kicker"] == "PEER MAPPING")

    assert peer_mapping_card["title"] == "Missing"
    assert peer_mapping_card["command"] == "make focus-peers TICKER=NVDA"


def test_stock_report_local_context_cards_use_staged_peer_front_door_when_commands_are_missing():
    coverage = pd.DataFrame(
        [
            {
                "dataset": "peers",
                "ticker": "NVDA",
                "ticker_present": True,
                "validation_status": "valid",
                "focus_command": "",
                "example_command": "",
                "target_file": "data/imports/peers.csv",
            }
        ]
    )
    peer_summary = {
        "peer_dataset_present": False,
        "peer_count": 2,
        "peer_fundamentals_available": 0,
        "peer_market_context_available": 0,
    }

    cards = dashboard.stock_report_local_context_cards(coverage, peer_summary)
    rendered = " ".join(str(value) for card in cards for value in card.values()).lower()
    peer_mapping_card = next(card for card in cards if card["kicker"] == "PEER MAPPING")

    assert peer_mapping_card["title"] == "Staged"
    assert peer_mapping_card["command"] == "make imports-validate"
    assert "make imports-preview" in rendered
    assert "make imports-apply" in rendered


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

    coverage = pd.DataFrame(
        [
            {"dataset": "prices", "ticker_present": True},
            {
                "dataset": "fundamentals",
                "ticker_present": False,
                "focus_command": "make imports-validate",
                "example_command": "make imports-preview",
                "target_file": "data/imports/fundamentals.csv",
            },
        ]
    )
    cards = dashboard.stock_report_next_step_cards(payload, coverage, {"peer_dataset_present": False})
    assert cards[0]["title"] == "Advance staged fundamentals import"
    assert cards[0]["command"] == "make imports-validate"
    assert "staged fundamentals" in cards[0]["body"].lower()

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

    coverage = pd.DataFrame(
        [
            {"dataset": "prices", "ticker_present": True},
            {"dataset": "fundamentals", "ticker_present": True},
            {
                "dataset": "peers",
                "ticker_present": True,
                "focus_command": "make imports-validate",
                "example_command": "make imports-preview",
                "target_file": "data/imports/peers.csv",
            },
        ]
    )
    cards = dashboard.stock_report_next_step_cards(payload, coverage, {"peer_dataset_present": False})
    assert cards[0]["title"] == "Advance staged peer import"
    assert cards[0]["command"] == "make imports-validate"
    assert "staged peer mappings" in cards[0]["body"].lower()

    payload["valuation_readiness"]["peer_ready"] = True
    cards = dashboard.stock_report_next_step_cards(payload, coverage, {"peer_dataset_present": True})
    assert cards[0]["title"] == "Review full report"


def test_stock_report_next_step_cards_use_staged_import_front_doors_when_commands_are_missing():
    payload = {
        "ticker": "NVDA",
        "valuation_readiness": {
            "dcf_ready": False,
            "peer_ready": False,
            "earnings_available": False,
            "analyst_estimates_available": False,
        },
        "missing_data_warnings": [],
    }
    coverage = pd.DataFrame(
        [
            {"dataset": "prices", "ticker_present": True},
            {
                "dataset": "fundamentals",
                "ticker_present": False,
                "target_file": "data/imports/fundamentals.csv",
            },
        ]
    )
    cards = dashboard.stock_report_next_step_cards(payload, coverage, {"peer_dataset_present": False})
    assert cards[0]["title"] == "Advance staged fundamentals import"
    assert cards[0]["command"] == "make imports-validate"

    payload["valuation_readiness"]["dcf_ready"] = True
    coverage = pd.DataFrame(
        [
            {"dataset": "prices", "ticker_present": True},
            {"dataset": "fundamentals", "ticker_present": True},
            {
                "dataset": "peers",
                "ticker_present": True,
                "target_file": "data/imports/peers.csv",
            },
        ]
    )
    cards = dashboard.stock_report_next_step_cards(payload, coverage, {"peer_dataset_present": False})
    assert cards[0]["title"] == "Advance staged peer import"
    assert cards[0]["command"] == "make imports-validate"


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
    assert cards[0]["command"] == "make validate-data"
    assert cards[1]["command"] == "make price-status TOP_N=10"
    assert cards[2]["command"] == "make action-queue-check TOP_N=10"
    assert cards[3]["command"] == "make data-wizard TOP_N=10"
    assert "make price-status top_n=10" in rendered.lower()
    assert "make action-queue-check top_n=10" in rendered.lower()
    assert "make data-wizard top_n=10" in rendered.lower()


def test_data_health_overview_cards_without_price_status_use_runbook_first_guidance():
    validation = pd.DataFrame({"validation_status": ["valid", "missing_file"]})
    action_queue = pd.DataFrame({"urgency": ["critical"]})
    coverage = pd.DataFrame({"usable_for_momentum": [False]})

    cards = dashboard.data_health_overview_cards(validation, None, action_queue, coverage)
    rendered = " ".join(str(value) for card in cards for value in card.values()).lower()

    assert "price status not generated" in rendered
    assert cards[0]["command"] == "make validate-data"
    assert cards[1]["command"] == "make runbook-prices-broader"
    assert cards[2]["command"] == "make action-queue-check TOP_N=10"
    assert cards[3]["command"] == "make data-wizard TOP_N=10"
    assert "make runbook-prices-broader" in rendered
    assert "make focus-price" in rendered
    assert "manual fallback" in rendered
    assert "make price-normalize" in rendered
    assert "make price-validate" in rendered
    assert "make price-preview" in rendered
    assert "make price-apply" in rendered
    assert "buy" not in rendered
    assert "sell" not in rendered


def test_data_health_overview_cards_surface_healthy_price_status_command_paths():
    validation = pd.DataFrame({"validation_status": ["valid", "valid_with_warnings"]})
    price_status = pd.DataFrame({"status": ["fetched", "skipped_fresh"]})
    action_queue = pd.DataFrame({"urgency": ["high", "medium"]})
    coverage = pd.DataFrame(
        {
            "usable_for_momentum": [True, True],
            "dcf_ready": [True, False],
            "peer_ready": [True, False],
            "has_earnings": [False, False],
            "has_analyst_estimates": [False, False],
            "missing_required_for_momentum": ["", ""],
            "missing_required_for_dcf": ["", "fundamentals"],
            "missing_required_for_peer_relative": ["", "peer mapping"],
        }
    )

    cards = dashboard.data_health_overview_cards(validation, price_status, action_queue, coverage)
    rendered = " ".join(str(value) for card in cards for value in card.values()).lower()

    assert cards[0]["command"] == "make validate-data"
    assert cards[1]["command"] == "make price-status TOP_N=10"
    assert cards[2]["command"] == "make action-queue-check TOP_N=10"
    assert cards[3]["command"] == "make data-wizard TOP_N=10"
    assert "latest price refresh did not report blocking source errors" in rendered
    assert "buy" not in rendered
    assert "sell" not in rendered


def test_data_health_overview_cards_handle_empty_validation_rows():
    validation = pd.DataFrame({"validation_status": []})
    price_status = pd.DataFrame({"status": ["fetched"]})
    action_queue = pd.DataFrame({"urgency": ["medium"]})
    coverage = pd.DataFrame({"usable_for_momentum": [False]})

    cards = dashboard.data_health_overview_cards(validation, price_status, action_queue, coverage)
    rendered = " ".join(str(value) for card in cards for value in card.values()).lower()

    assert cards[0]["title"] == "No validation rows"
    assert cards[0]["command"] == "make validate-data"
    assert cards[1]["command"] == "make price-status TOP_N=10"
    assert cards[2]["command"] == "make action-queue-check TOP_N=10"
    assert cards[3]["command"] == "make data-wizard TOP_N=10"
    assert "run local validation to inspect configured csv datasets" in rendered
    assert "buy" not in rendered
    assert "sell" not in rendered


def test_data_health_overview_cards_surface_top_staged_action_follow_through():
    validation = pd.DataFrame({"validation_status": ["valid", "valid_with_warnings"]})
    price_status = pd.DataFrame({"status": ["fetched"]})
    action_queue = pd.DataFrame(
        [
            {
                "priority": 1,
                "urgency": "critical",
                "action_type": "fundamentals",
                "ticker": "NVDA",
                "reason": "",
                "recommended_action": "Use staged local imports if the free refresh fails.",
                "focus_command": "make imports-validate",
                "example_command": "",
                "target_file": "data/imports/fundamentals.csv",
            }
        ]
    )
    coverage = pd.DataFrame({"usable_for_momentum": [True], "dcf_ready": [False], "peer_ready": [False]})

    cards = dashboard.data_health_overview_cards(validation, price_status, action_queue, coverage)
    action_card = next(card for card in cards if card["kicker"] == "NEXT ACTIONS")

    assert action_card["command"] == "make imports-validate"
    assert "make imports-preview" in action_card["body"].lower()
    assert "make imports-apply" in action_card["body"].lower()
    assert "use staged local imports if the free refresh fails" not in action_card["body"].lower()


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

    assert coverage_cards[0]["command"] == "make runbook-prices-broader"
    assert coverage_cards[1]["command"] == "make runbook-fundamentals-broader"
    assert coverage_cards[2]["command"] == "make runbook-peers-broader"
    assert coverage_cards[3]["command"] == "make onboarding"
    assert price_cards[0]["command"] == "make price-status TOP_N=10"
    assert price_cards[1]["command"] == "make price-status TOP_N=10"
    assert price_cards[2]["command"] == "make price-status TOP_N=10"
    assert staged_cards[0]["command"] == "make imports-preview"
    assert "1" in rendered
    assert "make price-status top_n=10" in rendered
    assert "manual fallback" in rendered
    assert "make price-normalize" in rendered
    assert "make price-validate" in rendered
    assert "make price-preview" in rendered
    assert "make price-apply" in rendered
    assert "preview first" in rendered
    assert "buy" not in rendered
    assert "sell" not in rendered


def test_data_health_tab_summary_cards_cover_sources_and_validation_fallbacks():
    validation = pd.DataFrame({"validation_status": ["valid", "valid_with_warnings", "missing_file"]})
    status = pd.DataFrame({"availability_status": ["available", "partial", "manual_only"]})

    source_cards = dashboard.data_health_tab_summary_cards("Sources", validation, None, status, None, {})
    validation_cards = dashboard.data_health_tab_summary_cards("Validation", validation, None, status, None, {})
    rendered = " ".join(
        str(value)
        for group in [source_cards, validation_cards]
        for card in group
        for value in card.values()
    ).lower()

    assert source_cards[0]["command"] == "make data-sources"
    assert source_cards[1]["command"] == "make data-sources"
    assert validation_cards[0]["command"] == "make validate-data"
    assert validation_cards[1]["command"] == "make validate-data"
    assert "status registry" in rendered
    assert "schema checks" in rendered
    assert "partial safe" in rendered
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


def test_data_health_fix_first_cards_fall_back_to_onboarding_refresh():
    cards = dashboard.data_health_fix_first_cards(None)
    rendered = " ".join(str(value) for card in cards for value in card).lower()

    assert len(cards) == 1
    assert cards[0][0] == "No fix-first actions yet"
    assert cards[0][2] == "make onboarding"
    assert "make onboarding" in rendered
    assert "buy" not in rendered
    assert "sell" not in rendered


def test_data_health_fix_first_cards_use_lane_front_doors_when_commands_are_missing():
    actions = pd.DataFrame(
        [
            {
                "priority": 1,
                "dataset": "peers",
                "ticker": "AMD",
                "reason": "Peer mappings are missing.",
                "recommended_action": "Research a peer set and stage it through the imports workflow.",
                "focus_command": "",
                "example_command": "",
            }
        ]
    )

    cards = dashboard.data_health_fix_first_cards(actions)

    assert cards[0][0] == "P1 peers - AMD"
    assert cards[0][2] == "make focus-peers TICKER=AMD"


def test_data_health_fix_first_cards_normalize_legacy_status_copy():
    actions = pd.DataFrame(
        [
            {
                "priority": 1,
                "dataset": "fundamentals",
                "ticker": "NVDA",
                "reason": "Local fundamentals still need staged validation.",
                "recommended_action": "Run make imports-validate, then make imports-preview, then make imports-apply, then make status to confirm the staged fundamentals.",
                "focus_command": "make focus-fundamentals TICKER=NVDA",
                "example_command": "",
            }
        ]
    )

    cards = dashboard.data_health_fix_first_cards(actions)

    assert "make status-check TOP_N=5" in cards[0][1]


def test_data_health_fix_first_cards_use_staged_flow_fallback_when_row_copy_is_missing():
    actions = pd.DataFrame(
        [
            {
                "priority": 1,
                "dataset": "fundamentals",
                "ticker": "NVDA",
                "reason": "",
                "recommended_action": "",
                "focus_command": "make imports-validate",
                "example_command": "",
            },
            {
                "priority": 2,
                "dataset": "peers",
                "ticker": "TSLA",
                "reason": "",
                "recommended_action": "",
                "focus_command": "make runbook-peers",
                "example_command": "",
            },
            {
                "priority": 3,
                "dataset": "peers",
                "ticker": "",
                "reason": "",
                "recommended_action": "",
                "focus_command": "make bundle-peers",
                "example_command": "",
            }
        ]
    )

    cards = dashboard.data_health_fix_first_cards(actions)

    assert cards[0][0] == "P1 fundamentals - NVDA"
    assert cards[0][2] == "make imports-validate"
    assert "staged local workflow next" in cards[0][1].lower()
    assert cards[1][2] == "make runbook-peers"
    assert "staged local workflow next" in cards[1][1].lower()
    assert cards[2][2] == "make bundle-peers"
    assert "highest-leverage local bundle first" in cards[2][1].lower()
    assert "not available" not in cards[0][1].lower()
    assert "not available" not in " ".join(card[1] for card in cards).lower()


def test_data_health_fix_first_cards_keep_staged_follow_through_visible_when_target_files_are_present():
    actions = pd.DataFrame(
        [
            {
                "priority": 1,
                "dataset": "fundamentals",
                "ticker": "NVDA",
                "reason": "",
                "recommended_action": "Use staged local imports if the free refresh fails.",
                "focus_command": "make imports-validate",
                "example_command": "",
                "target_file": "data/imports/fundamentals.csv",
            },
            {
                "priority": 2,
                "dataset": "peers",
                "ticker": "TSLA",
                "reason": "",
                "recommended_action": "Use staged local imports if the free refresh fails.",
                "focus_command": "make imports-validate",
                "example_command": "",
                "target_file": "data/imports/peers.csv",
            },
            {
                "priority": 3,
                "dataset": "prices",
                "ticker": "AMD",
                "reason": "",
                "recommended_action": "Use staged local imports if the free refresh fails.",
                "focus_command": "make price-validate",
                "example_command": "",
                "target_file": "data/imports/prices.csv",
            },
        ]
    )

    cards = dashboard.data_health_fix_first_cards(actions)

    assert cards[0][2] == "make imports-validate"
    assert "make imports-preview" in cards[0][1].lower()
    assert "make imports-apply" in cards[0][1].lower()
    assert cards[1][2] == "make imports-validate"
    assert "make imports-preview" in cards[1][1].lower()
    assert "make imports-apply" in cards[1][1].lower()
    assert cards[2][2] == "make price-validate"
    assert "make price-preview" in cards[2][1].lower()
    assert "make price-apply" in cards[2][1].lower()
    assert "use staged local imports if the free refresh fails" not in " ".join(card[1] for card in cards).lower()


def test_data_health_action_path_cards_surface_best_and_lane_commands():
    actions = pd.DataFrame(
        [
            {
                "priority": 1,
                "dataset": "prices",
                "ticker": "NVDA",
                "reason": "No verified local price history is present yet.",
                "recommended_action": "Normalize verified downloaded OHLCV rows, then run make price-validate, make price-preview, and make price-apply.",
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
                "recommended_action": "Normalize verified downloaded OHLCV rows, then run make price-validate, make price-preview, and make price-apply.",
                "focus_command": "make focus-price TICKER=NVDA",
                "example_command": "make price-worklist",
            }
        ]
    )

    cards = dashboard.data_health_action_path_cards(actions, queue)
    rendered = " ".join(str(value) for card in cards for value in card.values()).lower()

    assert len(cards) == 4
    assert cards[0]["kicker"] == "BEST NEXT"
    assert cards[0]["title"] == "make focus-price TICKER=NVDA"
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
    assert cards[0]["command"] == "make onboarding"
    assert "make onboarding" in rendered
    assert "buy" not in rendered
    assert "sell" not in rendered


def test_data_health_action_path_cards_use_lane_and_queue_front_doors_when_commands_are_missing():
    actions = pd.DataFrame(
        [
            {
                "priority": 2,
                "dataset": "fundamentals",
                "ticker": "AMD",
                "reason": "DCF inputs are still incomplete.",
                "recommended_action": "Run SEC staging for fundamentals, then validate and preview before applying.",
            }
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
            }
        ]
    )

    cards = dashboard.data_health_action_path_cards(actions, queue)
    rendered = " ".join(str(value) for card in cards for value in card.values()).lower()

    assert cards[0]["title"] == "make focus-price TICKER=NVDA"
    assert cards[0]["command"] == "make focus-price TICKER=NVDA"
    assert any(card.get("command") == "make focus-fundamentals TICKER=AMD" for card in cards)
    assert "make focus-price ticker=nvda" in rendered
    assert "make focus-fundamentals ticker=amd" in rendered
    assert "buy" not in rendered
    assert "sell" not in rendered


def test_data_health_action_path_cards_use_review_fallback_when_row_copy_is_missing():
    actions = pd.DataFrame(
        [
            {
                "priority": 2,
                "dataset": "peers",
                "ticker": "AMD",
                "reason": "",
                "recommended_action": "",
            }
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
                "reason": "",
                "recommended_action": "",
            }
        ]
    )

    cards = dashboard.data_health_action_path_cards(actions, queue)
    rendered = " ".join(str(value) for card in cards for value in card.values()).lower()

    assert cards[0]["title"] == "make focus-price TICKER=NVDA"
    assert "review price path." in cards[0]["body"].lower()
    assert any("review peer path." in str(card.get("body", "")).lower() for card in cards)
    assert "not available" not in rendered


def test_data_health_action_path_cards_use_command_family_fallbacks_when_row_copy_is_missing():
    actions = pd.DataFrame(
        [
            {
                "priority": 2,
                "dataset": "fundamentals",
                "ticker": "NVDA",
                "reason": "",
                "recommended_action": "",
                "focus_command": "make imports-validate",
                "example_command": "",
            },
            {
                "priority": 3,
                "dataset": "peers",
                "ticker": "TSLA",
                "reason": "",
                "recommended_action": "",
                "focus_command": "make runbook-peers",
                "example_command": "",
            }
        ]
    )
    queue = pd.DataFrame(
        [
            {
                "priority": 1,
                "urgency": "critical",
                "action_type": "fundamentals",
                "ticker": "NVDA",
                "title": "Advance staged fundamentals",
                "reason": "",
                "recommended_action": "",
                "focus_command": "make imports-validate",
                "example_command": "",
            }
        ]
    )

    cards = dashboard.data_health_action_path_cards(actions, queue)

    assert cards[0]["title"] == "make imports-validate"
    assert "staged local workflow next" in cards[0]["body"].lower()
    assert any("staged local workflow next" in str(card.get("body", "")).lower() for card in cards[1:])
    assert any(card.get("command") == "make runbook-peers" for card in cards[1:])
    assert "not available" not in " ".join(str(value) for card in cards for value in card.values()).lower()


def test_data_health_action_path_cards_keep_staged_follow_through_visible_when_target_files_are_present():
    actions = pd.DataFrame(
        [
            {
                "priority": 2,
                "dataset": "fundamentals",
                "ticker": "NVDA",
                "reason": "",
                "recommended_action": "Use staged local imports if the free refresh fails.",
                "focus_command": "make imports-validate",
                "example_command": "",
                "target_file": "data/imports/fundamentals.csv",
            },
            {
                "priority": 3,
                "dataset": "peers",
                "ticker": "TSLA",
                "reason": "",
                "recommended_action": "Use staged local imports if the free refresh fails.",
                "focus_command": "make imports-validate",
                "example_command": "",
                "target_file": "data/imports/peers.csv",
            },
            {
                "priority": 4,
                "dataset": "prices",
                "ticker": "AMD",
                "reason": "",
                "recommended_action": "Use staged local imports if the free refresh fails.",
                "focus_command": "make price-validate",
                "example_command": "",
                "target_file": "data/imports/prices.csv",
            },
        ]
    )
    queue = pd.DataFrame(
        [
            {
                "priority": 1,
                "urgency": "critical",
                "action_type": "fundamentals",
                "ticker": "NVDA",
                "title": "Advance staged fundamentals",
                "reason": "",
                "recommended_action": "Use staged local imports if the free refresh fails.",
                "focus_command": "make imports-validate",
                "example_command": "",
                "target_file": "data/imports/fundamentals.csv",
            }
        ]
    )

    cards = dashboard.data_health_action_path_cards(actions, queue)
    rendered = " ".join(str(value) for card in cards for value in card.values()).lower()

    assert cards[0]["title"] == "make imports-validate"
    assert "make imports-preview" in cards[0]["body"].lower()
    assert any(card.get("command") == "make imports-validate" and "make imports-preview" in str(card.get("body", "")).lower() for card in cards[1:3])
    assert any(card.get("command") == "make price-validate" and "make price-preview" in str(card.get("body", "")).lower() for card in cards)
    assert "use staged local imports if the free refresh fails" not in rendered


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
                "follow_up_command": "make imports-validate",
                "target_file": "data/imports/fundamentals.csv",
                "why_it_matters": "This holding is the best next candidate for explicit local DCF inputs.",
                "safe_next_step": "Keep SEC enrichment staged and review-only until make imports-validate, make imports-preview, and make imports-apply confirm the merge.",
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


def test_data_health_command_bundle_cards_use_review_fallback_when_summaries_are_missing():
    bundles = pd.DataFrame(
        [
            {
                "bundle_name": "Peer Mapping Bundle",
                "lane": "peers",
                "scope": "holdings_first",
                "ticker_count": 1,
                "tickers": "TSLA",
                "goal_summary": "",
                "why_it_matters": "",
                "bundle_shortcut_command": "",
                "detail_shortcut_command": "",
                "runbook_shortcut_command": "make runbook-peers",
                "primary_command": "",
            }
        ]
    )

    cards = dashboard.data_health_command_bundle_cards(bundles)

    assert cards[0]["command"] == "make runbook-peers"
    assert "staged local workflow next" in cards[0]["body"].lower()
    assert "not available" not in cards[0]["body"].lower()
    assert "not available" not in cards[0]["body"].lower()


def test_data_health_command_bundle_cards_use_staged_follow_through_when_summaries_are_missing():
    bundles = pd.DataFrame(
        [
            {
                "bundle_name": "SEC Fundamentals Bundle",
                "lane": "fundamentals",
                "scope": "holdings_first",
                "ticker_count": 3,
                "tickers": "META,NVDA,TSLA",
                "goal_summary": "",
                "why_it_matters": "",
                "bundle_shortcut_command": "",
                "detail_shortcut_command": "",
                "runbook_shortcut_command": "make runbook-fundamentals",
                "primary_command": "",
                "target_file": "data/imports/fundamentals.csv",
                "safe_next_step": "Keep SEC enrichment staged and review-only until make imports-validate, make imports-preview, and make imports-apply confirm the merge.",
            }
        ]
    )

    cards = dashboard.data_health_command_bundle_cards(bundles)

    assert cards[0]["command"] == "make runbook-fundamentals"
    assert "make imports-preview" in cards[0]["body"].lower()
    assert "make imports-apply" in cards[0]["body"].lower()
    assert "not available" not in cards[0]["body"].lower()


def test_data_health_command_bundle_cards_use_price_staged_follow_through_when_summaries_are_missing():
    bundles = pd.DataFrame(
        [
            {
                "bundle_name": "Price Coverage Bundle",
                "lane": "prices",
                "scope": "holdings_first",
                "ticker_count": 2,
                "tickers": "AMD,AVGO",
                "goal_summary": "",
                "why_it_matters": "",
                "bundle_shortcut_command": "",
                "detail_shortcut_command": "",
                "runbook_shortcut_command": "make runbook-prices",
                "primary_command": "",
                "target_file": "data/imports/prices.csv",
                "safe_next_step": "",
            }
        ]
    )

    cards = dashboard.data_health_command_bundle_cards(bundles)

    assert cards[0]["command"] == "make runbook-prices"
    assert "make price-validate" in cards[0]["body"].lower()
    assert "make price-preview" in cards[0]["body"].lower()
    assert "make price-apply" in cards[0]["body"].lower()
    assert "not available" not in cards[0]["body"].lower()


def test_data_health_command_bundle_cards_upgrade_generic_price_staged_note_to_explicit_follow_through():
    bundles = pd.DataFrame(
        [
            {
                "bundle_name": "Price Coverage Bundle",
                "lane": "prices",
                "scope": "holdings_first",
                "ticker_count": 2,
                "tickers": "AMD,AVGO",
                "goal_summary": "",
                "why_it_matters": "",
                "bundle_shortcut_command": "",
                "detail_shortcut_command": "",
                "runbook_shortcut_command": "make runbook-prices",
                "primary_command": "",
                "target_file": "data/imports/prices.csv",
                "safe_next_step": "Use staged local imports if the free refresh fails.",
            }
        ]
    )

    cards = dashboard.data_health_command_bundle_cards(bundles)

    assert cards[0]["command"] == "make runbook-prices"
    assert "make price-validate" in cards[0]["body"].lower()
    assert "make price-preview" in cards[0]["body"].lower()
    assert "make price-apply" in cards[0]["body"].lower()


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

    assert bundle_cards[0]["command"] == "make onboarding"
    assert bundle_cards[0]["title"] == "No command bundles yet"
    assert runbook_cards[0]["command"] == "make onboarding"
    assert runbook_cards[0]["title"] == "No bundle runbook yet"
    assert target_cards[0]["command"] == "make onboarding"
    assert target_cards[0]["title"] == "No price targets yet"
    assert "run make onboarding to refresh the onboarding outputs" in rendered
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
                "command": "make price-status",
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
    assert "make price-status" in rendered
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
    assert "make status-check top_n=5" in rendered
    assert "buy" not in rendered
    assert "sell" not in rendered


def test_data_health_command_bundle_runbook_cards_use_staged_follow_through_when_goal_summary_is_missing():
    runbook = pd.DataFrame(
        [
            {
                "bundle_name": "SEC Fundamentals Bundle",
                "lane": "fundamentals",
                "scope": "holdings_first",
                "step_order": 1,
                "step_label": "Review staged import",
                "command": "make imports-validate",
                "tickers": "META,NVDA,TSLA",
                "goal_summary": "",
                "target_file": "data/imports/fundamentals.csv",
                "safe_next_step": "Keep SEC enrichment staged and review-only until make imports-validate, make imports-preview, and make imports-apply confirm the merge.",
            }
        ]
    )

    cards = dashboard.data_health_command_bundle_runbook_cards(runbook)

    assert cards[0]["command"] == "make imports-validate"
    assert "make imports-preview" in cards[0]["body"].lower()
    assert "make imports-apply" in cards[0]["body"].lower()
    assert "review staged import" in cards[0]["body"].lower()


def test_data_health_command_bundle_runbook_cards_use_price_staged_follow_through_when_goal_summary_is_missing():
    runbook = pd.DataFrame(
        [
            {
                "bundle_name": "Price Coverage Bundle",
                "lane": "prices",
                "scope": "holdings_first",
                "step_order": 1,
                "step_label": "Review staged import",
                "command": "make price-validate",
                "tickers": "AMD,AVGO",
                "goal_summary": "",
                "target_file": "data/imports/prices.csv",
                "safe_next_step": "",
            }
        ]
    )

    cards = dashboard.data_health_command_bundle_runbook_cards(runbook)

    assert cards[0]["command"] == "make price-validate"
    assert "make price-preview" in cards[0]["body"].lower()
    assert "make price-apply" in cards[0]["body"].lower()
    assert "review staged import" in cards[0]["body"].lower()


def test_data_health_command_bundle_runbook_cards_upgrade_generic_price_staged_note_to_explicit_follow_through():
    runbook = pd.DataFrame(
        [
            {
                "bundle_name": "Price Coverage Bundle",
                "lane": "prices",
                "scope": "holdings_first",
                "step_order": 1,
                "step_label": "Review staged import",
                "command": "make price-validate",
                "tickers": "AMD,AVGO",
                "goal_summary": "",
                "target_file": "data/imports/prices.csv",
                "safe_next_step": "Use staged local imports if the free refresh fails.",
            }
        ]
    )

    cards = dashboard.data_health_command_bundle_runbook_cards(runbook)

    assert cards[0]["command"] == "make price-validate"
    assert "make price-preview" in cards[0]["body"].lower()
    assert "make price-apply" in cards[0]["body"].lower()
    assert "use staged local imports if the free refresh fails" not in cards[0]["body"].lower()


def test_data_health_command_bundle_runbook_cards_use_staged_command_when_steps_are_blank():
    runbook = pd.DataFrame(
        [
            {
                "bundle_name": "SEC Fundamentals Bundle",
                "lane": "fundamentals",
                "scope": "holdings_first",
                "step_order": 1,
                "step_label": "Review staged import",
                "command": "",
                "tickers": "META,NVDA,TSLA",
                "goal_summary": "",
                "target_file": "data/imports/fundamentals.csv",
                "safe_next_step": "Keep SEC enrichment staged and review-only until make imports-validate, make imports-preview, and make imports-apply confirm the merge.",
            }
        ]
    )

    cards = dashboard.data_health_command_bundle_runbook_cards(runbook)

    assert cards[0]["command"] == "make imports-validate"
    assert "review staged import: make imports-validate" in cards[0]["body"].lower()
    assert "make imports-preview" in cards[0]["body"].lower()
    assert "no runbook steps available" not in cards[0]["body"].lower()


def test_data_health_command_bundle_runbook_cards_use_price_staged_command_when_steps_are_blank():
    runbook = pd.DataFrame(
        [
            {
                "bundle_name": "Price Coverage Bundle",
                "lane": "prices",
                "scope": "holdings_first",
                "step_order": 1,
                "step_label": "Review staged import",
                "command": "",
                "tickers": "AMD,AVGO",
                "goal_summary": "",
                "target_file": "data/imports/prices.csv",
                "safe_next_step": "",
            }
        ]
    )

    cards = dashboard.data_health_command_bundle_runbook_cards(runbook)

    assert cards[0]["command"] == "make price-validate"
    assert "review staged import: make price-validate" in cards[0]["body"].lower()
    assert "make price-preview" in cards[0]["body"].lower()
    assert "make price-apply" in cards[0]["body"].lower()
    assert "no runbook steps available" not in cards[0]["body"].lower()


def test_data_health_command_bundle_runbook_cards_use_why_it_matters_when_goal_summary_is_missing():
    runbook = pd.DataFrame(
        [
            {
                "bundle_name": "Peer Mapping Bundle",
                "lane": "peers",
                "scope": "holdings_first",
                "step_order": 1,
                "step_label": "Fill peer mappings manually",
                "command": "data/imports/peers.csv",
                "tickers": "META,NVDA,TSLA",
                "goal_summary": "",
                "why_it_matters": "These tickers are closest to peer-relative coverage once manually researched mappings are added locally.",
            }
        ]
    )

    cards = dashboard.data_health_command_bundle_runbook_cards(runbook)

    assert "closest to peer-relative coverage" in cards[0]["body"].lower()
    assert "fill peer mappings manually: data/imports/peers.csv" in cards[0]["body"].lower()


def test_data_health_command_bundle_runbook_cards_use_runbook_fallback_when_summaries_are_missing():
    runbook = pd.DataFrame(
        [
            {
                "bundle_name": "Peer Mapping Bundle",
                "lane": "peers",
                "scope": "holdings_first",
                "step_order": 1,
                "step_label": "Open peer runbook",
                "command": "make runbook-peers",
                "tickers": "TSLA",
                "goal_summary": "",
                "why_it_matters": "",
            }
        ]
    )

    cards = dashboard.data_health_command_bundle_runbook_cards(runbook)

    assert cards[0]["command"] == "make runbook-peers"
    assert "staged local workflow next" in cards[0]["body"].lower()
    assert "not available" not in cards[0]["body"].lower()


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


def test_data_health_price_target_cards_keep_staged_price_follow_through_visible():
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
                "focus_command": "make focus-price TICKER=META",
                "example_command": "make price-normalize INPUT=data/raw/prices/META.csv TICKER=META SOURCE=yahoo_manual",
                "target_file": "data/imports/prices.csv",
                "safe_next_step": "Run make price-validate and make price-preview before make price-apply; do not fabricate missing history.",
            }
        ]
    )

    cards = dashboard.data_health_price_target_cards(worklist)
    rendered = " ".join(str(value) for card in cards for value in card.values()).lower()

    assert cards[0]["command"] == "make focus-price TICKER=META"
    assert "price-normalize" in rendered
    assert "make price-validate" in rendered
    assert "make price-preview" in rendered
    assert "make price-apply" in rendered
    assert "do not fabricate missing history" in rendered


def test_data_health_price_target_cards_upgrade_generic_staged_note_to_explicit_follow_through():
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
                "focus_command": "make focus-price TICKER=META",
                "example_command": "make price-normalize INPUT=data/raw/prices/META.csv TICKER=META SOURCE=yahoo_manual",
                "target_file": "data/imports/prices.csv",
                "safe_next_step": "Use staged local imports if the free refresh fails.",
            }
        ]
    )

    cards = dashboard.data_health_price_target_cards(worklist)
    rendered = " ".join(str(value) for card in cards for value in card.values()).lower()

    assert cards[0]["command"] == "make focus-price TICKER=META"
    assert "price-normalize" in rendered
    assert "make price-validate" in rendered
    assert "make price-preview" in rendered
    assert "make price-apply" in rendered


def test_price_target_cards_use_price_front_doors_when_commands_are_missing():
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
                "example_command": "",
                "focus_command": "",
            },
            {
                "priority": 2,
                "ticker": "",
                "price_history_days": 0,
                "next_price_goal": "Reach Preferred 1Y History",
                "next_target_history_rows": 252,
                "rows_needed_for_next_goal": 189,
                "suggested_start_date": "2025-01-01",
                "example_command": "",
                "focus_command": "",
            },
        ]
    )

    data_health_cards = dashboard.data_health_price_target_cards(worklist)
    overview_cards = dashboard.overview_price_target_cards(worklist)

    assert data_health_cards[0]["command"] == "make focus-price TICKER=META"
    assert overview_cards[0]["command"] == "make focus-price TICKER=META"
    assert data_health_cards[1]["command"] == "make runbook-prices-broader"
    assert overview_cards[1]["command"] == "make runbook-prices-broader"


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
                "example_command": "make sec-stage TICKERS=NVDA",
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


def test_data_health_deep_research_target_cards_preserve_staged_fundamentals_command():
    sec_queue = pd.DataFrame(
        [
            {
                "priority": 1,
                "ticker": "NVDA",
                "is_holding": True,
                "theme": "AI Semis",
                "price_history_days": 63,
                "missing_required_for_dcf": "staged fundamentals still need make imports-validate, make imports-preview, and make imports-apply",
                "recommended_action": "Run make imports-validate, then make imports-preview, then make imports-apply, then make status to confirm the live staged fundamentals.",
                "focus_command": "make imports-validate",
                "example_command": "make imports-preview",
                "target_file": "data/imports/fundamentals.csv",
            }
        ]
    )

    cards = dashboard.data_health_deep_research_target_cards(sec_queue, pd.DataFrame())

    assert cards[0]["command"] == "make imports-validate"
    assert "make imports-apply" in cards[0]["body"].lower()
    assert "make status-check top_n=5" in cards[0]["body"].lower()


def test_data_health_deep_research_target_cards_use_review_fallback_when_action_is_missing():
    sec_queue = pd.DataFrame(
        [
            {
                "priority": 1,
                "ticker": "AMD",
                "is_holding": False,
                "theme": "Semis",
                "price_history_days": 84,
                "missing_required_for_dcf": "fundamentals row",
                "recommended_action": "",
                "example_command": "",
            }
        ]
    )

    cards = dashboard.data_health_deep_research_target_cards(sec_queue, pd.DataFrame())

    assert "review fundamentals path." in cards[0]["body"].lower()
    assert "not available" not in cards[0]["body"].lower()


def test_data_health_deep_research_target_cards_use_runbook_fallback_when_action_is_missing():
    sec_queue = pd.DataFrame(
        [
            {
                "priority": 1,
                "ticker": "AMD",
                "is_holding": False,
                "theme": "Semis",
                "price_history_days": 84,
                "missing_required_for_dcf": "fundamentals row",
                "recommended_action": "",
                "focus_command": "make runbook-fundamentals",
                "example_command": "",
            }
        ]
    )

    cards = dashboard.data_health_deep_research_target_cards(sec_queue, pd.DataFrame())

    assert cards[0]["command"] == "make runbook-fundamentals"
    assert "staged local workflow next" in cards[0]["body"].lower()
    assert "not available" not in cards[0]["body"].lower()


def test_data_health_deep_research_target_cards_use_peer_review_fallback_when_action_is_missing():
    peer_queue = pd.DataFrame(
        [
            {
                "priority": 1,
                "ticker": "TSLA",
                "is_holding": False,
                "theme": "EV",
                "dcf_ready": False,
                "missing_required_for_peer_relative": "peer mapping",
                "recommended_action": "",
                "example_command": "",
            }
        ]
    )

    cards = dashboard.data_health_deep_research_target_cards(pd.DataFrame(), peer_queue)

    assert "review peer path." in cards[0]["body"].lower()
    assert "not available" not in cards[0]["body"].lower()


def test_data_health_deep_research_target_cards_use_peer_runbook_fallback_when_action_is_missing():
    peer_queue = pd.DataFrame(
        [
            {
                "priority": 1,
                "ticker": "TSLA",
                "is_holding": False,
                "theme": "EV",
                "dcf_ready": False,
                "missing_required_for_peer_relative": "peer mapping",
                "recommended_action": "",
                "focus_command": "make runbook-peers",
                "example_command": "",
            }
        ]
    )

    cards = dashboard.data_health_deep_research_target_cards(pd.DataFrame(), peer_queue)

    assert cards[0]["command"] == "make runbook-peers"
    assert "staged local workflow next" in cards[0]["body"].lower()
    assert "not available" not in cards[0]["body"].lower()


def test_data_health_deep_research_target_cards_keep_staged_import_paths_when_commands_are_missing():
    sec_queue = pd.DataFrame(
        [
            {
                "priority": 1,
                "ticker": "NVDA",
                "is_holding": True,
                "theme": "AI Semis",
                "price_history_days": 63,
                "missing_required_for_dcf": "staged fundamentals still need validate/preview/apply",
                "recommended_action": "",
                "focus_command": "",
                "example_command": "",
                "target_file": "data/imports/fundamentals.csv",
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
                "missing_required_for_peer_relative": "staged peers still need validate/preview/apply",
                "recommended_action": "",
                "focus_command": "",
                "example_command": "",
                "target_file": "data/imports/peers.csv",
            }
        ]
    )

    cards = dashboard.data_health_deep_research_target_cards(sec_queue, peer_queue)

    assert cards[0]["command"] == "make imports-validate"
    assert "staged fundamentals import" in cards[0]["body"].lower()
    assert cards[1]["command"] == "make imports-validate"
    assert "staged peer import" in cards[1]["body"].lower()


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


def test_overview_price_target_cards_keep_staged_price_follow_through_visible():
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
                "focus_command": "make focus-price TICKER=META",
                "example_command": "make price-normalize INPUT=data/raw/prices/META.csv TICKER=META SOURCE=yahoo_manual",
                "target_file": "data/imports/prices.csv",
                "safe_next_step": "Run make price-validate and make price-preview before make price-apply; do not fabricate missing history.",
            }
        ]
    )

    cards = dashboard.overview_price_target_cards(worklist)
    rendered = " ".join(str(value) for card in cards for value in card.values()).lower()

    assert cards[0]["command"] == "make focus-price TICKER=META"
    assert "price-normalize" in rendered
    assert "make price-validate" in rendered
    assert "make price-preview" in rendered
    assert "make price-apply" in rendered
    assert "do not fabricate missing history" in rendered


def test_overview_price_target_cards_upgrade_generic_staged_note_to_explicit_follow_through():
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
                "focus_command": "make focus-price TICKER=META",
                "example_command": "make price-normalize INPUT=data/raw/prices/META.csv TICKER=META SOURCE=yahoo_manual",
                "target_file": "data/imports/prices.csv",
                "safe_next_step": "Use staged local imports if the free refresh fails.",
            }
        ]
    )

    cards = dashboard.overview_price_target_cards(worklist)
    rendered = " ".join(str(value) for card in cards for value in card.values()).lower()

    assert cards[0]["command"] == "make focus-price TICKER=META"
    assert "price-normalize" in rendered
    assert "make price-validate" in rendered
    assert "make price-preview" in rendered
    assert "make price-apply" in rendered


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
                "example_command": "make sec-stage TICKERS=NVDA",
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


def test_overview_deep_research_target_cards_preserve_staged_fundamentals_command():
    sec_queue = pd.DataFrame(
        [
            {
                "priority": 1,
                "ticker": "NVDA",
                "is_holding": True,
                "theme": "AI Semis",
                "price_history_days": 63,
                "missing_required_for_dcf": "staged fundamentals still need make imports-validate, make imports-preview, and make imports-apply",
                "recommended_action": "Run make imports-validate, then make imports-preview, then make imports-apply, then make status to confirm the live staged fundamentals.",
                "focus_command": "make imports-validate",
                "example_command": "make imports-preview",
                "target_file": "data/imports/fundamentals.csv",
            }
        ]
    )

    cards = dashboard.overview_deep_research_target_cards(sec_queue, pd.DataFrame())

    assert cards[0]["command"] == "make imports-validate"
    assert "make imports-apply" in cards[0]["body"].lower()
    assert "make status-check top_n=5" in cards[0]["body"].lower()


def test_overview_deep_research_target_cards_use_review_fallback_when_action_is_missing():
    sec_queue = pd.DataFrame(
        [
            {
                "priority": 1,
                "ticker": "AMD",
                "is_holding": False,
                "theme": "Semis",
                "price_history_days": 84,
                "missing_required_for_dcf": "fundamentals row",
                "recommended_action": "",
                "example_command": "",
            }
        ]
    )

    cards = dashboard.overview_deep_research_target_cards(sec_queue, pd.DataFrame())

    assert "review fundamentals path." in cards[0]["body"].lower()
    assert "not available" not in cards[0]["body"].lower()


def test_overview_deep_research_target_cards_use_runbook_fallback_when_action_is_missing():
    sec_queue = pd.DataFrame(
        [
            {
                "priority": 1,
                "ticker": "AMD",
                "is_holding": False,
                "theme": "Semis",
                "price_history_days": 84,
                "missing_required_for_dcf": "fundamentals row",
                "recommended_action": "",
                "focus_command": "make runbook-fundamentals",
                "example_command": "",
            }
        ]
    )

    cards = dashboard.overview_deep_research_target_cards(sec_queue, pd.DataFrame())

    assert cards[0]["command"] == "make runbook-fundamentals"
    assert "staged local workflow next" in cards[0]["body"].lower()
    assert "not available" not in cards[0]["body"].lower()


def test_overview_deep_research_target_cards_use_peer_review_fallback_when_action_is_missing():
    peer_queue = pd.DataFrame(
        [
            {
                "priority": 1,
                "ticker": "TSLA",
                "is_holding": False,
                "theme": "EV",
                "dcf_ready": False,
                "missing_required_for_peer_relative": "peer mapping",
                "recommended_action": "",
                "example_command": "",
            }
        ]
    )

    cards = dashboard.overview_deep_research_target_cards(pd.DataFrame(), peer_queue)

    assert "review peer path." in cards[0]["body"].lower()
    assert "not available" not in cards[0]["body"].lower()


def test_overview_deep_research_target_cards_use_peer_runbook_fallback_when_action_is_missing():
    peer_queue = pd.DataFrame(
        [
            {
                "priority": 1,
                "ticker": "TSLA",
                "is_holding": False,
                "theme": "EV",
                "dcf_ready": False,
                "missing_required_for_peer_relative": "peer mapping",
                "recommended_action": "",
                "focus_command": "make runbook-peers",
                "example_command": "",
            }
        ]
    )

    cards = dashboard.overview_deep_research_target_cards(pd.DataFrame(), peer_queue)

    assert cards[0]["command"] == "make runbook-peers"
    assert "staged local workflow next" in cards[0]["body"].lower()
    assert "not available" not in cards[0]["body"].lower()


def test_overview_deep_research_target_cards_keep_staged_import_paths_when_commands_are_missing():
    sec_queue = pd.DataFrame(
        [
            {
                "priority": 1,
                "ticker": "NVDA",
                "is_holding": True,
                "theme": "AI Semis",
                "price_history_days": 63,
                "missing_required_for_dcf": "staged fundamentals still need validate/preview/apply",
                "recommended_action": "",
                "focus_command": "",
                "example_command": "",
                "target_file": "data/imports/fundamentals.csv",
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
                "missing_required_for_peer_relative": "staged peers still need validate/preview/apply",
                "recommended_action": "",
                "focus_command": "",
                "example_command": "",
                "target_file": "data/imports/peers.csv",
            }
        ]
    )

    cards = dashboard.overview_deep_research_target_cards(sec_queue, peer_queue)

    assert cards[0]["command"] == "make imports-validate"
    assert "staged fundamentals import" in cards[0]["body"].lower()
    assert cards[1]["command"] == "make imports-validate"
    assert "staged peer import" in cards[1]["body"].lower()


def test_deep_research_target_fallback_cards_use_onboarding_refresh():
    data_health_cards = dashboard.data_health_deep_research_target_cards(None, None)
    overview_cards = dashboard.overview_deep_research_target_cards(None, None)
    price_cards = dashboard.overview_price_target_cards(None)

    rendered = " ".join(
        str(value)
        for card_group in (data_health_cards, overview_cards, price_cards)
        for card in card_group
        for value in card.values()
    ).lower()

    assert data_health_cards[0]["command"] == "make onboarding"
    assert data_health_cards[0]["title"] == "No DCF or peer targets yet"
    assert overview_cards[0]["command"] == "make onboarding"
    assert overview_cards[0]["title"] == "No DCF or peer targets yet"
    assert price_cards[0]["command"] == "make onboarding"
    assert price_cards[0]["title"] == "No price targets yet"
    assert "run make onboarding" in rendered
    assert "buy" not in rendered
    assert "sell" not in rendered


def test_overview_bundle_empty_states_use_operator_facing_titles():
    bundle_cards = dashboard.overview_command_bundle_cards(None)
    handoff_cards = dashboard.overview_bundle_handoff_cards(None, None, None)
    runbook_cards = dashboard.overview_bundle_runbook_cards(None)

    assert bundle_cards[0]["title"] == "No command bundles yet"
    assert handoff_cards[0]["title"] == "No bundle guidance yet"
    assert runbook_cards[0]["title"] == "No bundle runbook yet"
    assert bundle_cards[0]["command"] == "make onboarding"
    assert handoff_cards[0]["command"] == "make onboarding"
    assert runbook_cards[0]["command"] == "make onboarding"


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
                "recommended_action": "Refresh NVDA prices, or normalize verified downloaded OHLCV rows into data/imports/prices.csv before make price-validate, make price-preview, and make price-apply.",
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
                "example_command": "make sec-stage TICKERS=NVDA",
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
    assert cards[0]["command"] == "make data-wizard TOP_N=10"
    assert "make data-wizard" in rendered


def test_data_coverage_wizard_cards_use_lane_front_doors_when_commands_are_missing():
    wizard = pd.DataFrame(
        [
            {
                "priority": 1,
                "ticker": "AMD",
                "unlock_goal": "Unlock DCF",
                "blocking_dataset": "fundamentals",
                "current_status": "shares_outstanding missing",
                "why_it_matters": "DCF needs shares and cash-flow inputs.",
                "recommended_action": "Stage candidate fundamentals before validating and previewing the import.",
                "focus_command": "",
                "example_command": "",
            }
        ]
    )

    cards = dashboard.data_coverage_wizard_cards(wizard)
    valuation_card = next(card for card in cards if card["kicker"] == "VALUATION")

    assert valuation_card["title"] == "1 blocker"
    assert valuation_card["command"] == "make focus-fundamentals TICKER=AMD"
    assert "make focus-fundamentals TICKER=AMD" in valuation_card["badges"]


def test_data_coverage_wizard_cards_use_review_fallback_when_row_copy_is_missing():
    wizard = pd.DataFrame(
        [
            {
                "priority": 1,
                "ticker": "TSLA",
                "unlock_goal": "Unlock Peer Relative",
                "blocking_dataset": "peers",
                "current_status": "",
                "why_it_matters": "",
                "recommended_action": "",
                "focus_command": "",
                "example_command": "",
            }
        ]
    )

    cards = dashboard.data_coverage_wizard_cards(wizard)
    peer_card = next(card for card in cards if card["kicker"] == "PEERS")

    assert peer_card["title"] == "1 blocker"
    assert peer_card["command"] == "make focus-peers TICKER=TSLA"
    assert "review peer path." in peer_card["body"].lower()
    assert "not available" not in peer_card["body"].lower()


def test_data_coverage_wizard_cards_use_staged_flow_fallback_when_row_copy_is_missing():
    wizard = pd.DataFrame(
        [
            {
                "priority": 1,
                "ticker": "NVDA",
                "unlock_goal": "Unlock DCF",
                "blocking_dataset": "fundamentals",
                "current_status": "",
                "why_it_matters": "",
                "recommended_action": "",
                "focus_command": "make imports-validate",
                "example_command": "",
            }
        ]
    )

    cards = dashboard.data_coverage_wizard_cards(wizard)
    valuation_card = next(card for card in cards if card["kicker"] == "VALUATION")

    assert valuation_card["title"] == "1 blocker"
    assert valuation_card["command"] == "make imports-validate"
    assert "staged local workflow next" in valuation_card["body"].lower()
    assert "not available" not in valuation_card["body"].lower()


def test_data_coverage_wizard_cards_use_runbook_fallback_when_row_copy_is_missing():
    wizard = pd.DataFrame(
        [
            {
                "priority": 1,
                "ticker": "TSLA",
                "unlock_goal": "Unlock Peer Relative",
                "blocking_dataset": "peers",
                "current_status": "",
                "why_it_matters": "",
                "recommended_action": "",
                "focus_command": "make runbook-peers",
                "example_command": "",
            }
        ]
    )

    cards = dashboard.data_coverage_wizard_cards(wizard)
    peer_card = next(card for card in cards if card["kicker"] == "PEERS")

    assert peer_card["title"] == "1 blocker"
    assert peer_card["command"] == "make runbook-peers"
    assert "staged local workflow next" in peer_card["body"].lower()
    assert "not available" not in peer_card["body"].lower()


def test_data_coverage_wizard_cards_keep_staged_follow_through_visible_when_target_files_are_present():
    wizard = pd.DataFrame(
        [
            {
                "priority": 1,
                "ticker": "NVDA",
                "unlock_goal": "Unlock DCF",
                "blocking_dataset": "fundamentals",
                "current_status": "",
                "why_it_matters": "",
                "recommended_action": "Use staged local imports if the free refresh fails.",
                "focus_command": "make imports-validate",
                "example_command": "",
                "target_file": "data/imports/fundamentals.csv",
            },
            {
                "priority": 1,
                "ticker": "TSLA",
                "unlock_goal": "Unlock Peer Relative",
                "blocking_dataset": "peers",
                "current_status": "",
                "why_it_matters": "",
                "recommended_action": "Use staged local imports if the free refresh fails.",
                "focus_command": "make imports-validate",
                "example_command": "",
                "target_file": "data/imports/peers.csv",
            },
            {
                "priority": 1,
                "ticker": "AMD",
                "unlock_goal": "Unlock Monthly Picks",
                "blocking_dataset": "prices",
                "current_status": "",
                "why_it_matters": "",
                "recommended_action": "Use staged local imports if the free refresh fails.",
                "focus_command": "make price-validate",
                "example_command": "",
                "target_file": "data/imports/prices.csv",
            },
        ]
    )

    cards = dashboard.data_coverage_wizard_cards(wizard)
    valuation_card = next(card for card in cards if card["kicker"] == "VALUATION")
    peer_card = next(card for card in cards if card["kicker"] == "PEERS")
    monthly_card = next(card for card in cards if card["kicker"] == "MONTHLY")

    assert valuation_card["command"] == "make imports-validate"
    assert "make imports-preview" in valuation_card["body"].lower()
    assert "make imports-apply" in valuation_card["body"].lower()
    assert peer_card["command"] == "make imports-validate"
    assert "make imports-preview" in peer_card["body"].lower()
    assert "make imports-apply" in peer_card["body"].lower()
    assert monthly_card["command"] == "make price-validate"
    assert "make price-preview" in monthly_card["body"].lower()
    assert "make price-apply" in monthly_card["body"].lower()
    assert "use staged local imports if the free refresh fails" not in " ".join(card["body"] for card in cards).lower()


def test_universe_preset_cards_include_preview_commands():
    cards = dashboard.universe_preset_cards()
    rendered = " ".join(str(value) for card in cards for value in card.values())

    assert cards
    assert "make universe-preview" in rendered
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
    assert "make universe-preview" in rendered
    assert "make universe-apply" in rendered
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
    assert cards[0]["command"] == "make universe-apply"
    assert cards[2]["command"] == "make universe-apply"
    assert "12 current rows" in rendered
    assert "apply stays cli-only" in rendered
    assert "make universe-preview" in rendered
    assert "make universe-apply" in rendered
    assert "buy" not in rendered
    assert "sell" not in rendered
    assert "buy" not in rendered
    assert "sell" not in rendered


def test_universe_manager_summary_cards_surface_make_preview_and_apply():
    cards = dashboard.universe_manager_summary_cards(
        {
            "row_count": 12,
            "duplicate_ticker_count": 1,
            "missing_theme_count": 2,
            "unclassified_theme_count": 1,
        },
        {"exists": True, "row_count": 4},
    )
    rendered = " ".join(str(value) for card in cards for value in card.values()).lower()

    assert len(cards) == 3
    assert cards[1]["command"] == "make universe-apply"
    assert cards[2]["command"] == "make universe-preview"
    assert "make universe-preview" in rendered
    assert "make universe-apply" in rendered
    assert "staged file present" in rendered


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
    assert any(row["Command"] == "make status-check TOP_N=5" for row in workflow_rows)
    assert any(row["Command"] == "make data-wizard TOP_N=5" for row in workflow_rows)
    assert any(row["Command"] == "make focus-price TICKER=NVDA" for row in workflow_rows)
    assert any(row["Command"] == "make focus-fundamentals TICKER=NVDA" for row in workflow_rows)
    assert any(row["Command"] == "make focus-peers TICKER=NVDA" for row in workflow_rows)
    assert any(row["Command"] == "make runbook-prices-broader" for row in workflow_rows)
    assert any(row["Command"] == "make verify" for row in workflow_rows)
    assert any(row["Command"] == "make validate-all" for row in workflow_rows)
    assert any(row["Command"] == "make dashboard-smoke" for row in workflow_rows)
    assert any(row["Command"] == "make daily" for row in workflow_rows)
    assert "verified ohlcv files before relying on momentum or track-record context" in rendered
    assert "make runbook-prices-broader" in rendered
    assert "overview tab" in nav_rendered
    assert "monthly picks tab" in nav_rendered
    assert "make status-check top_n=5" in rendered
    fundamentals_row = next(row for row in missing_rows if row["Dashboard Label"] == "Needs SEC enrichment")
    peers_row = next(row for row in missing_rows if row["Dashboard Label"] == "Needs peers.csv")
    assert "make status-check TOP_N=5" in fundamentals_row["What to do"]
    assert "make status-check TOP_N=5" in peers_row["What to do"]
    assert "make data-wizard top_n=5" in rendered
    assert "data health tab" in nav_rendered
    assert "make runbook-prices-broader" in empty_rendered
    assert "make runbook-fundamentals-broader" in empty_rendered
    assert "make runbook-peers-broader" in empty_rendered
    assert "make focus-price" in empty_rendered
    assert "run make templates, then fill data/imports/peers.csv" in empty_rendered
    assert "price-normalize" in empty_rendered
    assert "make focus-fundamentals" in empty_rendered
    assert "make imports-validate" in empty_rendered
    assert "make imports-preview" in empty_rendered
    assert "make imports-apply" in empty_rendered
    assert "make price-validate" in empty_rendered
    assert "make price-preview" in empty_rendered
    assert "make price-apply" in empty_rendered
    assert "make runbook-fundamentals-broader" in rendered
    assert "make runbook-peers-broader" in rendered
    assert "make imports-validate" in rendered
    assert "make imports-preview" in rendered
    assert "make imports-apply" in rendered
    assert "peers.csv" in empty_rendered
    assert "make imports-validate" in rendered
    assert "make imports-preview" in rendered
    assert "make imports-apply" in rendered
    assert "staged peer fundamentals or price blocker" in empty_rendered
    assert "staged peer fundamentals or peer price follow-through" in rendered


def test_priority_now_falls_back_to_status_first_ready_path():
    class ReadyCatalog:
        def load_dataframe(self, name: str):
            if name == "fundamentals":
                return pd.DataFrame(
                    [
                        {"ticker": "NVDA", "free_cash_flow": 10},
                        {"ticker": "MSFT", "free_cash_flow": 12},
                    ]
                )
            if name == "peers":
                return pd.DataFrame([{"ticker": "NVDA", "peer_ticker": "MSFT"}])
            return pd.DataFrame()

    payload = {"top_onboarding_actions": []}
    actions = dashboard.priority_now_fallback_actions(payload, missing_warning_count=0, catalog=ReadyCatalog())

    rendered = " ".join(str(item) for row in actions for item in row).lower()
    assert "workflow looks ready" in rendered
    assert "make status-check top_n=5" in rendered
    assert "dashboard-smoke" in rendered
    assert "place_order" not in rendered
    assert "submit_order" not in rendered
    assert "execute_trade" not in rendered


def test_priority_now_fallback_actions_use_wizard_and_peer_runbook_front_doors():
    class StubCatalog:
        def load_dataframe(self, name: str):
            if name == "fundamentals":
                return pd.DataFrame([{"ticker": "NVDA"}, {"ticker": "TSLA"}])
            if name == "peers":
                return pd.DataFrame()
            return pd.DataFrame()

    actions = dashboard.priority_now_fallback_actions(None, missing_warning_count=3, catalog=StubCatalog())
    rendered = " ".join(str(item) for row in actions for item in row).lower()

    assert any(row[0] == "Data gaps are visible" and row[2] == "make data-wizard TOP_N=10" for row in actions)
    assert any(row[0] == "Peer context needs local research" and row[2] == "make runbook-peers-broader" for row in actions)
    assert "make data-wizard top_n=10" in rendered
    assert "make runbook-peers-broader" in rendered
    assert "buy" not in rendered
    assert "sell" not in rendered


def test_normalize_operator_command_rewrites_legacy_price_and_universe_commands():
    assert (
        dashboard.normalize_operator_command("SEC_USER_AGENT='Name email@example.com' make sec-stage TICKERS=nvda, msft")
        == "make sec-stage TICKERS=NVDA,MSFT"
    )
    assert (
        dashboard.normalize_operator_command("python3 -m src.data_update --tickers amd, nvda")
        == "make price-refresh TICKERS=AMD,NVDA"
    )
    assert (
        dashboard.normalize_operator_command("python3 -m src.universe_builder --apply-import")
        == "make universe-apply"
    )
    assert (
        dashboard.normalize_operator_command("python3 -m src.universe_builder --preview --preset sp500_smh --max-tickers 50")
        == "make universe-preview"
    )
    assert (
        dashboard.normalize_operator_command("python3 -m src.universe_builder --preview --sources sp500,nasdaq,smh,holdings --max-tickers 100")
        == "make universe-preview"
    )
    assert (
        dashboard.normalize_operator_command("python3 -m src.universe_builder --write-import --preset sp500_smh --max-tickers 50")
        == "make universe-apply"
    )


def test_preferred_row_command_rewrites_legacy_price_refresh_example_command():
    row = {
        "focus_command": "",
        "example_command": "python3 -m src.data_update --tickers amd, nvda",
    }

    assert dashboard.preferred_row_command(row) == "make price-refresh TICKERS=AMD,NVDA"


def test_preferred_bundle_command_rewrites_legacy_sec_user_agent_command():
    row = {
        "bundle_shortcut_command": "",
        "primary_command": "SEC_USER_AGENT='Name email@example.com' make sec-stage TICKERS=nvda, msft",
    }

    assert dashboard.preferred_bundle_command(row) == "make sec-stage TICKERS=NVDA,MSFT"


def test_preferred_bundle_command_falls_back_to_runbook_and_detail_shortcuts():
    runbook_only = {
        "runbook_shortcut_command": "make runbook-prices",
    }
    detail_only = {
        "detail_shortcut_command": "make detail-prices",
    }

    assert dashboard.preferred_bundle_command(runbook_only) == "make runbook-prices"
    assert dashboard.preferred_bundle_command(detail_only) == "make detail-prices"


def test_preferred_bundle_command_falls_back_to_lane_runbooks_when_bundle_commands_are_missing():
    assert dashboard.preferred_bundle_command({"lane": "prices"}) == "make runbook-prices-broader"
    assert dashboard.preferred_bundle_command({"lane": "fundamentals"}) == "make runbook-fundamentals-broader"
    assert dashboard.preferred_bundle_command({"lane": "peers"}) == "make runbook-peers-broader"


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


def test_price_refresh_fallback_message_uses_runbook_and_normalize_flow():
    plain = dashboard.price_refresh_fallback_message()
    warned = dashboard.price_refresh_fallback_message(include_remote_failure_prefix=True)

    assert "make runbook-prices-broader" in plain
    assert "make focus-price" in plain
    assert "make price-normalize" in plain
    assert "make price-validate" in plain
    assert warned.startswith("Remote price refresh had source issues.")


def test_price_refresh_cli_note_message_uses_runbook_and_normalize_flow():
    note = dashboard.price_refresh_cli_note_message()

    assert note.startswith("CLI-only:")
    assert "make runbook-prices-broader" in note
    assert "make focus-price" in note
    assert "make price-normalize" in note


def test_data_gap_report_notice_uses_data_sources_front_door():
    body, command = dashboard.data_gap_report_notice(None)

    assert "local gap report has not been generated yet" in body.lower()
    assert command == "make data-sources"


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


def test_overview_command_bundle_cards_use_bundle_native_shortcuts_when_primary_is_missing():
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
                "bundle_shortcut_command": "",
                "detail_shortcut_command": "",
                "runbook_shortcut_command": "make runbook-prices",
                "primary_command": "",
            }
        ]
    )

    cards = dashboard.overview_command_bundle_cards(bundles)

    assert cards[0]["command"] == "make runbook-prices"


def test_overview_command_bundle_cards_use_review_fallback_when_summaries_are_missing():
    bundles = pd.DataFrame(
        [
            {
                "bundle_name": "Peer Mapping Bundle",
                "lane": "peers",
                "scope": "holdings_first",
                "ticker_count": 1,
                "tickers": "TSLA",
                "goal_summary": "",
                "why_it_matters": "",
                "bundle_shortcut_command": "",
                "detail_shortcut_command": "",
                "runbook_shortcut_command": "make runbook-peers",
                "primary_command": "",
            }
        ]
    )

    cards = dashboard.overview_command_bundle_cards(bundles)

    assert cards[0]["command"] == "make runbook-peers"
    assert "staged local workflow next" in cards[0]["body"].lower()
    assert "not available" not in cards[0]["body"].lower()


def test_overview_command_bundle_cards_use_staged_follow_through_when_summaries_are_missing():
    bundles = pd.DataFrame(
        [
            {
                "bundle_name": "SEC Fundamentals Bundle",
                "lane": "fundamentals",
                "scope": "holdings_first",
                "ticker_count": 3,
                "tickers": "META,NVDA,TSLA",
                "goal_summary": "",
                "why_it_matters": "",
                "bundle_shortcut_command": "",
                "detail_shortcut_command": "",
                "runbook_shortcut_command": "make runbook-fundamentals",
                "primary_command": "",
                "target_file": "data/imports/fundamentals.csv",
                "safe_next_step": "Keep SEC enrichment staged and review-only until make imports-validate, make imports-preview, and make imports-apply confirm the merge.",
            }
        ]
    )

    cards = dashboard.overview_command_bundle_cards(bundles)

    assert cards[0]["command"] == "make runbook-fundamentals"
    assert "make imports-preview" in cards[0]["body"].lower()
    assert "make imports-apply" in cards[0]["body"].lower()
    assert "not available" not in cards[0]["body"].lower()


def test_overview_command_bundle_cards_use_price_staged_follow_through_when_summaries_are_missing():
    bundles = pd.DataFrame(
        [
            {
                "bundle_name": "Price Coverage Bundle",
                "lane": "prices",
                "scope": "holdings_first",
                "ticker_count": 2,
                "tickers": "AMD,AVGO",
                "goal_summary": "",
                "why_it_matters": "",
                "bundle_shortcut_command": "",
                "detail_shortcut_command": "",
                "runbook_shortcut_command": "make runbook-prices",
                "primary_command": "",
                "target_file": "data/imports/prices.csv",
                "safe_next_step": "",
            }
        ]
    )

    cards = dashboard.overview_command_bundle_cards(bundles)

    assert cards[0]["command"] == "make runbook-prices"
    assert "make price-validate" in cards[0]["body"].lower()
    assert "make price-preview" in cards[0]["body"].lower()
    assert "make price-apply" in cards[0]["body"].lower()
    assert "not available" not in cards[0]["body"].lower()


def test_overview_command_bundle_cards_upgrade_generic_price_staged_note_to_explicit_follow_through():
    bundles = pd.DataFrame(
        [
            {
                "bundle_name": "Price Coverage Bundle",
                "lane": "prices",
                "scope": "holdings_first",
                "ticker_count": 2,
                "tickers": "AMD,AVGO",
                "goal_summary": "",
                "why_it_matters": "",
                "bundle_shortcut_command": "",
                "detail_shortcut_command": "",
                "runbook_shortcut_command": "make runbook-prices",
                "primary_command": "",
                "target_file": "data/imports/prices.csv",
                "safe_next_step": "Use staged local imports if the free refresh fails.",
            }
        ]
    )

    cards = dashboard.overview_command_bundle_cards(bundles)

    assert cards[0]["command"] == "make runbook-prices"
    assert "make price-validate" in cards[0]["body"].lower()
    assert "make price-preview" in cards[0]["body"].lower()
    assert "make price-apply" in cards[0]["body"].lower()


def test_bundle_cards_and_handoff_use_lane_runbooks_when_bundle_commands_are_missing():
    bundles = pd.DataFrame(
        [
            {
                "bundle_name": "Peer Mapping Bundle",
                "lane": "peers",
                "scope": "holdings_first",
                "ticker_count": 3,
                "tickers": "META,NVDA,TSLA",
                "goal_summary": "Advance transparent peer-relative readiness for the listed tickers",
                "bundle_shortcut_command": "",
                "detail_shortcut_command": "",
                "runbook_shortcut_command": "",
                "primary_command": "",
                "follow_up_command": "",
            }
        ]
    )

    bundle_cards = dashboard.overview_command_bundle_cards(bundles)
    handoff_cards = dashboard.overview_bundle_handoff_cards(bundles, None, None)

    assert bundle_cards[0]["command"] == "make runbook-peers-broader"
    assert handoff_cards[0]["command"] == "make runbook-peers-broader"


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

    assert bundle_cards[0]["command"] == "make onboarding"
    assert handoff_cards[0]["command"] == "make onboarding"
    assert runbook_cards[0]["command"] == "make onboarding"
    assert "run make onboarding" in rendered
    assert "buy" not in rendered
    assert "sell" not in rendered


def test_bundle_runbook_cards_use_first_usable_step_command_when_lead_row_is_blank():
    runbook = pd.DataFrame(
        [
            {
                "bundle_name": "Peer Mapping Bundle",
                "lane": "peers",
                "scope": "holdings_first",
                "step_order": 1,
                "step_label": "Explain lane",
                "command": "",
                "tickers": "NVDA",
                "goal_summary": "Advance transparent peer-relative readiness for the listed tickers",
            },
            {
                "bundle_name": "Peer Mapping Bundle",
                "lane": "peers",
                "scope": "holdings_first",
                "step_order": 2,
                "step_label": "Run bundle command",
                "command": "make templates",
                "tickers": "NVDA",
                "goal_summary": "Advance transparent peer-relative readiness for the listed tickers",
            },
        ]
    )

    data_health_cards = dashboard.data_health_command_bundle_runbook_cards(runbook)
    overview_cards = dashboard.overview_bundle_runbook_cards(runbook)

    assert data_health_cards[0]["command"] == "make templates"
    assert overview_cards[0]["command"] == "make templates"


def test_bundle_runbook_cards_use_first_usable_step_command_for_fallback_copy():
    runbook = pd.DataFrame(
        [
            {
                "bundle_name": "Peer Mapping Bundle",
                "lane": "peers",
                "scope": "holdings_first",
                "step_order": 1,
                "step_label": "Explain lane",
                "command": "",
                "tickers": "NVDA",
                "goal_summary": "",
                "why_it_matters": "",
            },
            {
                "bundle_name": "Peer Mapping Bundle",
                "lane": "peers",
                "scope": "holdings_first",
                "step_order": 2,
                "step_label": "Open peer runbook",
                "command": "make runbook-peers",
                "tickers": "NVDA",
                "goal_summary": "",
                "why_it_matters": "",
            },
        ]
    )

    data_health_cards = dashboard.data_health_command_bundle_runbook_cards(runbook)
    overview_cards = dashboard.overview_bundle_runbook_cards(runbook)

    assert data_health_cards[0]["command"] == "make runbook-peers"
    assert "staged local workflow next" in data_health_cards[0]["body"].lower()
    assert overview_cards[0]["command"] == "make runbook-peers"
    assert "staged local workflow next" in overview_cards[0]["body"].lower()
    assert "not available" not in " ".join(str(value) for card in data_health_cards + overview_cards for value in card.values()).lower()


def test_bundle_runbook_cards_normalize_top_level_command_from_first_usable_step():
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
            }
        ]
    )

    data_health_cards = dashboard.data_health_command_bundle_runbook_cards(runbook)
    overview_cards = dashboard.overview_bundle_runbook_cards(runbook)

    assert data_health_cards[0]["command"] == "make price-refresh TICKERS=META"
    assert overview_cards[0]["command"] == "make price-refresh TICKERS=META"


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
    assert "make status-check top_n=5" not in rendered
    assert "start by 2025-12-01" in rendered
    assert "make price-normalize input=data/raw/prices/meta.csv ticker=meta source=yahoo_manual" in rendered
    assert "make sec-stage tickers=nvda" in rendered
    assert "buy" not in rendered
    assert "sell" not in rendered


def test_overview_bundle_runbook_cards_use_staged_follow_through_when_goal_summary_is_missing():
    runbook = pd.DataFrame(
        [
            {
                "bundle_name": "SEC Fundamentals Bundle",
                "lane": "fundamentals",
                "scope": "holdings_first",
                "step_order": 1,
                "step_label": "Review staged import",
                "command": "make imports-validate",
                "tickers": "META,NVDA,TSLA",
                "goal_summary": "",
                "target_file": "data/imports/fundamentals.csv",
                "safe_next_step": "Keep SEC enrichment staged and review-only until make imports-validate, make imports-preview, and make imports-apply confirm the merge.",
            }
        ]
    )

    cards = dashboard.overview_bundle_runbook_cards(runbook)

    assert cards[0]["command"] == "make imports-validate"
    assert "make imports-preview" in cards[0]["body"].lower()
    assert "make imports-apply" in cards[0]["body"].lower()
    assert "review staged import" in cards[0]["body"].lower()


def test_overview_bundle_runbook_cards_use_price_staged_follow_through_when_goal_summary_is_missing():
    runbook = pd.DataFrame(
        [
            {
                "bundle_name": "Price Coverage Bundle",
                "lane": "prices",
                "scope": "holdings_first",
                "step_order": 1,
                "step_label": "Review staged import",
                "command": "make price-validate",
                "tickers": "AMD,AVGO",
                "goal_summary": "",
                "target_file": "data/imports/prices.csv",
                "safe_next_step": "",
            }
        ]
    )

    cards = dashboard.overview_bundle_runbook_cards(runbook)

    assert cards[0]["command"] == "make price-validate"
    assert "make price-preview" in cards[0]["body"].lower()
    assert "make price-apply" in cards[0]["body"].lower()
    assert "review staged import" in cards[0]["body"].lower()


def test_overview_bundle_runbook_cards_upgrade_generic_price_staged_note_to_explicit_follow_through():
    runbook = pd.DataFrame(
        [
            {
                "bundle_name": "Price Coverage Bundle",
                "lane": "prices",
                "scope": "holdings_first",
                "step_order": 1,
                "step_label": "Review staged import",
                "command": "make price-validate",
                "tickers": "AMD,AVGO",
                "goal_summary": "",
                "target_file": "data/imports/prices.csv",
                "safe_next_step": "Use staged local imports if the free refresh fails.",
            }
        ]
    )

    cards = dashboard.overview_bundle_runbook_cards(runbook)

    assert cards[0]["command"] == "make price-validate"
    assert "make price-preview" in cards[0]["body"].lower()
    assert "make price-apply" in cards[0]["body"].lower()
    assert "use staged local imports if the free refresh fails" not in cards[0]["body"].lower()


def test_overview_bundle_runbook_cards_use_staged_command_when_steps_are_blank():
    runbook = pd.DataFrame(
        [
            {
                "bundle_name": "SEC Fundamentals Bundle",
                "lane": "fundamentals",
                "scope": "holdings_first",
                "step_order": 1,
                "step_label": "Review staged import",
                "command": "",
                "tickers": "META,NVDA,TSLA",
                "goal_summary": "",
                "target_file": "data/imports/fundamentals.csv",
                "safe_next_step": "Keep SEC enrichment staged and review-only until make imports-validate, make imports-preview, and make imports-apply confirm the merge.",
            }
        ]
    )

    cards = dashboard.overview_bundle_runbook_cards(runbook)

    assert cards[0]["command"] == "make imports-validate"
    assert "review staged import: make imports-validate" in cards[0]["body"].lower()
    assert "make imports-preview" in cards[0]["body"].lower()


def test_overview_bundle_runbook_cards_use_price_staged_command_when_steps_are_blank():
    runbook = pd.DataFrame(
        [
            {
                "bundle_name": "Price Coverage Bundle",
                "lane": "prices",
                "scope": "holdings_first",
                "step_order": 1,
                "step_label": "Review staged import",
                "command": "",
                "tickers": "AMD,AVGO",
                "goal_summary": "",
                "target_file": "data/imports/prices.csv",
                "safe_next_step": "",
            }
        ]
    )

    cards = dashboard.overview_bundle_runbook_cards(runbook)

    assert cards[0]["command"] == "make price-validate"
    assert "review staged import: make price-validate" in cards[0]["body"].lower()
    assert "make price-preview" in cards[0]["body"].lower()
    assert "make price-apply" in cards[0]["body"].lower()


def test_overview_bundle_runbook_cards_use_why_it_matters_when_goal_summary_is_missing():
    runbook = pd.DataFrame(
        [
            {
                "bundle_name": "Peer Mapping Bundle",
                "lane": "peers",
                "scope": "holdings_first",
                "step_order": 1,
                "step_label": "Fill peer mappings manually",
                "command": "data/imports/peers.csv",
                "tickers": "META,NVDA,TSLA",
                "goal_summary": "",
                "why_it_matters": "These tickers are closest to peer-relative coverage once manually researched mappings are added locally.",
            }
        ]
    )

    cards = dashboard.overview_bundle_runbook_cards(runbook)

    assert "closest to peer-relative coverage" in cards[0]["body"].lower()
    assert "fill peer mappings manually: data/imports/peers.csv" in cards[0]["body"].lower()


def test_overview_bundle_runbook_cards_use_runbook_fallback_when_summaries_are_missing():
    runbook = pd.DataFrame(
        [
            {
                "bundle_name": "Peer Mapping Bundle",
                "lane": "peers",
                "scope": "holdings_first",
                "step_order": 1,
                "step_label": "Open peer runbook",
                "command": "make runbook-peers",
                "tickers": "TSLA",
                "goal_summary": "",
                "why_it_matters": "",
            }
        ]
    )

    cards = dashboard.overview_bundle_runbook_cards(runbook)

    assert cards[0]["command"] == "make runbook-peers"
    assert "staged local workflow next" in cards[0]["body"].lower()
    assert "not available" not in cards[0]["body"].lower()


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
                "follow_up_command": "make imports-validate",
                "target_file": "data/imports/fundamentals.csv",
                "why_it_matters": "These tickers are the best next candidates for explicit local DCF inputs.",
                "safe_next_step": "Keep SEC enrichment staged and review-only until make imports-validate, make imports-preview, and make imports-apply confirm the merge.",
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
                "safe_next_step": "Keep SEC enrichment staged and review-only until make imports-validate, make imports-preview, and make imports-apply confirm the merge.",
            },
            {
                "bundle_name": "SEC Fundamentals Bundle",
                "lane": "fundamentals",
                "scope": "holdings_first",
                "step_order": 2,
                "step_label": "Review follow-up output",
                "command": "make imports-validate",
                "tickers": "META,NVDA,TSLA",
                "goal_summary": "Advance explicit local DCF readiness for the listed tickers",
                "target_file": "data/imports/fundamentals.csv",
                "why_it_matters": "These tickers are the best next candidates for explicit local DCF inputs.",
                "safe_next_step": "Keep SEC enrichment staged and review-only until make imports-validate, make imports-preview, and make imports-apply confirm the merge.",
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
    assert "make imports-validate" in rendered
    assert "make imports-preview" in rendered
    assert "make imports-apply" in rendered
    assert "make status-check top_n=5" in rendered
    assert "meta" in rendered
    assert "buy" not in rendered
    assert "sell" not in rendered


def test_overview_bundle_handoff_cards_normalize_explicit_follow_through_command():
    bundles = pd.DataFrame(
        [
            {
                "bundle_name": "Price Coverage Bundle",
                "lane": "prices",
                "scope": "holdings_first",
                "ticker_count": 3,
                "tickers": "META,NVDA,TSLA",
                "goal_summary": "Unlock Monthly Picks for 2 tickers; 57 verified rows still needed across this bundle",
                "primary_command": "make bundle-prices",
                "follow_up_command": "python3 -m src.data_update --tickers META,NVDA,TSLA",
            }
        ]
    )

    cards = dashboard.overview_bundle_handoff_cards(bundles, None, None)

    assert cards[1]["title"] == "make price-refresh TICKERS=META,NVDA,TSLA"
    assert cards[1]["command"] == "make price-refresh TICKERS=META,NVDA,TSLA"


def test_overview_bundle_handoff_cards_use_runbook_follow_through_when_bundle_field_is_missing():
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
                "follow_up_command": "",
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
            },
            {
                "bundle_name": "SEC Fundamentals Bundle",
                "lane": "fundamentals",
                "scope": "holdings_first",
                "step_order": 2,
                "step_label": "Review follow-up output",
                "command": "make imports-validate",
            },
        ]
    )

    cards = dashboard.overview_bundle_handoff_cards(bundles, None, runbook)

    assert cards[1]["title"] == "make imports-validate"
    assert cards[1]["command"] == "make imports-validate"


def test_overview_bundle_handoff_cards_use_staged_follow_through_when_bundle_row_is_sparse():
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
                "follow_up_command": "",
                "target_file": "data/imports/fundamentals.csv",
                "safe_next_step": "Keep SEC enrichment staged and review-only until make imports-validate, make imports-preview, and make imports-apply confirm the merge.",
            }
        ]
    )

    cards = dashboard.overview_bundle_handoff_cards(bundles, None, None)
    rendered = " ".join(str(value) for card in cards for value in card.values()).lower()

    assert cards[1]["title"] == "make imports-validate"
    assert cards[1]["command"] == "make imports-validate"
    assert "make imports-preview" in rendered
    assert "make imports-apply" in rendered


def test_overview_bundle_handoff_cards_use_staged_summary_when_goal_summary_is_missing():
    bundles = pd.DataFrame(
        [
            {
                "bundle_name": "SEC Fundamentals Bundle",
                "lane": "fundamentals",
                "scope": "holdings_first",
                "ticker_count": 3,
                "tickers": "META,NVDA,TSLA",
                "goal_summary": "",
                "why_it_matters": "",
                "primary_command": "SEC_USER_AGENT='Name email@example.com' make sec-stage TICKERS=META,NVDA,TSLA",
                "follow_up_command": "",
                "target_file": "data/imports/fundamentals.csv",
                "safe_next_step": "Keep SEC enrichment staged and review-only until make imports-validate, make imports-preview, and make imports-apply confirm the merge.",
            }
        ]
    )

    cards = dashboard.overview_bundle_handoff_cards(bundles, None, None)

    assert cards[0]["command"] == "make sec-stage TICKERS=META,NVDA,TSLA"
    assert "make imports-preview" in cards[0]["body"].lower()
    assert "make imports-apply" in cards[0]["body"].lower()
    assert "start with make sec-stage tickers=meta,nvda,tsla" in cards[0]["body"].lower()
    assert cards[1]["command"] == "make imports-validate"


def test_overview_bundle_handoff_cards_use_runbook_fallback_when_summaries_are_missing():
    bundles = pd.DataFrame(
        [
            {
                "bundle_name": "Peer Mapping Bundle",
                "lane": "peers",
                "scope": "holdings_first",
                "ticker_count": 1,
                "tickers": "TSLA",
                "goal_summary": "",
                "why_it_matters": "",
                "bundle_shortcut_command": "",
                "detail_shortcut_command": "",
                "runbook_shortcut_command": "make runbook-peers",
                "primary_command": "",
                "follow_up_command": "",
            }
        ]
    )

    cards = dashboard.overview_bundle_handoff_cards(bundles, None, None)

    assert cards[0]["command"] == "make runbook-peers"
    assert "staged local workflow next" in cards[0]["body"].lower()
    assert "not available" not in cards[0]["body"].lower()


def test_overview_bundle_handoff_cards_normalize_refresh_command_from_runbook():
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
                "follow_up_command": "make imports-validate",
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
            },
            {
                "bundle_name": "SEC Fundamentals Bundle",
                "lane": "fundamentals",
                "scope": "holdings_first",
                "step_order": 2,
                "step_label": "Refresh status outputs",
                "command": "make status",
            },
        ]
    )

    cards = dashboard.overview_bundle_handoff_cards(bundles, None, runbook)

    assert cards[2]["title"] == "Refresh status outputs"
    assert cards[2]["command"] == "make status-check TOP_N=5"


def test_overview_bundle_handoff_cards_use_monthly_front_door_for_price_bundle_refresh():
    bundles = pd.DataFrame(
        [
            {
                "bundle_name": "Price Coverage Bundle",
                "lane": "prices",
                "scope": "holdings_first",
                "ticker_count": 3,
                "tickers": "META,NVDA,TSLA",
                "goal_summary": "Unlock Monthly Picks for 2 tickers; 57 verified rows still needed across this bundle",
                "primary_command": "make bundle-prices",
                "follow_up_command": "make price-status",
                "target_file": "data/imports/prices.csv",
                "why_it_matters": "These tickers still block broader local research because price history is missing or too short.",
                "safe_next_step": "Use staged local imports if the free refresh fails.",
            }
        ]
    )
    details = pd.DataFrame(
        [
            {
                "bundle_name": "Price Coverage Bundle",
                "lane": "prices",
                "ticker": "META",
                "is_holding": True,
                "theme": "AI Platforms",
                "sector_etf": "QQQ",
                "current_unlock_stage": "prices",
            }
        ]
    )
    runbook = pd.DataFrame(
        [
            {
                "bundle_name": "Price Coverage Bundle",
                "lane": "prices",
                "scope": "holdings_first",
                "step_order": 1,
                "step_label": "Run bundle command",
                "command": "make bundle-prices",
                "tickers": "META,NVDA,TSLA",
                "goal_summary": "Unlock Monthly Picks for 2 tickers; 57 verified rows still needed across this bundle",
                "target_file": "data/imports/prices.csv",
            },
            {
                "bundle_name": "Price Coverage Bundle",
                "lane": "prices",
                "scope": "holdings_first",
                "step_order": 2,
                "step_label": "Review follow-up output",
                "command": "make price-status",
                "tickers": "META,NVDA,TSLA",
                "goal_summary": "Unlock Monthly Picks for 2 tickers; 57 verified rows still needed across this bundle",
                "target_file": "data/imports/prices.csv",
            },
            {
                "bundle_name": "Price Coverage Bundle",
                "lane": "prices",
                "scope": "holdings_first",
                "step_order": 3,
                "step_label": "Refresh status outputs",
                "command": "make status",
                "tickers": "META,NVDA,TSLA",
                "goal_summary": "Unlock Monthly Picks for 2 tickers; 57 verified rows still needed across this bundle",
                "target_file": "data/imports/prices.csv",
            },
        ]
    )

    cards = dashboard.overview_bundle_handoff_cards(bundles, details, runbook)
    rendered = " ".join(str(value) for card in cards for value in card.values()).lower()

    assert cards[2]["title"] == "Refresh monthly context"
    assert cards[2]["command"] == "make monthly"
    assert "make price-validate" in rendered
    assert "make price-preview" in rendered
    assert "make price-apply" in rendered
    assert "make monthly" in rendered
    assert "buy" not in rendered
    assert "sell" not in rendered


def test_overview_bundle_handoff_cards_use_monthly_front_door_when_goal_summary_is_missing():
    bundles = pd.DataFrame(
        [
            {
                "bundle_name": "Price Coverage Bundle",
                "lane": "prices",
                "scope": "holdings_first",
                "ticker_count": 3,
                "tickers": "META,NVDA,TSLA",
                "goal_summary": "",
                "primary_command": "make bundle-prices",
                "follow_up_command": "make price-status",
                "target_file": "data/imports/prices.csv",
                "why_it_matters": "These tickers still block Monthly Picks because price history is missing or too short.",
                "safe_next_step": "Use staged local imports if the free refresh fails.",
            }
        ]
    )
    details = pd.DataFrame(
        [
            {
                "bundle_name": "Price Coverage Bundle",
                "lane": "prices",
                "ticker": "META",
                "is_holding": True,
                "theme": "AI Platforms",
                "sector_etf": "QQQ",
                "current_unlock_stage": "prices",
            }
        ]
    )
    runbook = pd.DataFrame(
        [
            {
                "bundle_name": "Price Coverage Bundle",
                "lane": "prices",
                "scope": "holdings_first",
                "step_order": 1,
                "step_label": "Run bundle command",
                "command": "make bundle-prices",
                "tickers": "META,NVDA,TSLA",
                "goal_summary": "",
                "target_file": "data/imports/prices.csv",
            },
            {
                "bundle_name": "Price Coverage Bundle",
                "lane": "prices",
                "scope": "holdings_first",
                "step_order": 2,
                "step_label": "Review follow-up output",
                "command": "make price-status",
                "tickers": "META,NVDA,TSLA",
                "goal_summary": "",
                "target_file": "data/imports/prices.csv",
            },
            {
                "bundle_name": "Price Coverage Bundle",
                "lane": "prices",
                "scope": "holdings_first",
                "step_order": 3,
                "step_label": "Refresh status outputs",
                "command": "make status",
                "tickers": "META,NVDA,TSLA",
                "goal_summary": "",
                "target_file": "data/imports/prices.csv",
            },
        ]
    )

    cards = dashboard.overview_bundle_handoff_cards(bundles, details, runbook)
    rendered = " ".join(str(value) for card in cards for value in card.values()).lower()

    assert cards[2]["title"] == "Refresh monthly context"
    assert cards[2]["command"] == "make monthly"
    assert "make price-validate" in rendered
    assert "make price-preview" in rendered
    assert "make price-apply" in rendered
    assert "make monthly" in rendered


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
                "safe_next_step": "Fill only manually researched peers for the listed tickers, then run make imports-validate, make imports-preview, and make imports-apply before make status refreshes readiness and action outputs.",
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
                "safe_next_step": "Fill only manually researched peers for the listed tickers, then run make imports-validate, make imports-preview, and make imports-apply before make status refreshes readiness and action outputs.",
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
                "safe_next_step": "Fill only manually researched peers for the listed tickers, then run make imports-validate, make imports-preview, and make imports-apply before make status refreshes readiness and action outputs.",
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
    assert cards[2]["command"] == "make status-check TOP_N=5"
    assert "make templates" in rendered
    assert "data/imports/peers.csv" in rendered
    assert "make imports-validate" in rendered
    assert "make imports-preview" in rendered
    assert "make imports-apply" in rendered
    assert "make status-check top_n=5" in rendered
    assert "buy" not in rendered
    assert "sell" not in rendered
