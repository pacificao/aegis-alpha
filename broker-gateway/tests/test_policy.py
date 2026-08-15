import pytest
from app.policy import enforce_tool_allowed, is_tool_allowed

@pytest.mark.parametrize("name", ["get_accounts", "get_portfolio", "get_equity_positions", "get_equity_quotes"])
def test_read_only_tools_are_allowed(name):
    assert is_tool_allowed(name)

@pytest.mark.parametrize("name", ["place_equity_order", "place_option_order", "cancel_equity_order", "review_equity_order", "create_watchlist", "unknown_tool"])
def test_mutations_and_unknown_tools_are_blocked(name):
    assert not is_tool_allowed(name)
    with pytest.raises(PermissionError):
        enforce_tool_allowed(name)
