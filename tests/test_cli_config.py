import io
import json
import os
import stat

import httpx
import pytest

from school_cli import cli, cli_config
from school_cli.cli_client import CLIError, SchoolClient


@pytest.fixture
def config_file(tmp_path, monkeypatch):
    path = tmp_path / "user-config/.env"
    monkeypatch.setattr(cli_config, "env_path", lambda: path)
    monkeypatch.delenv(cli_config.SERVER_KEY, raising=False)
    return path


class Terminal(io.StringIO):
    def isatty(self):
        return True


def test_first_network_command_prompts_once_then_reuses_local_env(
    config_file, monkeypatch, tmp_path, capsys
):
    prompts = []
    destinations = []
    monkeypatch.setattr("sys.stdin", Terminal())

    def answer(prompt):
        prompts.append(prompt)
        return "school.dev.pillowai.cn"

    monkeypatch.setattr("builtins.input", answer)

    def handler(request):
        destinations.append(str(request.url))
        return httpx.Response(200, json=[])

    monkeypatch.setattr(
        cli,
        "SchoolClient",
        lambda server, session_file, **kwargs: SchoolClient(
            server, session_file, transport=httpx.MockTransport(handler)
        ),
    )
    arguments = ["--session-file", str(tmp_path / "cookies"), "class", "list"]
    assert cli.main(arguments) == 0
    assert json.loads(capsys.readouterr().out)["ok"]
    assert len(prompts) == 1
    assert (
        config_file.read_text()
        == 'SCHOOL_SERVER_URL="https://school.dev.pillowai.cn"\n'
    )
    if os.name != "nt":
        assert stat.S_IMODE(config_file.stat().st_mode) == 0o600
    assert cli.main(arguments) == 0
    assert json.loads(capsys.readouterr().out)["ok"]
    assert len(prompts) == 1
    assert destinations == ["https://school.dev.pillowai.cn/api/classes"] * 2


def test_precedence_is_explicit_then_process_then_local_env(config_file, monkeypatch):
    cli_config.set_server("https://saved.example")
    assert cli_config.resolve_server() == "https://saved.example"
    monkeypatch.setenv("SCHOOL_SERVER_URL", "https://process.example")
    assert cli_config.resolve_server() == "https://process.example"
    assert cli_config.resolve_server("https://once.example") == "https://once.example"
    assert "https://saved.example" in config_file.read_text()


def test_working_directory_env_cannot_select_a_different_school(
    config_file, tmp_path, monkeypatch
):
    monkeypatch.chdir(tmp_path)
    (tmp_path / ".env").write_text('SCHOOL_SERVER_URL="https://unrelated.example"\n')
    assert cli_config.configured_server() == (None, None)
    config_file.parent.mkdir()
    config_file.write_text("OTHER_VALUE=only\n")
    with pytest.raises(CLIError) as error:
        cli_config.resolve_server()
    assert error.value.kind == "configuration"


def test_configuration_preserves_other_env_lines_and_dry_run_never_writes(config_file):
    preview = cli_config.set_server("school.dev.pillowai.cn", dry_run=True)
    assert preview["dry_run"] and not config_file.exists()
    config_file.parent.mkdir()
    config_file.write_text(
        '# local preferences\nOTHER_VALUE="keep me"\nexport SCHOOL_SERVER_URL="https://old.example"\nSCHOOL_SERVER_URL="https://duplicate.example"\n'
    )
    cli_config.set_server("https://school.dev.pillowai.cn/")
    content = config_file.read_text()
    assert content.count("SCHOOL_SERVER_URL=") == 1
    assert 'OTHER_VALUE="keep me"' in content
    assert "# local preferences" in content


@pytest.mark.parametrize(
    "value",
    [
        "https://school.dev.pillowai.cn/classroom",
        "https://school.dev.pillowai.cn/classroom/",
        "https://user:password@school.example",
        "http://remote.example",
        "https://school.example?token=secret",
        "https://school.example/#fragment",
        "",
    ],
)
def test_invalid_server_does_not_overwrite_saved_configuration(config_file, value):
    cli_config.set_server("https://saved.example")
    original = config_file.read_bytes()
    with pytest.raises(CLIError):
        cli_config.set_server(value)
    assert config_file.read_bytes() == original


def test_noninteractive_missing_config_and_previews_do_not_hang(
    config_file, monkeypatch, capsys
):
    monkeypatch.setattr("sys.stdin", io.StringIO())
    assert cli.main(["class", "list"]) == 1
    assert json.loads(capsys.readouterr().out)["error"]["kind"] == "configuration"
    assert cli.main(["class", "create", "--name", "预览", "--dry-run"]) == 1
    assert not config_file.exists()
    assert json.loads(capsys.readouterr().out)["error"]["kind"] == "configuration"
    assert cli.main(["schema", "class", "create"]) == 0
    assert json.loads(capsys.readouterr().out)["ok"]
    assert cli.main(["skills", "list"]) == 0
    assert json.loads(capsys.readouterr().out)["ok"]
    assert not config_file.exists()


def test_config_commands_work_offline(config_file, monkeypatch, capsys):
    monkeypatch.setattr("sys.stdin", Terminal())
    monkeypatch.setattr("builtins.input", lambda _: "school.dev.pillowai.cn")
    assert cli.main(["config", "init"]) == 0
    assert (
        json.loads(capsys.readouterr().out)["data"]["server"]
        == "https://school.dev.pillowai.cn"
    )
    assert cli.main(["config", "show"]) == 0
    assert json.loads(capsys.readouterr().out)["data"]["source"] == "env_file"
    assert cli.main(["config", "set-server", "http://127.0.0.1:3030", "--dry-run"]) == 0
    assert json.loads(capsys.readouterr().out)["data"]["dry_run"]
    assert cli_config.resolve_server() == "https://school.dev.pillowai.cn"


def test_empty_or_cancelled_prompt_does_not_write(config_file, monkeypatch):
    monkeypatch.setattr("sys.stdin", Terminal())
    monkeypatch.setattr("builtins.input", lambda _: "  ")
    with pytest.raises(CLIError):
        cli_config.initialize()
    assert not config_file.exists()
    monkeypatch.setattr("builtins.input", lambda _: (_ for _ in ()).throw(EOFError()))
    with pytest.raises(CLIError):
        cli_config.initialize()
    assert not config_file.exists()
