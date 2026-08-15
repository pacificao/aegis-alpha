"""Fail-closed Phase 1 Robinhood MCP policy."""
READ_ONLY_TOOLS = frozenset({
    "get_accounts", "get_portfolio", "get_realized_pnl", "get_pnl_trade_history", "search",
    "get_watchlists", "get_watchlist_items", "get_option_watchlist", "get_popular_watchlists",
    "get_equity_historicals", "get_equity_fundamentals", "get_financials", "get_equity_price_book",
    "get_equity_technical_indicators", "get_earnings_results", "get_earnings_calendar", "get_indexes",
    "get_index_quotes", "get_equity_positions", "get_equity_tax_lots", "get_equity_quotes",
    "get_equity_orders", "get_equity_tradability", "get_option_historicals", "get_option_chains",
    "get_option_instruments", "get_option_quotes", "get_option_positions", "get_option_orders",
    "get_scans", "get_scanner_filter_specs", "run_scan",
})
MUTATION_PREFIXES = ("place_", "cancel_", "create_", "update_", "add_", "remove_", "follow_", "unfollow_", "review_")


def is_tool_allowed(name: str) -> bool:
    return name in READ_ONLY_TOOLS and not name.startswith(MUTATION_PREFIXES)


def enforce_tool_allowed(name: str) -> None:
    if not is_tool_allowed(name):
        raise PermissionError(f"Robinhood MCP tool is prohibited in Phase 1: {name}")
