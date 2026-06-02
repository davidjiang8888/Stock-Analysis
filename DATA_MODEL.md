# Data Model

## Canonical Schemas

### Master Market Universe

File: `data/universe_master.csv`

Columns:

`ticker,name,exchange,asset_type,security_type,sector,industry,country,currency,is_active_listing,source,source_updated_at,created_at,updated_at`

### Active Research Universe

File: `data/universe_active.csv`

Columns:

`ticker,scope,priority,theme,research_status,user_notes,added_at,updated_at`

Compatibility file: `data/universe.csv` remains supported for existing pipeline code.

### Prices

File: `data/prices.csv`

Columns:

`ticker,date,open,high,low,close,adj_close,volume,source,updated_at`

### Fundamentals

File: `data/fundamentals.csv`

Columns:

`ticker,period,period_end,revenue,net_income,free_cash_flow,fcf_margin,shares_outstanding,total_debt,cash_and_equivalents,source,updated_at`

### Peers

File: `data/peers.csv`

Columns:

`ticker,peer_ticker,peer_group,theme,relationship_type,source,updated_at`

### Earnings

File: `data/earnings.csv`

Columns:

`ticker,fiscal_period,report_date,eps_actual,eps_estimate,revenue_actual,revenue_estimate,source,updated_at`

### Analyst Estimates

File: `data/analyst_estimates.csv`

Columns:

`ticker,period,eps_estimate,revenue_estimate,price_target_mean,price_target_high,price_target_low,rating_consensus,source,updated_at`

### Readiness Outputs

Primary file: `data/reports/ticker_readiness_report.csv`

Columns:

`ticker,name,exchange,asset_type,sector,industry,theme,in_master_universe,in_active_universe,price_ready,momentum_ready,market_direction_ready,liquidity_ready,correlation_ready,fundamentals_ready,dcf_ready,peer_ready,earnings_ready,analyst_estimates_ready,portfolio_ready,overall_readiness_state,ready_features,partial_features,blocked_features,excluded_features,missing_data,next_action,updated_at`

### Decision Outputs

Primary file: `data/outputs/research_decisions.csv`

Compatibility copy: `outputs/research_decisions.csv`

Columns:

`ticker,name,asset_type,exchange,sector,industry,theme,decision_bucket,confidence,main_reason,supporting_features,blocked_features,excluded_features,missing_data,next_action,data_readiness_score,analysis_score,decision_score,updated_at`

### Rejected Import Rows

Folder: `data/rejected/`

Common columns:

`source_file,source_row,ticker,rejection_reason`

Dataset-specific rejected files may include contextual fields such as `date`, `close`, or `source`.

### Data Source Status

File: `data/reports/data_source_status.csv`

Columns:

`source_name,source_type,status,credential_required,credential_present,last_attempted_at,last_success_at,rows_available,failure_reason,manual_fallback_available,manual_import_path,updated_at`
