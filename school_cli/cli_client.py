"""HTTP transport shared by school commands; never bypass the public gateway."""

import hashlib
import http.cookiejar
import json
import os
import tempfile
from pathlib import Path
from urllib.parse import unquote, urlsplit

import httpx


class CLIError(Exception):
    def __init__(self, kind, message, *, status=None, details=None):
        super().__init__(message)
        self.kind, self.status, self.details = kind, status, details

    def as_dict(self):
        result = {"kind": self.kind, "message": str(self)}
        if self.status is not None:
            result["status"] = self.status
        if self.details is not None:
            result["details"] = redact(self.details)
        return result


def redact(value):
    if isinstance(value, dict):
        return {
            k: "[redacted]"
            if any(s in k.lower() for s in ("password", "token", "secret", "cookie"))
            else redact(v)
            for k, v in value.items()
        }
    if isinstance(value, list):
        return [redact(v) for v in value]
    return value


def normalize_server(server):
    parts = urlsplit(server)
    if (
        any(character.isspace() for character in server)
        or parts.scheme not in {"http", "https"}
        or not parts.hostname
        or parts.username
        or parts.password
        or parts.query
        or parts.fragment
    ):
        raise CLIError("input", "平台地址必须是没有凭据、查询参数或片段的 HTTP(S) URL")
    if parts.scheme == "http" and parts.hostname not in {
        "localhost",
        "127.0.0.1",
        "::1",
    }:
        raise CLIError("input", "远程平台请使用 HTTPS；HTTP 仅用于本机开发")
    return server.rstrip("/")


def validate_path(path):
    decoded = path
    for _ in range(4):
        expanded = unquote(decoded)
        if expanded == decoded:
            break
        decoded = expanded
    parts = urlsplit(decoded)
    if (
        not parts.path.startswith("/api/")
        or parts.scheme
        or parts.netloc
        or parts.fragment
        or "\\" in decoded
        or any(p in {".", ".."} for p in parts.path.split("/"))
    ):
        raise CLIError("input", "只允许调用本平台 /api/ 下的路径")


def atomic_text(path, content):
    path = Path(path)
    path.parent.mkdir(parents=True, exist_ok=True)
    fd, temporary = tempfile.mkstemp(dir=path.parent, prefix=".school-")
    try:
        with os.fdopen(fd, "w", encoding="utf-8") as handle:
            handle.write(content)
        os.replace(temporary, path)
    finally:
        Path(temporary).unlink(missing_ok=True)


class SchoolClient:
    def __init__(self, server, session_file=None, *, transport=None, fresh=False):
        self.server = normalize_server(server)
        key = hashlib.sha256(self.server.encode()).hexdigest()[:16]
        self.session_file = (
            Path(session_file)
            if session_file
            else (Path.home() / ".config/classroom-platform" / f"{key}.cookies")
        )
        self.jar = http.cookiejar.LWPCookieJar()
        if self.session_file.exists() and not fresh:
            saved = self.session_file.read_text(encoding="utf-8")
            binding = f"# school-server: {self.server}\n"
            if binding not in saved:
                raise CLIError(
                    "authentication", "会话未绑定此平台，请重新执行 auth login"
                )
            try:
                self.jar.load(str(self.session_file), ignore_discard=True)
            except http.cookiejar.LoadError as exc:
                raise CLIError("authentication", "会话文件损坏，请重新登录") from exc
        self.http = httpx.Client(
            cookies=self.jar, transport=transport, follow_redirects=False
        )
        self.streamed = False

    def close(self):
        self.http.close()

    def _save_session(self):
        if not list(self.jar):
            return
        self.session_file.parent.mkdir(parents=True, exist_ok=True, mode=0o700)
        fd, temporary = tempfile.mkstemp(
            dir=self.session_file.parent, prefix=".cookies-"
        )
        os.close(fd)
        try:
            self.jar.save(temporary, ignore_discard=True)
            with open(temporary, "a", encoding="utf-8") as handle:
                handle.write(f"# school-server: {self.server}\n")
            os.replace(temporary, self.session_file)
        finally:
            Path(temporary).unlink(missing_ok=True)

    @staticmethod
    def _decode(response):
        try:
            result = response.json()
        except ValueError as exc:
            raise CLIError(
                "service", "平台返回非 JSON 响应", status=response.status_code
            ) from exc
        code = result.get("code", 0) if isinstance(result, dict) else 0
        if type(code) is not int:
            raise CLIError("service", "平台业务状态码无效", status=response.status_code)
        if response.is_error or response.is_redirect or code != 0:
            status = response.status_code
            kind = (
                "authentication"
                if status == 401 or code in {1001, 1004, 1005}
                else "permission"
                if status == 403
                else "conflict"
                if status == 409 or code == 4007
                else "input"
                if status in {400, 422}
                else "not_found"
                if status == 404
                else "service"
            )
            message = (
                (result.get("message") or result.get("detail"))
                if isinstance(result, dict)
                else None
            )
            # Validation payloads may echo a password or other supplied input.
            if not isinstance(message, str):
                message = (
                    "请求字段不符合平台要求" if kind == "input" else "平台请求未完成"
                )
            raise CLIError(kind, message, status=status)
        return (
            result.get("data")
            if isinstance(result, dict) and "code" in result
            else result
        )

    def request(
        self, method, path, data=None, *, params=None, stream=False, files=None
    ):
        validate_path(path)
        method = method.upper()
        headers = {"Accept": "text/event-stream" if stream else "application/json"}
        if method != "GET" and path != "/api/auth/login":
            me = self.request("GET", "/api/auth/me")
            headers["X-CSRF-Token"] = me["csrf_token"]
        kwargs = {
            "headers": headers,
            "params": params,
            "timeout": 180 if stream else 30,
        }
        if files is not None:
            kwargs.update(files=files, data=data)
        elif data is not None:
            kwargs["json"] = data
        try:
            if stream:
                with self.http.stream(method, self.server + path, **kwargs) as response:
                    if (
                        response.is_success
                        and "text/event-stream"
                        in response.headers.get("content-type", "")
                    ):
                        self.streamed = True
                        failed = False
                        for line in response.iter_lines():
                            print(line, flush=True)
                            if (
                                line.startswith("event:")
                                and line[6:].strip() == "error"
                            ):
                                failed = True
                            if line.startswith("data:"):
                                try:
                                    item = json.loads(line[5:])
                                except ValueError:
                                    continue
                                if (
                                    isinstance(item, dict)
                                    and item.get("type") == "error"
                                ):
                                    failed = True
                        self._save_session()
                        if failed:
                            raise CLIError(
                                "service", "授课流返回错误事件，请检查 SSE 中的具体结果"
                            )
                        return None
                    response.read()
                    return self._decode(response)
            response = self.http.request(method, self.server + path, **kwargs)
            result = self._decode(response)
            self._save_session()
            return result
        except httpx.TimeoutException as exc:
            raise CLIError(
                "network", "请求超时；写操作结果可能未知，请查询状态后再决定是否重试"
            ) from exc
        except httpx.HTTPError as exc:
            raise CLIError(
                "network", "连接中断或平台不可用；写操作请先查询实际状态，不要盲目重试"
            ) from exc


def read_json(value):
    import sys

    raw = (
        sys.stdin.read()
        if value == "@-"
        else (
            Path(value[1:]).read_text(encoding="utf-8")
            if value.startswith("@")
            else value
        )
    )
    return json.loads(raw)
