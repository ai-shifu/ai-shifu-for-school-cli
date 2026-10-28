"""混合式智慧教学 CLI：教师业务命令与独立 Skills。"""

import argparse
import getpass
import json
import mimetypes
import sys
from importlib.metadata import version
from pathlib import Path

from pydantic import ValidationError

from . import cli_courses as courses
from .cli_client import (
    CLIError,
    SchoolClient,
    read_json,
    redact,
    validate_path,
)
from .cli_commands import BY_NAME, COMMANDS
from .cli_config import initialize, resolve_server, set_server, show_config
from .cli_skills import install_skills, list_skills, read_skill
from .onboarding import setup


class SchoolParser(argparse.ArgumentParser):
    def error(self, message):
        raise CLIError("input", "命令参数不完整或无效；请运行对应命令 --help 或 schema")


def _positive(value):
    result = int(value)
    if result < 1:
        raise argparse.ArgumentTypeError("ID 必须为正整数")
    return result


def _common(parser, *, root=False):
    default = None if root else argparse.SUPPRESS
    parser.add_argument(
        "--server",
        default=default,
        help="临时指定学校服务地址；未指定时读取本机 .env",
    )
    parser.add_argument(
        "--session-file", type=Path, default=default, help="隔离账号的会话文件"
    )
    parser.add_argument(
        "--dry-run",
        action="store_true",
        default=False if root else default,
        help="预览请求，不执行写操作",
    )


def build_parser():
    parser = SchoolParser(prog="ai-shifu-for-school", description=__doc__)
    _common(parser, root=True)
    parser.add_argument(
        "--version", action="version", version=version("ai-shifu-for-school-cli")
    )
    groups = {(): parser.add_subparsers(dest="command", required=True)}
    leaves = {}
    for spec in COMMANDS:
        parts = tuple(spec.name.split())
        for length in range(1, len(parts)):
            prefix = parts[:length]
            if prefix not in groups:
                group = groups[prefix[:-1]].add_parser(prefix[-1])
                groups[prefix] = group.add_subparsers(
                    dest="group_" + str(length), required=True
                )
        leaf = groups[parts[:-1]].add_parser(
            parts[-1],
            help=spec.description or spec.name,
            description=spec.description or spec.name,
        )
        leaves[spec.name] = leaf
        leaf.set_defaults(spec=spec)
        _common(leaf)
        for argument in spec.arguments:
            argument_type = str
            if argument.endswith("_id"):
                argument_type = _positive
            elif argument.endswith("_bid"):
                argument_type = courses.identifier
            leaf.add_argument(argument, type=argument_type)
        if spec.model:
            for name in spec.model.model_fields:
                if name == "password":
                    continue
                leaf.add_argument(
                    "--" + name.replace("_", "-"),
                    default=None,
                    help=f"请求字段 {name}；数组及对象使用 JSON",
                )
        leaf.add_argument(
            "--data",
            help="JSON 对象、@文件.json，或 @- 从标准输入读取；显式字段选项优先",
        )
        leaf.add_argument("--query", help="GET 查询参数 JSON 对象（支持 @文件及 @-）")
        if spec.handler in {"content", "upload"}:
            leaf.add_argument(
                "--file",
                type=Path,
                required=True,
                help="本地文件；课时内容必须为 UTF-8",
            )
        if spec.handler == "metadata":
            leaf.add_argument("--course-prompt-file", type=Path)
        if spec.handler in {"content", "metadata"}:
            baseline = leaf.add_mutually_exclusive_group(required=True)
            baseline.add_argument(
                "--base-revision", type=int, help="编辑前记录的版本基线"
            )
            baseline.add_argument("--course-dir", type=Path)
        if spec.handler in {"pull", "status", "save", "create_directory"}:
            leaf.add_argument("--course-dir", type=Path, required=True)
    api = groups[()].add_parser("api", help="原始 API 兜底；权限与网页一致")
    _common(api)
    api.add_argument("method", choices=["GET", "POST", "PUT", "PATCH", "DELETE"])
    api.add_argument("path")
    api.add_argument("--data")
    api.add_argument("--query")
    api.add_argument("--stream", action="store_true")
    schema = groups[()].add_parser(
        "schema", help="查询命令及参数；例如 schema online lesson update"
    )
    schema.add_argument("name", nargs="*")
    setup_parser = groups[()].add_parser(
        "setup", help="引导填写域名、安装 Skills 并登录"
    )
    _common(setup_parser)
    config = groups[()].add_parser("config", help="配置本机 .env 中的学校域名")
    config_sub = config.add_subparsers(dest="config_action", required=True)
    initialize_parser = config_sub.add_parser("init", help="交互填写并保存学校域名")
    _common(initialize_parser)
    set_parser = config_sub.add_parser(
        "set-server", help="保存指定学校域名，不登录或迁移会话"
    )
    set_parser.add_argument("url")
    set_parser.add_argument("--dry-run", action="store_true", default=argparse.SUPPRESS)
    show_parser = config_sub.add_parser("show", help="查看当前生效地址及配置文件位置")
    _common(show_parser)
    skills = groups[()].add_parser("skills", help="随包携带的独立教学 Skills")
    skill_sub = skills.add_subparsers(dest="skill_action", required=True)
    skill_sub.add_parser("list")
    read = skill_sub.add_parser("read")
    read.add_argument("name", choices=list_skills())
    read.add_argument("reference", nargs="?", default="SKILL.md")
    install = skill_sub.add_parser("install")
    install.add_argument("--dest", type=Path, required=True)
    install.add_argument("--dry-run", action="store_true", default=argparse.SUPPRESS)
    doctor = groups[()].add_parser(
        "doctor", help="检查包内 Skills、连接、当前身份与线上引擎状态"
    )
    _common(doctor)
    # Keep the already documented school CLI spellings, without a second executable.
    for name, target in {
        "login": "auth login",
        "me": "auth me",
        "logout": "auth logout",
        "classes": "class list",
        "courses": "course list",
    }.items():
        alias = groups[()].add_parser(name, help=target + " 的简写")
        _common(alias)
        alias.set_defaults(spec=BY_NAME[target])
        if name == "login":
            alias.add_argument("username")
        alias.add_argument("--data")
        alias.add_argument("--query")
    inbox = groups[()].add_parser("inbox", help="已有学生任务入口")
    _common(inbox)
    return parser, leaves


def _body(args, spec):
    data = read_json(args.data) if getattr(args, "data", None) else {}
    if not isinstance(data, dict):
        raise CLIError("input", "--data 必须是 JSON 对象")
    if spec.model:
        schema = spec.model.model_json_schema()
        properties = schema["properties"]
        for name in spec.model.model_fields:
            value = getattr(args, name, None)
            if value is not None:
                shape = properties[name]
                if "$ref" in shape:
                    shape = schema["$defs"][shape["$ref"].split("/")[-1]]
                types = {
                    shape.get("type"),
                    *(x.get("type") for x in shape.get("anyOf", [])),
                }
                data[name] = json.loads(value) if types & {"array", "object"} else value
                if "integer" in types:
                    data[name] = int(value)
        if spec.handler == "student" and "password" not in data:
            if args.dry_run:
                # Validate every other field while keeping the preview noninteractive.
                data["password"] = "DryRunOnly!2026"
            else:
                data["password"] = getpass.getpass("新学生初始密码：")
        data = spec.model.model_validate(data).model_dump(
            mode="json", exclude_unset=True
        )
    return data


def _baseline(args, client, spec):
    if getattr(args, "base_revision", None) is not None:
        if args.base_revision < 0:
            raise CLIError("input", "版本号不能为负数")
        return args.base_revision
    manifest = courses.load_manifest(args.course_dir, client.server, args.course_bid)
    if spec.handler == "metadata":
        return manifest["course"]["revision"]
    entry = next(
        (
            item
            for item in manifest["lessons"]
            if item["outline_bid"] == args.outline_bid
        ),
        None,
    )
    if not entry:
        raise CLIError("input", "该课时未绑定到课程目录，请先拉取")
    return entry["revision"]


def execute(args, client):
    if args.command == "inbox":
        return client.request("GET", "/api/inbox")
    if args.command == "doctor":
        health = client.request("GET", "/api/health")
        me = client.request("GET", "/api/auth/me")
        online = client.request("GET", "/api/platform/online-status")
        return {
            "package_version": version("ai-shifu-for-school-cli"),
            "skills": list_skills(),
            "health": health,
            "user": me["user"],
            "online": online,
        }
    if args.command == "api":
        validate_path(args.path)
        data = read_json(args.data) if args.data else None
        query = read_json(args.query) if args.query else None
        if query is not None and not isinstance(query, dict):
            raise CLIError("input", "--query 必须是 JSON 对象")
        if args.dry_run:
            return {
                "dry_run": True,
                "method": args.method,
                "path": args.path,
                "data": data,
                "query": query,
            }
        return client.request(
            args.method, args.path, data, params=query, stream=args.stream
        )
    spec = args.spec
    handler = spec.handler
    if handler in {"pull", "status", "save", "create_directory"}:
        if handler == "pull":
            return courses.pull(
                client, args.course_bid, args.course_dir, dry_run=args.dry_run
            )
        if handler == "status":
            return courses.status(client, args.course_dir)
        return getattr(courses, handler)(client, args.course_dir, dry_run=args.dry_run)
    data = _body(args, spec)
    path = spec.path.format(**{name: getattr(args, name) for name in spec.arguments})
    query = read_json(args.query) if args.query else None
    if query is not None and not isinstance(query, dict):
        raise CLIError("input", "--query 必须是 JSON 对象")
    if handler == "login":
        if args.dry_run:
            return {
                "dry_run": True,
                "method": "POST",
                "path": path,
                "username": args.username,
            }
        from .schemas import Credentials

        data = Credentials(
            username=args.username, password=getpass.getpass("密码：")
        ).model_dump()
    elif handler == "metadata":
        if args.course_prompt_file:
            if "system_prompt" in data:
                raise CLIError(
                    "input",
                    "--data 中的 system_prompt 与 --course-prompt-file 不能同时提供",
                )
            data["system_prompt"] = args.course_prompt_file.read_text(encoding="utf-8")
        return courses.update_metadata(
            client,
            args.course_bid,
            data,
            _baseline(args, client, spec),
            dry_run=args.dry_run,
        )
    elif handler == "content":
        return courses.update_content(
            client,
            args.course_bid,
            args.outline_bid,
            args.file.read_text(encoding="utf-8"),
            _baseline(args, client, spec),
            dry_run=args.dry_run,
        )
    elif handler == "variables":
        if spec.method == "GET":
            query = {**(query or {}), "parent_id": args.course_bid}
        else:
            if data.get("parent_id", args.course_bid) != args.course_bid:
                raise CLIError("input", "变量所属课程与目标课程不一致")
            data["parent_id"] = args.course_bid
    elif handler == "debug":
        query = {**(query or {}), "preview_mode": "true"}
    if args.dry_run:
        preview = {
            "dry_run": True,
            "method": spec.method,
            "path": path,
            "data": data,
            "query": query,
        }
        if handler == "upload":
            if not args.file.is_file():
                raise CLIError("input", "上传文件不存在")
            preview["file"] = str(args.file)
        return preview
    if handler == "upload":
        with args.file.open("rb") as handle:
            return client.request(
                spec.method,
                path,
                data,
                files={
                    "file": (
                        args.file.name,
                        handle,
                        mimetypes.guess_type(args.file.name)[0]
                        or "application/octet-stream",
                    )
                },
            )
    result = client.request(
        spec.method,
        path,
        data if spec.method != "GET" else None,
        params=query,
        stream=handler == "debug",
    )
    if handler == "logout":
        client.session_file.unlink(missing_ok=True)
    if handler == "submissions":
        return result["submissions"]
    return result


def main(argv=None):
    client = None
    args = None
    try:
        parser, leaves = build_parser()
        args = parser.parse_args(argv)
        if args.command == "schema":
            name = " ".join(args.name).replace(".", " ")
            if name and name not in BY_NAME:
                raise CLIError("input", "命令不存在；不带参数运行 schema 查看全部命令")
            selected = [BY_NAME[name]] if name else COMMANDS
            result = []
            for spec in selected:
                item = spec.schema()
                item["options"] = [
                    {
                        "flags": action.option_strings,
                        "required": action.required,
                        "help": action.help,
                    }
                    for action in leaves[spec.name]._actions
                    if action.option_strings
                ]
                result.append(item)
            result = result[0] if name else result
        elif args.command == "skills":
            if args.skill_action == "read":
                print(read_skill(args.name, args.reference))
                return 0
            result = (
                list_skills()
                if args.skill_action == "list"
                else install_skills(args.dest, dry_run=args.dry_run)
            )
        elif args.command == "setup":
            result = setup(
                server=args.server, session_file=args.session_file, dry_run=args.dry_run
            )
        elif args.command == "config":
            if args.config_action == "init":
                result = initialize(server=args.server, dry_run=args.dry_run)
            elif args.config_action == "set-server":
                result = set_server(args.url, dry_run=args.dry_run)
            else:
                result = show_config(args.server)
        else:
            fresh = getattr(getattr(args, "spec", None), "handler", "") == "login"
            client = SchoolClient(
                resolve_server(args.server, dry_run=args.dry_run),
                args.session_file,
                fresh=fresh,
            )
            result = execute(args, client)
        if not (client and client.streamed):
            print(
                json.dumps(
                    {"ok": True, "data": redact(result)}, ensure_ascii=False, indent=2
                )
            )
        return 0
    except ValidationError as exc:
        error = CLIError(
            "input",
            "输入字段不符合要求",
            details=exc.errors(
                include_input=False, include_context=False, include_url=False
            ),
        )
    except CLIError as exc:
        error = exc
    except (ValueError, OSError, KeyError, TypeError, IndexError) as exc:
        # Do not echo JSON decode snippets or credentials from user input.
        error = CLIError(
            "input",
            f"输入或本地文件无效（{type(exc).__name__}）；请用 schema 或 --help 核对",
        )
    finally:
        if client:
            client.close()
    stream = bool(
        args
        and (
            getattr(args, "stream", False)
            or getattr(getattr(args, "spec", None), "handler", "") == "debug"
        )
    )
    print(
        json.dumps(
            {"ok": False, "error": error.as_dict()}, ensure_ascii=False, indent=2
        ),
        file=sys.stderr if stream else sys.stdout,
    )
    return 1


if __name__ == "__main__":
    raise SystemExit(main())
