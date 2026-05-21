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
            "GeneratedAt": ["2026-05-21T00:00:00Z"],
        }
    )

    reordered = dashboard.reorder_columns(frame)

    assert list(reordered.columns[:5]) == [
        "Ticker",
        "PrimaryPurpose",
        "CompositeScore",
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
    assert tables["price_import_worklist.csv"][0] is None
    assert "has not been generated" in tables["price_import_worklist.csv"][1]
    assert dashboard.summarize_ticker_coverage(None)["usable_price_tickers"] == 0
    assert dashboard.summarize_price_worklist(None)["priority_1"] == 0


def test_summarize_price_worklist_counts_readiness_levels():
    worklist = pd.DataFrame(
        {
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
    assert actions[0][3] == "danger"
    assert commands[0]["Command"] == "make onboarding"


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
    assert "make onboarding" in rendered
    assert "buy" not in rendered
    assert "sell" not in rendered


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
                "example_command": "make sec-stage TICKERS=MSFT",
            },
            {
                "priority": 1,
                "dataset": "prices",
                "ticker": "NVDA",
                "reason": "Short local price history.",
                "recommended_action": "Normalize verified downloaded OHLCV rows.",
                "example_command": "make price-normalize INPUT=data/raw/prices/NVDA.csv TICKER=NVDA SOURCE=yahoo_manual",
            },
        ]
    )

    cards = dashboard.data_health_fix_first_cards(actions)
    rendered = " ".join(str(value) for card in cards for value in card).lower()

    assert cards[0][0] == "P1 prices - NVDA"
    assert cards[0][3] == "danger"
    assert "price-normalize" in rendered
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
                "why_it_matters": "Monthly ranking needs verified local price history.",
                "example_command": "python3 -m src.data_update --tickers NVDA",
            },
            {
                "priority": 2,
                "ticker": "NVDA",
                "unlock_goal": "Unlock DCF",
                "blocking_dataset": "fundamentals",
                "why_it_matters": "DCF needs cash-flow inputs.",
                "example_command": "python3 -m src.stock_report --sec-stage-fundamentals --tickers NVDA",
            },
        ]
    )

    cards = dashboard.data_coverage_wizard_cards(wizard)
    rendered = " ".join(str(value) for card in cards for value in card.values()).lower()

    assert "monthly" in rendered
    assert "valuation" in rendered
    assert "not blocking" in rendered
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
    assert any(row["Command"] == "make verify" for row in workflow_rows)
    assert any(row["Command"] == "make validate-all" for row in workflow_rows)
    assert any(row["Command"] == "make dashboard-smoke" for row in workflow_rows)
    assert any(row["Command"] == "make daily" for row in workflow_rows)
    assert "overview tab" in nav_rendered
    assert "monthly picks tab" in nav_rendered
    assert "data health tab" in nav_rendered
    assert "price-normalize" in empty_rendered
    assert "sec-stage" in empty_rendered
    assert "peers.csv" in empty_rendered
    assert "place_order" not in rendered
    assert "submit_order" not in rendered
    assert "execute_trade" not in rendered
    assert "buy" not in nav_rendered
    assert "sell" not in nav_rendered


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
