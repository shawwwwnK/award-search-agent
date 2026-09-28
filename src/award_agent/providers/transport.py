"""Finite, injectable provider transports. Neither transport retries a call."""

from __future__ import annotations

import os
import subprocess
import tempfile
import time
from collections.abc import Mapping, Sequence
from dataclasses import dataclass
from typing import Protocol

import httpx


class TransportLimitError(ValueError):
    def __init__(self, message: str, *, observed_bytes: int = 0, sample: bytes = b"") -> None:
        super().__init__(message)
        self.observed_bytes = observed_bytes
        self.sample = sample[:4096]


@dataclass(frozen=True)
class HttpResponse:
    status_code: int
    body: bytes
    elapsed_seconds: float


class HttpTransport(Protocol):
    def get(
        self,
        url: str,
        *,
        params: Mapping[str, str | int | bool],
        headers: Mapping[str, str],
        timeout_seconds: float,
        max_response_bytes: int,
    ) -> HttpResponse: ...


class HttpxTransport:
    def get(
        self,
        url: str,
        *,
        params: Mapping[str, str | int | bool],
        headers: Mapping[str, str],
        timeout_seconds: float,
        max_response_bytes: int,
    ) -> HttpResponse:
        if timeout_seconds <= 0 or max_response_bytes <= 0:
            raise ValueError("transport time and byte limits must be positive")
        started = time.monotonic()
        with (
            httpx.Client(timeout=timeout_seconds, follow_redirects=False) as client,
            client.stream("GET", url, params=params, headers=headers) as response,
        ):
            chunks: list[bytes] = []
            total = 0
            for chunk in response.iter_bytes():
                total += len(chunk)
                if total > max_response_bytes:
                    raise TransportLimitError(
                        "provider response exceeded byte budget",
                        observed_bytes=total,
                        sample=(b"".join(chunks) + chunk)[:4096],
                    )
                if time.monotonic() - started > timeout_seconds:
                    raise TimeoutError("provider response exceeded elapsed-time budget")
                chunks.append(chunk)
            return HttpResponse(
                status_code=response.status_code,
                body=b"".join(chunks),
                elapsed_seconds=time.monotonic() - started,
            )


@dataclass(frozen=True)
class CommandResponse:
    exit_code: int
    stdout: bytes
    stderr: bytes
    elapsed_seconds: float


class CommandTransport(Protocol):
    def run(
        self,
        argv: Sequence[str],
        *,
        timeout_seconds: float,
        max_response_bytes: int,
    ) -> CommandResponse: ...


class SubprocessTransport:
    def run(
        self,
        argv: Sequence[str],
        *,
        timeout_seconds: float,
        max_response_bytes: int,
    ) -> CommandResponse:
        if not argv or timeout_seconds <= 0 or max_response_bytes <= 0:
            raise ValueError("command, time, and byte limits must be provided")
        started = time.monotonic()
        # Regular temporary files avoid an unbounded in-memory stdout pipe.
        with tempfile.TemporaryFile() as stdout, tempfile.TemporaryFile() as stderr:
            process = subprocess.Popen(list(argv), stdout=stdout, stderr=stderr)
            while (exit_code := process.poll()) is None:
                observed_bytes = (
                    os.fstat(stdout.fileno()).st_size + os.fstat(stderr.fileno()).st_size
                )
                if observed_bytes > max_response_bytes:
                    process.kill()
                    process.wait()
                    stdout.seek(0)
                    sample = stdout.read(2048)
                    stderr.seek(0)
                    sample += stderr.read(2048)
                    raise TransportLimitError(
                        "provider command exceeded byte budget",
                        observed_bytes=observed_bytes,
                        sample=sample,
                    )
                if time.monotonic() - started > timeout_seconds:
                    process.kill()
                    process.wait()
                    raise TimeoutError("provider command exceeded elapsed-time budget")
                time.sleep(0.02)
            observed_bytes = os.fstat(stdout.fileno()).st_size + os.fstat(stderr.fileno()).st_size
            if observed_bytes > max_response_bytes:
                stdout.seek(0)
                sample = stdout.read(2048)
                stderr.seek(0)
                sample += stderr.read(2048)
                raise TransportLimitError(
                    "provider command exceeded byte budget",
                    observed_bytes=observed_bytes,
                    sample=sample,
                )
            stdout.seek(0)
            stderr.seek(0)
            return CommandResponse(
                exit_code=exit_code,
                stdout=stdout.read(),
                stderr=stderr.read(),
                elapsed_seconds=time.monotonic() - started,
            )
