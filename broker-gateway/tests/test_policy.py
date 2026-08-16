import pytest
from app.policy import enforce_tool_allowed, is_tool_allowed, validate_authorization_url


def test_robinhood_protected_resource_is_the_full_official_mcp_endpoint():
    source = (__import__("pathlib").Path(__file__).parents[1] / "app" / "main.py").read_text()
    assert 'server_url=MCP_URL' in source
    assert 'server_url="https://agent.robinhood.com"' not in source

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
