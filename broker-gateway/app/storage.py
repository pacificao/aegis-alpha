"""Encrypted OAuth storage. Secret values are never logged or returned."""
import json
import os
from pathlib import Path
from typing import TypeVar

from cryptography.fernet import Fernet, InvalidToken
from mcp.client.auth import TokenStorage
from mcp.shared.auth import OAuthClientInformationFull, OAuthToken

T = TypeVar("T", OAuthToken, OAuthClientInformationFull)


class EncryptedFileTokenStorage(TokenStorage):
    def __init__(self, data_dir: str, key_file: str):
        self.data_dir = Path(data_dir)
        self.key_file = Path(key_file)
        self.data_dir.mkdir(mode=0o700, parents=True, exist_ok=True)
        self.cipher = Fernet(self.key_file.read_bytes().strip())

    def _read(self, name: str, model: type[T]) -> T | None:
        path = self.data_dir / name
        if not path.exists():
            return None
        try:
            payload = self.cipher.decrypt(path.read_bytes())
            return model.model_validate(json.loads(payload))
        except (InvalidToken, ValueError, json.JSONDecodeError) as error:
            raise RuntimeError("Protected Robinhood authorization storage is invalid") from error

    def _write(self, name: str, value: OAuthToken | OAuthClientInformationFull) -> None:
        target = self.data_dir / name
        temporary = self.data_dir / f".{name}.tmp"
        payload = json.dumps(value.model_dump(mode="json"), separators=(",", ":")).encode()
        fd = os.open(temporary, os.O_WRONLY | os.O_CREAT | os.O_TRUNC, 0o600)
        try:
            os.write(fd, self.cipher.encrypt(payload))
            os.fsync(fd)
        finally:
            os.close(fd)
        os.replace(temporary, target)

    async def get_tokens(self) -> OAuthToken | None:
        return self._read("oauth-token.enc", OAuthToken)

    async def set_tokens(self, tokens: OAuthToken) -> None:
        self._write("oauth-token.enc", tokens)

    async def get_client_info(self) -> OAuthClientInformationFull | None:
        return self._read("oauth-client.enc", OAuthClientInformationFull)

    async def set_client_info(self, client_info: OAuthClientInformationFull) -> None:
        self._write("oauth-client.enc", client_info)

    def configured(self) -> bool:
        return (self.data_dir / "oauth-token.enc").is_file()

    def clear(self) -> None:
        for name in ("oauth-token.enc", "oauth-client.enc"):
            path = self.data_dir / name
            if path.exists():
                path.unlink()
