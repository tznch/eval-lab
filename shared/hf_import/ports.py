"""Find a free localhost port for model server wiring."""

from __future__ import annotations

import socket


def find_free_port(start: int = 8080, end: int = 8090) -> int:
    for port in range(start, end + 1):
        with socket.socket(socket.AF_INET, socket.SOCK_STREAM) as sock:
            try:
                sock.bind(("127.0.0.1", port))
            except OSError:
                continue
            return port
    raise RuntimeError(f"No free port in {start}–{end}")
