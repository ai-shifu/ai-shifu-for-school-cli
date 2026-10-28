"""Interactive setup for a new client installation."""

import getpass
import sys
from pathlib import Path

from .cli_client import CLIError, SchoolClient
from .cli_config import configured_server, initialize
from .cli_skills import install_skills
from .schemas import Credentials


def _ask(message):
    print(message, end="", file=sys.stderr, flush=True)
    try:
        return input("").strip()
    except (EOFError, KeyboardInterrupt) as exc:
        raise CLIError(
            "configuration", "已取消设置；已完成步骤会保留，可再次运行 setup"
        ) from exc


def setup(*, server=None, session_file=None, dry_run=False):
    selected, _ = configured_server(server)
    if dry_run:
        return {
            "dry_run": True,
            "server": selected,
            "steps": ["configure school", "select skill target", "login and verify"],
        }
    if not sys.stdin.isatty():
        raise CLIError(
            "configuration",
            "请在终端运行 ai-shifu-for-school setup；自动化环境可分别配置域名和登录",
        )
    completed = []
    if selected is None:
        selected = initialize()["server"]
    completed.append("server_configured")
    print(f"连接学校：{selected}", file=sys.stderr)
    choice = (
        _ask("安装 Skills 到哪个工具？1）Codex  2）Claude Code  3）仅使用 CLI [1]：")
        or "1"
    )
    if choice not in {"1", "2", "3"}:
        raise CLIError("input", "请选择 1、2 或 3；未安装 Skills")
    if choice != "3":
        destination = (
            Path.home() / (".codex" if choice == "1" else ".claude") / "skills"
        )
        install_skills(destination)
        completed.append("skills_installed")
    username = _ask("老师账号：")
    credentials = Credentials(username=username, password=getpass.getpass("密码："))
    client = SchoolClient(selected, session_file, fresh=True)
    try:
        client.request("POST", "/api/auth/login", credentials.model_dump())
        completed.append("signed_in")
        me = client.request("GET", "/api/auth/me")
    except CLIError as exc:
        exc.details = {
            "completed": completed,
            "next": "核对学校地址和账号后执行 auth login；不需要重复安装",
        }
        raise
    finally:
        client.close()
    return {
        "server": selected,
        "user": me["user"],
        "completed": completed,
        "next": "重新加载宿主 Skills，然后请求查看自己的班级；也可运行 class list",
    }
