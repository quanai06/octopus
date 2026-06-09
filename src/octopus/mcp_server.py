from __future__ import annotations

import json
import sys
from typing import Any, TextIO

from pydantic import ValidationError

from octopus.tools.jsonio import to_jsonable
from octopus.tools.registry import call_tool, list_tool_specs
from octopus.tools.resources import list_resources, read_resource

PROTOCOL_VERSION = "2024-11-05"


def serve_stdio() -> None:
    server = MCPStdioServer(sys.stdin, sys.stdout)
    server.serve()


class MCPStdioServer:
    def __init__(self, stdin: TextIO, stdout: TextIO) -> None:
        self.stdin = stdin
        self.stdout = stdout

    def serve(self) -> None:
        while True:
            message = self._read_message()
            if message is None:
                break
            response = handle_message(message)
            if response is not None:
                self._write_message(response)

    def _read_message(self) -> dict[str, Any] | None:
        headers: dict[str, str] = {}
        while True:
            line = self.stdin.readline()
            if line == "":
                return None
            line = line.rstrip("\r\n")
            if not line:
                break
            key, _, value = line.partition(":")
            headers[key.lower()] = value.strip()
        length = int(headers.get("content-length", "0"))
        if length <= 0:
            return None
        body = self.stdin.read(length)
        return json.loads(body)

    def _write_message(self, payload: dict[str, Any]) -> None:
        body = json.dumps(payload, ensure_ascii=False)
        self.stdout.write(f"Content-Length: {len(body.encode('utf-8'))}\r\n\r\n{body}")
        self.stdout.flush()


def handle_message(message: dict[str, Any]) -> dict[str, Any] | None:
    if "id" not in message:
        return None
    request_id = message["id"]
    method = str(message.get("method") or "")
    raw_params = message.get("params")
    params: dict[str, Any] = raw_params if isinstance(raw_params, dict) else {}
    try:
        result = _dispatch(method, params)
    except Exception as exc:
        return {
            "jsonrpc": "2.0",
            "id": request_id,
            "error": _error_payload(exc),
        }
    return {"jsonrpc": "2.0", "id": request_id, "result": result}


def _dispatch(method: str, params: dict[str, Any]) -> dict[str, Any] | None:
    if method == "initialize":
        return {
            "protocolVersion": PROTOCOL_VERSION,
            "capabilities": {
                "tools": {"listChanged": False},
                "resources": {"listChanged": False},
            },
            "serverInfo": {"name": "octopus", "version": "0.1.0"},
        }
    if method == "ping":
        return {}
    if method == "shutdown":
        return None
    if method == "tools/list":
        return {
            "tools": [
                {
                    "name": spec.name,
                    "description": spec.description,
                    "inputSchema": spec.input_schema,
                }
                for spec in list_tool_specs()
            ]
        }
    if method == "tools/call":
        name = str(params.get("name") or "")
        arguments = params.get("arguments")
        if not isinstance(arguments, dict):
            arguments = {}
        result = to_jsonable(call_tool(name, arguments))
        text = json.dumps(result, ensure_ascii=False, indent=2)
        return {
            "content": [{"type": "text", "text": text}],
            "structuredContent": result,
            "isError": False,
        }
    if method == "resources/list":
        return {
            "resources": [
                {
                    "uri": resource.uri,
                    "name": resource.name,
                    "description": resource.description,
                    "mimeType": resource.mime_type,
                }
                for resource in list_resources()
            ]
        }
    if method == "resources/read":
        uri = str(params.get("uri") or "")
        resource, text = read_resource(uri)
        return {
            "contents": [
                {
                    "uri": resource.uri,
                    "mimeType": resource.mime_type,
                    "text": text,
                }
            ]
        }
    raise ValueError(f"Unsupported MCP method: {method}")


def _error_payload(exc: Exception) -> dict[str, Any]:
    if isinstance(exc, KeyError):
        code = -32602
    elif isinstance(exc, ValidationError):
        code = -32602
    elif isinstance(exc, ValueError):
        code = -32602
    else:
        code = -32000
    return {"code": code, "message": str(exc)}
