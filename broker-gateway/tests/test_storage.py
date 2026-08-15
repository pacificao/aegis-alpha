import asyncio

from cryptography.fernet import Fernet
from mcp.shared.auth import OAuthToken

from app.storage import EncryptedFileTokenStorage


def test_oauth_token_is_encrypted_at_rest(tmp_path):
    key = tmp_path / "key"
    key.write_bytes(Fernet.generate_key())
    storage = EncryptedFileTokenStorage(str(tmp_path), str(key))
    token = OAuthToken(access_token="must-never-appear-on-disk", token_type="bearer")
    asyncio.run(storage.set_tokens(token))
    assert b"must-never-appear-on-disk" not in (tmp_path / "oauth-token.enc").read_bytes()
    assert asyncio.run(storage.get_tokens()).access_token == "must-never-appear-on-disk"
