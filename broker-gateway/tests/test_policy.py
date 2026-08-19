import pytest
from app.policy import MARKET_DATA_TOOLS, contains_sensitive_argument, enforce_tool_allowed, is_tool_allowed, parse_loopback_callback, validate_authorization_url


def test_robinhood_protected_resource_is_the_full_official_mcp_endpoint():
    source = (__import__("pathlib").Path(__file__).parents[1] / "app" / "main.py").read_text()
    assert 'server_url=MCP_URL' in source
    assert 'server_url="https://agent.robinhood.com"' not in source
    assert 'scope="internal"' in source
    assert '_flow_task.cancel()' in source
    assert '_flow_task = None' in source
    assert '_callback = None' in source

@pytest.mark.parametrize("name", ["get_accounts", "get_portfolio", "get_equity_positions", "get_equity_quotes"])
def test_read_only_tools_are_allowed(name):
    assert is_tool_allowed(name)

@pytest.mark.parametrize("name", ["place_equity_order", "place_option_order", "cancel_equity_order", "review_equity_order", "create_watchlist", "unknown_tool"])
def test_mutations_and_unknown_tools_are_blocked(name):
    assert not is_tool_allowed(name)
    with pytest.raises(PermissionError):
        enforce_tool_allowed(name)


@pytest.mark.parametrize("url", [
    "https://robinhood.com/oauth/authorize",
    "https://www.robinhood.com/oauth/authorize",
    "https://agent.robinhood.com/oauth/authorize",
    "https://oauth.robinhood.com/oauth/authorize",
])
def test_official_authorization_redirects_are_allowed(url):
    assert validate_authorization_url(url) == url


@pytest.mark.parametrize("url", [
    "http://robinhood.com/oauth/authorize",
    "https://robinhood.com.evil.example/oauth/authorize",
    "https://evil.example/oauth/authorize",
    "https://robinhood.com:444/oauth/authorize",
])
def test_untrusted_authorization_redirects_are_blocked(url):
    with pytest.raises(RuntimeError):
        validate_authorization_url(url)


def test_loopback_callback_extracts_code_and_state():
    assert parse_loopback_callback("http://127.0.0.1:8765/callback?code=temporary&state=expected") == ("temporary", "expected")


@pytest.mark.parametrize("url", [
    "https://127.0.0.1:8765/callback?code=x&state=y",
    "http://localhost:8765/callback?code=x&state=y",
    "http://127.0.0.1:9999/callback?code=x&state=y",
    "http://127.0.0.1:8765/other?code=x&state=y",
    "http://127.0.0.1:8765/callback?code=x",
])
def test_invalid_loopback_callbacks_fail_closed(url):
    with pytest.raises(ValueError):
        parse_loopback_callback(url)


def test_denied_loopback_callback_is_not_accepted():
    with pytest.raises(PermissionError):
        parse_loopback_callback("http://127.0.0.1:8765/callback?error=access_denied&state=x")


def test_market_data_subset_is_public_read_only():
    assert {"get_equity_historicals", "get_equity_quotes", "get_equity_fundamentals", "get_crypto_quotes"}.issubset(MARKET_DATA_TOOLS)
    assert MARKET_DATA_TOOLS.issubset(__import__("app.policy", fromlist=["READ_ONLY_TOOLS"]).READ_ONLY_TOOLS)
    assert not {"get_accounts", "get_portfolio", "get_equity_positions", "get_equity_orders"} & MARKET_DATA_TOOLS
    assert not any(name.startswith(("place_", "cancel_", "create_", "update_", "review_")) for name in MARKET_DATA_TOOLS)


def test_sensitive_market_arguments_are_rejected_recursively():
    assert contains_sensitive_argument({"nested":{"token":"never-accepted"}})
    assert not contains_sensitive_argument({"symbols":["SPY"],"interval":"day"})
