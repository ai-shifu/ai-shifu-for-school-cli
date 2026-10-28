import json
from pathlib import Path

import pytest

from school_cli import cli_courses as courses
from school_cli.cli_client import CLIError


class CourseService:
    """Deterministic course API double; it never calls a model or live instance."""

    server = "http://127.0.0.1:9999"

    def __init__(self):
        self.calls = []
        self.detail = {
            "name": "原课程",
            "description": "介绍",
            "system_prompt": "课程提示词",
        }
        self.number = 1
        self.outlines = {}
        self.fail_write = None
        self.write_count = 0

    def request(self, method, path, data=None, *, params=None):
        self.calls.append((method, path, data))
        if method != "GET":
            self.write_count += 1
            if self.write_count == self.fail_write:
                raise CLIError("network", "模拟连接中断")
            self.number += 1
        if path == "/api/online/shifu/shifus":
            self.detail.update(data)
            self.outlines = {
                "default_chapter": {
                    "bid": "default_chapter",
                    "name": "Untitled Chapter",
                    "parent_bid": "",
                    "revision": self.number,
                    "versions": {},
                    "content": "",
                },
                "default_lesson": {
                    "bid": "default_lesson",
                    "name": "Untitled Lesson",
                    "parent_bid": "default_chapter",
                    "revision": self.number,
                    "versions": {self.number: ""},
                    "content": "",
                },
            }
            return {"bid": "course1"}
        suffix = path.removeprefix(courses.course_path("course1"))
        if suffix == "/detail":
            if method == "POST":
                self.detail.update(data)
            return dict(self.detail)
        if suffix == "/draft-meta":
            outline = (params or {}).get("outline_bid")
            return {
                "revision": self.outlines[outline]["revision"]
                if outline
                else self.number
            }
        if suffix == "/outlines":
            if method == "PUT":
                bid = "outline" + str(len(self.outlines) + 1)
                self.outlines[bid] = {
                    "bid": bid,
                    "name": data["name"],
                    "parent_bid": data.get("parent_bid", ""),
                    "content": "",
                    "revision": self.number,
                    "versions": {self.number: ""},
                }
                return {"bid": bid}
            return [
                {
                    **node,
                    "children": [
                        dict(child)
                        for child in self.outlines.values()
                        if child["parent_bid"] == node["bid"]
                    ],
                }
                for node in self.outlines.values()
                if not node["parent_bid"]
            ]
        segments = suffix.strip("/").split("/")
        if segments[0] == "outlines":
            node = self.outlines[segments[1]]
            if len(segments) == 2 and method == "POST":
                node["name"] = data["name"]
                return {"bid": node["bid"]}
            if "history" in segments:
                number = int(segments[-1])
                return {"version_id": number, "content": node["versions"][number]}
            if method == "POST":
                if node["revision"] != data["base_revision"]:
                    raise CLIError("conflict", "draft conflict")
                node.update(content=data["data"], revision=self.number)
                node["versions"][self.number] = data["data"]
                return {"new_revision": self.number}
            return node["content"]
        raise AssertionError((method, path, data))


def author_directory(root):
    (root / "lessons").mkdir(parents=True)
    (root / "README.md").write_text("# 分数入门\n", encoding="utf-8")
    (root / "course-description.md").write_text("理解平均分", encoding="utf-8")
    (root / "course-prompt.md").write_text("按课时目标授课", encoding="utf-8")
    (root / "lessons/lesson-01.md").write_text(
        "解释二分之一和平均分。", encoding="utf-8"
    )
    (root / "structure.json").write_text(
        json.dumps(
            {
                "chapters": [
                    {
                        "title": "分数",
                        "lessons": [{"title": "二分之一", "file": "lesson-01.md"}],
                    }
                ]
            },
            ensure_ascii=False,
        ),
        encoding="utf-8",
    )
    return root


def test_create_pull_edit_save_keeps_ids_and_stops_stale_writes(tmp_path):
    source = author_directory(tmp_path / "authored")
    client = CourseService()
    assert courses.create_directory(client, source, dry_run=True)["publish"] is False
    assert not client.calls and not (source / ".school-create.json").exists()
    created = courses.create_directory(client, source)
    assert created["course_bid"] == "course1" and not created["published"]
    assert len(client.outlines) == 2
    assert client.outlines["default_chapter"]["name"] == "分数"
    assert courses.status(client, source)["clean"]
    original_ids = set(client.outlines)
    target = tmp_path / "pulled"
    courses.pull(client, "course1", target)
    assert (target / "lessons/lesson-01.md").read_text(
        encoding="utf-8"
    ) == "解释二分之一和平均分。"
    (target / "course-prompt.md").write_text("新增共享表达要求", encoding="utf-8")
    (target / "lessons/lesson-01.md").write_text(
        "解释平均分，并用折纸演示。", encoding="utf-8"
    )
    before = client.write_count
    assert courses.save(client, target, dry_run=True)["remote_writes"] is False
    assert client.write_count == before
    saved = courses.save(client, target)
    assert len(saved["completed"]) == 2
    assert set(client.outlines) == original_ids
    assert client.detail["system_prompt"] == "新增共享表达要求"
    assert courses.status(client, target)["clean"]
    (target / "lessons/lesson-01.md").write_text("保留本地修改", encoding="utf-8")
    client.number += 1
    before = client.write_count
    with pytest.raises(CLIError) as result:
        courses.save(client, target)
    assert result.value.kind == "conflict"
    assert client.write_count == before
    assert (target / "lessons/lesson-01.md").read_text(
        encoding="utf-8"
    ) == "保留本地修改"


def test_pull_backups_and_wrong_service_fail_before_requests(tmp_path):
    source = author_directory(tmp_path / "authored")
    client = CourseService()
    courses.create_directory(client, source)
    (source / "lessons/lesson-01.md").write_text("本地未保存", encoding="utf-8")
    pulled = courses.pull(client, "course1", source)
    assert any(
        Path(path).read_text(encoding="utf-8") == "本地未保存"
        for path in pulled["backups"]
    )
    manifest = json.loads((source / courses.MANIFEST).read_text())
    manifest["server"] = "https://another-school.example"
    (source / courses.MANIFEST).write_text(json.dumps(manifest))
    before = len(client.calls)
    with pytest.raises(CLIError):
        courses.pull(client, "course1", source)
    assert len(client.calls) == before


def test_pull_checks_complete_snapshot_before_local_writes(tmp_path):
    source = author_directory(tmp_path / "authored")
    client = CourseService()
    courses.create_directory(client, source)
    original = client.request

    def invalid_history(method, path, data=None, **kwargs):
        if "/history/" in path:
            return {"version_id": -1, "content": "错误快照"}
        return original(method, path, data, **kwargs)

    client.request = invalid_history
    destination = tmp_path / "untouched"
    with pytest.raises(CLIError):
        courses.pull(client, "course1", destination)
    assert not destination.exists()


def test_create_connection_loss_records_pending_and_never_duplicates(tmp_path):
    source = author_directory(tmp_path / "authored")
    client = CourseService()
    client.fail_write = 3
    with pytest.raises(CLIError) as result:
        courses.create_directory(client, source)
    assert result.value.kind == "network"
    assert "course" in result.value.details["completed"]
    journal = json.loads((source / ".school-create.json").read_text())
    assert journal["pending"] == "chapter:0"
    count = client.write_count
    with pytest.raises(CLIError) as result:
        courses.create_directory(client, source)
    assert result.value.kind == "conflict"
    assert client.write_count == count


def test_structure_changes_and_path_escape_are_rejected(tmp_path):
    source = author_directory(tmp_path / "authored")
    client = CourseService()
    structure = json.loads((source / "structure.json").read_text())
    structure["chapters"][0]["lessons"][0]["file"] = "../../outside.md"
    (source / "structure.json").write_text(json.dumps(structure))
    with pytest.raises(CLIError):
        courses.create_directory(client, source)
    assert not client.calls
    author_directory(tmp_path / "second")
    source = tmp_path / "second"
    courses.create_directory(client, source)
    (source / "structure.json").write_text('{"chapters":[]}', encoding="utf-8")
    before = client.write_count
    with pytest.raises(CLIError):
        courses.save(client, source)
    assert client.write_count == before


def test_content_preflight_and_business_conflict_preserve_local_file(tmp_path):
    client = CourseService()
    source = author_directory(tmp_path / "authored")
    courses.create_directory(client, source)
    manifest = courses.load_manifest(source, client.server)
    lesson = manifest["lessons"][0]
    original = client.request

    def conflict(method, path, data=None, **kwargs):
        if method == "POST" and path.endswith("/mdflow"):
            raise CLIError("conflict", "业务错误码4007")
        return original(method, path, data, **kwargs)

    client.request = conflict
    with pytest.raises(CLIError) as result:
        courses.update_content(
            client, "course1", lesson["outline_bid"], "本地修改", lesson["revision"]
        )
    assert result.value.kind == "conflict"
    assert (source / "lessons/lesson-01.md").read_text(
        encoding="utf-8"
    ) == "解释二分之一和平均分。"
