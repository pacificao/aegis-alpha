import pytest
from pydantic import ValidationError

from app.config import Settings


def test_phase_one_rejects_trading_enablement():
    with pytest.raises(ValidationError, match="Trading is prohibited"):
        Settings(aegis_trading_enabled=True)

