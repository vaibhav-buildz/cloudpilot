"""Versioned, length-prefixed control messages and bounded binary payloads."""

import asyncio
import json
import re
import socket
import struct

VERSION = 1
JOB_ID = re.compile(r"[0-9a-f]{32}")
HEADER = struct.Struct("!II")
MAX_METADATA = 8192
MAX_ERROR = 4000


class ProtocolError(RuntimeError):
    """The current connection cannot be reused."""


async def _read(connection: socket.socket, length: int) -> bytes:
    loop = asyncio.get_running_loop()
    data = bytearray(length)
    remaining = memoryview(data)
    while remaining:
        count = await loop.sock_recv_into(connection, remaining)
        if count == 0:
            raise EOFError("Simulation connection closed")
        remaining = remaining[count:]
    return bytes(data)


async def receive(connection: socket.socket, max_payload: int) -> tuple[dict, bytes]:
    metadata_size, payload_size = HEADER.unpack(await _read(connection, HEADER.size))
    if not 0 < metadata_size <= MAX_METADATA or payload_size > max_payload:
        raise ProtocolError("Invalid simulation frame length")
    try:
        metadata = json.loads(await _read(connection, metadata_size))
    except (ValueError, RecursionError) as exc:
        raise ProtocolError("Invalid simulation metadata") from exc
    if (
        not isinstance(metadata, dict)
        or type(metadata.get("version")) is not int
        or metadata["version"] != VERSION
    ):
        raise ProtocolError("Unexpected simulation protocol version")
    return metadata, await _read(connection, payload_size)


async def send(
    connection: socket.socket, metadata: dict, payload: bytes = b"", *, max_payload: int
) -> None:
    encoded = json.dumps(
        {**metadata, "version": VERSION}, separators=(",", ":"), allow_nan=False
    ).encode()
    if len(encoded) > MAX_METADATA or len(payload) > max_payload:
        raise ProtocolError("Simulation frame exceeds size limit")
    loop = asyncio.get_running_loop()
    await loop.sock_sendall(connection, HEADER.pack(len(encoded), len(payload)) + encoded)
    if payload:
        await loop.sock_sendall(connection, payload)
