from app.config import Settings

def test_trading_is_disabled_by_default_and_requires_external_gates():
    assert Settings().aegis_trading_enabled is False
    assert Settings(aegis_trading_enabled=True).aegis_trading_enabled is True
