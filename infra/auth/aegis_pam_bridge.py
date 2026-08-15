#!/usr/bin/env python3
"""Minimal local-only PAM authentication bridge for the Aegis backend."""

from __future__ import annotations

import ctypes
import ctypes.util
import json
import os
import socket
import socketserver
import struct
import threading
import time
from collections import deque

SOCKET_PATH = "/run/aegis-auth/pam.sock"
AUTHORIZED_USERNAME = os.environ.get("AEGIS_AUTHORIZED_USER", "")
BACKEND_UID = 100
BACKEND_GID = 101
MAX_REQUEST_BYTES = 4096
MAX_ATTEMPTS = 10
RATE_WINDOW_SECONDS = 300

PAM_SUCCESS = 0
PAM_PROMPT_ECHO_OFF = 1
PAM_PROMPT_ECHO_ON = 2


class PamMessage(ctypes.Structure):
    _fields_ = [("msg_style", ctypes.c_int), ("msg", ctypes.c_char_p)]


class PamResponse(ctypes.Structure):
    _fields_ = [("resp", ctypes.c_char_p), ("resp_retcode", ctypes.c_int)]


Conversation = ctypes.CFUNCTYPE(
    ctypes.c_int,
    ctypes.c_int,
    ctypes.POINTER(ctypes.POINTER(PamMessage)),
    ctypes.POINTER(ctypes.POINTER(PamResponse)),
    ctypes.c_void_p,
)


class PamConv(ctypes.Structure):
    _fields_ = [("conv", Conversation), ("appdata_ptr", ctypes.c_void_p)]


_pam = ctypes.CDLL(ctypes.util.find_library("pam") or "libpam.so.0")
_libc = ctypes.CDLL(ctypes.util.find_library("c") or "libc.so.6")
_libc.calloc.restype = ctypes.c_void_p
_libc.strdup.restype = ctypes.c_void_p
_pam.pam_start.argtypes = [ctypes.c_char_p, ctypes.c_char_p, ctypes.POINTER(PamConv), ctypes.POINTER(ctypes.c_void_p)]
_pam.pam_authenticate.argtypes = [ctypes.c_void_p, ctypes.c_int]
_pam.pam_acct_mgmt.argtypes = [ctypes.c_void_p, ctypes.c_int]
_pam.pam_end.argtypes = [ctypes.c_void_p, ctypes.c_int]


def authenticate(username: str, password: str) -> bool:
    password_bytes = bytearray(password.encode("utf-8"))
    username_bytes = username.encode("utf-8")

    @Conversation
    def conversation(count, messages, responses, _appdata):
        memory = _libc.calloc(count, ctypes.sizeof(PamResponse))
        if not memory:
            return 5
        response_array = ctypes.cast(memory, ctypes.POINTER(PamResponse))
        for index in range(count):
            style = messages[index].contents.msg_style
            if style == PAM_PROMPT_ECHO_OFF:
                answer = bytes(password_bytes)
            elif style == PAM_PROMPT_ECHO_ON:
                answer = username_bytes
            else:
                answer = b""
            response_array[index].resp = ctypes.cast(_libc.strdup(answer), ctypes.c_char_p)
            response_array[index].resp_retcode = 0
        responses[0] = response_array
        return PAM_SUCCESS

    handle = ctypes.c_void_p()
    conv = PamConv(conversation, None)
    result = _pam.pam_start(b"aegis-alpha", username_bytes, ctypes.byref(conv), ctypes.byref(handle))
    try:
        if result == PAM_SUCCESS:
            result = _pam.pam_authenticate(handle, 0)
        if result == PAM_SUCCESS:
            result = _pam.pam_acct_mgmt(handle, 0)
        return result == PAM_SUCCESS
    finally:
        if handle:
            _pam.pam_end(handle, result)
        for index in range(len(password_bytes)):
            password_bytes[index] = 0


class RateLimiter:
    def __init__(self) -> None:
        self._attempts: deque[float] = deque()
        self._lock = threading.Lock()

    def allow(self) -> bool:
        with self._lock:
            now = time.monotonic()
            while self._attempts and self._attempts[0] < now - RATE_WINDOW_SECONDS:
                self._attempts.popleft()
            if len(self._attempts) >= MAX_ATTEMPTS:
                return False
            self._attempts.append(now)
            return True


rate_limiter = RateLimiter()


class Handler(socketserver.StreamRequestHandler):
    def handle(self) -> None:
        peer_pid, peer_uid, peer_gid = struct.unpack("3i", self.request.getsockopt(socket.SOL_SOCKET, socket.SO_PEERCRED, 12))
        del peer_pid
        if peer_uid != BACKEND_UID or peer_gid != BACKEND_GID or not rate_limiter.allow():
            self._respond(False)
            return
        raw = self.rfile.readline(MAX_REQUEST_BYTES + 1)
        if not raw.endswith(b"\n") or len(raw) > MAX_REQUEST_BYTES:
            self._respond(False)
            return
        try:
            payload = json.loads(raw)
            username = payload.get("username")
            password = payload.get("password")
            valid = (
                username == AUTHORIZED_USERNAME
                and isinstance(password, str)
                and 0 < len(password.encode("utf-8")) <= 1024
                and authenticate(username, password)
            )
        except (ValueError, TypeError, UnicodeError):
            valid = False
        self._respond(valid)

    def _respond(self, authenticated: bool) -> None:
        self.wfile.write(json.dumps({"authenticated": authenticated}, separators=(",", ":")).encode() + b"\n")


class Server(socketserver.ThreadingUnixStreamServer):
    daemon_threads = True
    allow_reuse_address = False


def main() -> None:
    if not AUTHORIZED_USERNAME:
        raise RuntimeError("AEGIS_AUTHORIZED_USER must be configured")
    os.makedirs(os.path.dirname(SOCKET_PATH), mode=0o750, exist_ok=True)
    os.chown(os.path.dirname(SOCKET_PATH), 0, BACKEND_GID)
    os.chmod(os.path.dirname(SOCKET_PATH), 0o750)
    try:
        os.unlink(SOCKET_PATH)
    except FileNotFoundError:
        pass
    with Server(SOCKET_PATH, Handler) as server:
        os.chown(SOCKET_PATH, 0, BACKEND_GID)
        os.chmod(SOCKET_PATH, 0o660)
        server.serve_forever(poll_interval=0.5)


if __name__ == "__main__":
    main()
