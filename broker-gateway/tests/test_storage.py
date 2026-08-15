import asyncio

from cryptography.fernet import Fernet
from mcp.shared.auth import OAuthToken

from app.storage import EncryptedFileTokenStorage


def test_oauth_token_is_encrypted_at_rest(tmp_path):
    key = tmp_path / "key"
    key.write_bytes(Fernet.generate_key())
    key.chmod(0o600)
    storage = EncryptedFileTokenStorage(str(tmp_path), str(key))
    token = OAuthToken(access_token="must-never-appear-on-disk", token_type="bearer")
    asyncio.run(storage.set_tokens(token))
    assert b"must-never-appear-on-disk" not in (tmp_path / "oauth-token.enc").read_bytes()
    assert asyncio.run(storage.get_tokens()).access_token == "must-never-appear-on-disk"
    assert (tmp_path / "oauth-token.enc").stat().st_mode & 0o777 == 0o600
    assert tmp_path.stat().st_mode & 0o777 == 0o700


def test_symlink_token_storage_fails_closed(tmp_path):
    key = tmp_path / "key"
    key.write_bytes(Fernet.generate_key())
    key.chmod(0o600)
    outside = tmp_path / "outside"
    outside.write_text("do not overwrite")
    (tmp_path / "oauth-token.enc").symlink_to(outside)
    storage = EncryptedFileTokenStorage(str(tmp_path), str(key))
    token = OAuthToken(access_token="must-never-appear-on-disk", token_type="bearer")
    try:
        asyncio.run(storage.set_tokens(token))
        raise AssertionError("symlink storage must fail closed")
    except RuntimeError:
        pass
    assert outside.read_text() == "do not overwrite"


def test_world_readable_encryption_key_fails_closed(tmp_path):
    key = tmp_path / "key"
    key.write_bytes(Fernet.generate_key())
    key.chmod(0o604)
    try:
        EncryptedFileTokenStorage(str(tmp_path), str(key))
        raise AssertionError("world-readable key must fail closed")
    except RuntimeError:
        pass
