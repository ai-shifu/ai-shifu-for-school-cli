import io
import json

import httpx

from school_cli import cli, cli_config, onboarding
from school_cli.cli_client import SchoolClient


class Terminal(io.StringIO):
    def isatty(self):
        return True


def test_setup_installs_skills_and_verifies_account(tmp_path, monkeypatch, capsys):
    monkeypatch.setattr(onboarding.Path, "home", lambda: tmp_path)
    monkeypatch.setattr("sys.stdin", Terminal())
    answers = iter(["school.example", "1", "teacher.with.dot"])
    monkeypatch.setattr("builtins.input", lambda _: next(answers))
    monkeypatch.setattr(
        onboarding.getpass, "getpass", lambda _: "FixtureOnlyPassword!2026"
    )
    requests = []

    def handler(request):
        requests.append(request)
        if request.method == "POST":
            assert json.loads(request.content)["username"] == "teacher.with.dot"
        return httpx.Response(
            200,
            json={
                "user": {"username": "teacher.with.dot", "role": "teacher"},
                "csrf_token": "fixture-csrf",
            },
        )

    monkeypatch.setattr(
        onboarding,
        "SchoolClient",
        lambda server, session_file, **kwargs: SchoolClient(
            server, session_file, transport=httpx.MockTransport(handler), **kwargs
        ),
    )
    assert cli.main(["setup"]) == 0
    result = json.loads(capsys.readouterr().out)["data"]
    assert result["completed"] == ["server_configured", "skills_installed", "signed_in"]
    assert result["user"]["role"] == "teacher"
    assert "FixtureOnlyPassword" not in json.dumps(result)
    assert len(list((tmp_path / ".codex/skills").glob("*/SKILL.md"))) == 5
    assert cli_config.resolve_server() == "https://school.example"
    assert [request.url.path for request in requests] == [
        "/api/auth/login",
        "/api/auth/me",
    ]


def test_noninteractive_setup_and_preview_do_not_write(tmp_path, monkeypatch, capsys):
    monkeypatch.setattr(onboarding.Path, "home", lambda: tmp_path)
    monkeypatch.setattr("sys.stdin", io.StringIO())
    assert cli.main(["setup", "--dry-run"]) == 0
    assert json.loads(capsys.readouterr().out)["data"]["dry_run"]
    assert cli.main(["setup"]) == 1
    assert json.loads(capsys.readouterr().out)["error"]["kind"] == "configuration"
    assert not list(tmp_path.iterdir())


def test_login_failure_preserves_completed_setup(tmp_path, monkeypatch, capsys):
    monkeypatch.setattr(onboarding.Path, "home", lambda: tmp_path)
    monkeypatch.setattr("sys.stdin", Terminal())
    answers = iter(["school.example", "3", "teacher_demo"])
    monkeypatch.setattr("builtins.input", lambda _: next(answers))
    monkeypatch.setattr(
        onboarding.getpass, "getpass", lambda _: "FixtureOnlyPassword!2026"
    )
    transport = httpx.MockTransport(
        lambda request: httpx.Response(401, json={"detail": "账号或密码不正确"})
    )
    monkeypatch.setattr(
        onboarding,
        "SchoolClient",
        lambda server, session_file, **kwargs: SchoolClient(
            server, session_file, transport=transport, **kwargs
        ),
    )
    assert cli.main(["setup"]) == 1
    error = json.loads(capsys.readouterr().out)["error"]
    assert error["kind"] == "authentication"
    assert error["details"]["completed"] == ["server_configured"]
    assert cli_config.resolve_server() == "https://school.example"
    assert not (tmp_path / ".codex").exists()
