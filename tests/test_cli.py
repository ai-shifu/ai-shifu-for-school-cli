import io
import json
from pathlib import Path

import httpx
import pytest

from school_cli import cli
from school_cli.cli_client import CLIError, SchoolClient
from school_cli.cli_commands import COMMANDS
from school_cli.cli_skills import install_skills, list_skills, read_skill


@pytest.fixture
def runner(tmp_path, monkeypatch, capsys):
    calls = []

    def handler(request):
        calls.append(request)
        raise AssertionError("offline preview must not contact a school service")

    monkeypatch.setattr(
        cli,
        "SchoolClient",
        lambda server, session_file, **kwargs: SchoolClient(
            server, session_file, transport=httpx.MockTransport(handler), **kwargs
        ),
    )

    def run(*arguments, succeeds=True):
        code = cli.main(
            [
                "--server",
                "http://127.0.0.1",
                "--session-file",
                str(tmp_path / "cookies"),
                *map(str, arguments),
            ]
        )
        output = json.loads(capsys.readouterr().out)
        assert code == (0 if succeeds else 1)
        assert output["ok"] is succeeds
        return output.get("data") if succeeds else output["error"]

    return run, calls, None, None, None


def test_dry_run_and_invalid_inputs_never_contact_platform(
    runner, tmp_path, monkeypatch
):
    run, calls, _, _, _ = runner
    preview = run("class", "create", "--name", "只预览", "--dry-run")
    assert preview["dry_run"] and not calls
    preview = run(
        "student",
        "create",
        "--username",
        "new_student",
        "--display-name",
        "学生",
        "--dry-run",
    )
    assert preview["data"]["password"] == "[redacted]" and not calls
    assert (
        run(
            "activity",
            "create",
            1,
            "--class-id",
            1,
            "--kind",
            "discussion",
            "--title",
            "无效类型",
            succeeds=False,
        )["kind"]
        == "input"
    )
    assert run("class", "members", "../1", succeeds=False)["kind"] == "input"
    assert (
        run("api", "POST", "/api/%2e%2e/auth/login", "--dry-run", succeeds=False)[
            "kind"
        ]
        == "input"
    )
    assert (
        run(
            "online",
            "lesson",
            "update",
            "bid",
            "outline",
            "--file",
            "missing.md",
            succeeds=False,
        )["kind"]
        == "input"
    )
    assert not calls
    payload = tmp_path / "request.json"
    payload.write_text('{"name":"文件班级"}', encoding="utf-8")
    assert (
        run("class", "create", "--data", "@" + str(payload), "--dry-run")["data"][
            "name"
        ]
        == "文件班级"
    )
    monkeypatch.setattr("sys.stdin", io.StringIO('{"name":"标准输入"}'))
    assert (
        run("class", "create", "--data", "@-", "--dry-run")["data"]["name"]
        == "标准输入"
    )
    assert not calls


@pytest.mark.parametrize(
    "status,body,kind",
    [
        (200, {"code": 4007, "message": "draft conflict"}, "conflict"),
        (200, {"code": 1004, "message": "login required"}, "authentication"),
        (403, {"detail": "forbidden"}, "permission"),
        (422, {"detail": [{"input": "private-password"}]}, "input"),
        (503, {"detail": "offline"}, "service"),
    ],
)
def test_transport_business_errors(status, body, kind, tmp_path):
    requests = []

    def handle(request):
        requests.append(request)
        return httpx.Response(status, json=body)

    client = SchoolClient(
        "http://127.0.0.1", tmp_path / "session", transport=httpx.MockTransport(handle)
    )
    try:
        with pytest.raises(CLIError) as result:
            client.request("GET", "/api/test")
        assert result.value.kind == kind
        assert "private-password" not in str(result.value)
        assert len(requests) == 1
    finally:
        client.close()


def test_sse_uses_csrf_and_preserves_utf8(tmp_path, capsys):
    seen = []

    def handle(request):
        seen.append(request)
        if request.url.path == "/api/auth/me":
            return httpx.Response(200, json={"csrf_token": "csrf"})
        assert request.headers["x-csrf-token"] == "csrf"
        return httpx.Response(
            200,
            headers={"content-type": "text/event-stream"},
            content='event: message\ndata: {"text":"平均分"}\n\nevent: end\ndata: {}\n\n'.encode(),
        )

    client = SchoolClient(
        "http://127.0.0.1", tmp_path / "session", transport=httpx.MockTransport(handle)
    )
    try:
        assert (
            client.request(
                "PUT", "/api/online/learn/shifu/bid/run/lesson", {}, stream=True
            )
            is None
        )
        assert "平均分" in capsys.readouterr().out
        assert len(seen) == 2
    finally:
        client.close()


def test_network_write_is_not_retried(tmp_path):
    writes = []

    def handle(request):
        if request.method == "GET":
            return httpx.Response(200, json={"csrf_token": "csrf"})
        writes.append(request)
        raise httpx.ReadTimeout("timeout")

    client = SchoolClient(
        "http://127.0.0.1", tmp_path / "session", transport=httpx.MockTransport(handle)
    )
    try:
        with pytest.raises(CLIError) as result:
            client.request("POST", "/api/classes", {"name": "class"})
        assert result.value.kind == "network"
        assert len(writes) == 1
    finally:
        client.close()


def test_skills_are_self_contained_and_install_conflicts_are_atomic(tmp_path):
    names = list_skills()
    assert len(names) == 5
    assert "课程提示词" in read_skill(
        "school-online-course", "references/course-prompt.md"
    )
    target = tmp_path / "skills"
    assert install_skills(target, dry_run=True)["dry_run"]
    assert not target.exists()
    install_skills(target)
    install_skills(target)
    changed = target / names[-1] / "SKILL.md"
    changed.write_text("本地版本", encoding="utf-8")
    missing = target / names[0] / "SKILL.md"
    missing.unlink()
    with pytest.raises(CLIError) as result:
        install_skills(target)
    assert result.value.kind == "conflict"
    assert changed.read_text(encoding="utf-8") == "本地版本"
    assert not missing.exists()
    with pytest.raises(CLIError):
        read_skill("school-online-course", "../../../../pyproject.toml")
    for path in Path("skills").rglob("*.md"):
        import re

        for link in re.findall(r"\]\(([^)]+)\)", path.read_text(encoding="utf-8")):
            assert not link.startswith("/")
            if "://" not in link:
                assert (path.parent / link).is_file(), (path, link)


def test_schema_has_every_business_command_and_required_input(capsys):
    assert cli.main(["schema"]) == 0
    schema = json.loads(capsys.readouterr().out)["data"]
    assert len(schema) == len(COMMANDS)
    assert cli.main(["schema", "activity.create"]) == 0
    schema = json.loads(capsys.readouterr().out)["data"]
    assert "class_id" in schema["input"]["required"]
    assert set(schema["input"]["properties"]["kind"]["enum"]) == {
        "attendance",
        "rollcall",
        "exercise",
        "homework",
    }


def test_optional_metadata_fields_are_not_reset_and_variables_stay_scoped(runner):
    run, calls, _, _, _ = runner
    result = run(
        "online", "update", "bid", "--base-revision", 7, "--name", "新标题", "--dry-run"
    )
    assert result["data"] == {"name": "新标题"}
    result = run(
        "online",
        "update",
        "bid",
        "--base-revision",
        7,
        "--ask-enabled-status",
        "5102",
        "--dry-run",
    )
    assert result["data"] == {"ask_enabled_status": 5102}
    error = run(
        "online",
        "variable",
        "create",
        "bid",
        "--profile-key",
        "目标",
        "--parent-id",
        "foreign",
        "--dry-run",
        succeeds=False,
    )
    assert error["kind"] == "input"
    assert not calls


def test_stream_error_is_failure_without_corrupting_sse(tmp_path, capsys):
    def handle(request):
        return httpx.Response(
            200,
            headers={"content-type": "text/event-stream"},
            content=b'data: {"type":"error","message":"failed"}\n\n',
        )

    client = SchoolClient(
        "http://127.0.0.1", tmp_path / "session", transport=httpx.MockTransport(handle)
    )
    try:
        with pytest.raises(CLIError) as result:
            client.request("GET", "/api/test", stream=True)
        assert result.value.kind == "service"
        assert capsys.readouterr().out.startswith('data: {"type":"error"')
    finally:
        client.close()


def test_null_business_result_still_emits_success_json(tmp_path, monkeypatch, capsys):
    def handle(request):
        if request.url.path == "/api/auth/me":
            return httpx.Response(200, json={"csrf_token": "csrf"})
        return httpx.Response(200, json={"code": 0, "data": None})

    monkeypatch.setattr(
        cli,
        "SchoolClient",
        lambda server, session_file, **kwargs: SchoolClient(
            server, session_file, transport=httpx.MockTransport(handle)
        ),
    )
    assert (
        cli.main(
            [
                "--server",
                "http://127.0.0.1:8766",
                "--session-file",
                str(tmp_path / "cookies"),
                "online",
                "outline",
                "delete",
                "course",
                "outline",
            ]
        )
        == 0
    )
    assert json.loads(capsys.readouterr().out) == {"ok": True, "data": None}
