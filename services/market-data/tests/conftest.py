from __future__ import annotations

import shutil
import subprocess
import time
from collections.abc import Iterator
from pathlib import Path

import pytest
from support import TEST_CALENDAR, calendar


@pytest.fixture
def cal():  # type: ignore[no-untyped-def]
    return calendar()


@pytest.fixture(scope="session")
def file_calendar():  # type: ignore[no-untyped-def]
    from qm_md.sessions import SessionCalendar

    return SessionCalendar.from_yaml(TEST_CALENDAR, allow_test=True)


def _free_port() -> int:
    import socket

    with socket.socket() as s:
        s.bind(("127.0.0.1", 0))
        return int(s.getsockname()[1])


class RedisServer:
    def __init__(self, workdir: Path) -> None:
        self.port = _free_port()
        self.url = f"redis://127.0.0.1:{self.port}/0"
        self._workdir = workdir
        self._proc: subprocess.Popen[bytes] | None = None

    def start(self) -> None:
        self._proc = subprocess.Popen(
            ["redis-server", "--port", str(self.port), "--save", "", "--appendonly", "no",
             "--dir", str(self._workdir)],
            stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL,
        )
        deadline = time.time() + 5
        import redis

        while time.time() < deadline:
            try:
                redis.Redis.from_url(self.url, socket_connect_timeout=0.2).ping()
                return
            except redis.RedisError:
                time.sleep(0.05)
        raise RuntimeError("redis-server did not start")

    def kill(self) -> None:
        if self._proc is not None and self._proc.poll() is None:
            self._proc.kill()
            self._proc.wait(timeout=5)

    def stop(self) -> None:
        self.kill()


@pytest.fixture
def redis_server(tmp_path: Path) -> Iterator[RedisServer]:
    if shutil.which("redis-server") is None:
        pytest.skip("redis-server not installed; integration test skipped")
    server = RedisServer(tmp_path)
    server.start()
    try:
        yield server
    finally:
        server.stop()
