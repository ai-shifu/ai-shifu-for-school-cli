"""Persist the school service address in the user's local environment file."""

import json
import os
import re
import sys
from pathlib import Path
from urllib.parse import urlsplit

from dotenv import dotenv_values

from .cli_client import CLIError, atomic_text, normalize_server

SERVER_KEY = "SCHOOL_SERVER_URL"


def env_path():
    return Path.home() / ".config/ai-shifu-for-school/.env"


def school_url(value):
    value = value.strip()
    if "://" not in value:
        value = "https://" + value
    value = normalize_server(value)
    if urlsplit(value).path.rstrip("/") in {
        "/classroom",
        "/online",
        "/classes",
        "/records",
    }:
        raise CLIError("input", "请填写学校服务域名，不要包含 /classroom 等网页路径")
    return value


def set_server(value, *, dry_run=False):
    server = school_url(value)
    path = env_path()
    if not dry_run:
        lines = path.read_text(encoding="utf-8").splitlines() if path.exists() else []
        setting = SERVER_KEY + "=" + json.dumps(server, ensure_ascii=False)
        pattern = re.compile(r"^\s*(?:export\s+)?" + SERVER_KEY + r"\s*=")
        updated = []
        replaced = False
        for line in lines:
            if pattern.match(line):
                if not replaced:
                    updated.append(setting)
                    replaced = True
            else:
                updated.append(line)
        if not replaced:
            updated.append(setting)
        path.parent.mkdir(parents=True, exist_ok=True, mode=0o700)
        atomic_text(path, "\n".join(updated) + "\n")
    return {"server": server, "env_file": str(path), "dry_run": dry_run}


def configured_server(explicit=None):
    if explicit:
        return school_url(explicit), "argument"
    if os.environ.get(SERVER_KEY):
        return school_url(os.environ[SERVER_KEY]), "environment"
    path = env_path()
    if path.exists():
        saved = dotenv_values(path, interpolate=False).get(SERVER_KEY)
        if not saved:
            raise CLIError(
                "configuration",
                "本地 .env 缺少学校域名，请执行 config init 或 config set-server",
            )
        return school_url(saved), "env_file"
    return None, None


def initialize(*, server=None, dry_run=False):
    if not server:
        if not sys.stdin.isatty():
            raise CLIError(
                "configuration",
                "请在终端执行 ai-shifu-for-school config init 填写学校域名；也可使用 config set-server <域名>",
            )
        try:
            print(
                "学校服务域名（例如 https://school.example，不含 /classroom）：",
                end="",
                file=sys.stderr,
                flush=True,
            )
            server = input("")
        except (EOFError, KeyboardInterrupt) as exc:
            raise CLIError("configuration", "已取消域名配置，未修改配置文件") from exc
        if not server.strip():
            raise CLIError("configuration", "学校域名不能为空，未修改配置文件")
    return set_server(server, dry_run=dry_run)


def resolve_server(explicit=None, *, dry_run=False):
    server, _ = configured_server(explicit)
    if server:
        return server
    if dry_run:
        raise CLIError(
            "configuration",
            "尚未设置学校域名；预览不会写配置，请先 config init 或提供 --server",
        )
    return initialize()["server"]


def show_config(explicit=None):
    server, source = configured_server(explicit)
    return {
        "server": server,
        "source": source,
        "env_file": str(env_path()),
        "configured": server is not None,
    }
