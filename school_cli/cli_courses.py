"""School-owned course files and version-aware writes; no official CLI dependency."""

import hashlib
import json
import re
import uuid
from pathlib import Path

from .cli_client import CLIError, atomic_text

MANIFEST = ".school-sync.json"


def digest(text):
    return hashlib.sha256(text.encode("utf-8")).hexdigest()


def identifier(value):
    if not isinstance(value, str) or not re.fullmatch(r"[A-Za-z0-9_-]+", value):
        raise CLIError("input", "资源 ID 只能包含字母、数字、下划线和连字符")
    return value


def course_path(bid):
    return "/api/online/shifu/shifus/" + identifier(bid)


def local_path(root, relative):
    root = Path(root).resolve()
    dest = (root / relative).resolve()
    if dest == root or not dest.is_relative_to(root):
        raise CLIError("input", "课程文件路径不能越出课程目录")
    return dest


def write_json(path, value):
    atomic_text(path, json.dumps(value, ensure_ascii=False, indent=2) + "\n")


def revision(client, bid, outline=None):
    result = client.request(
        "GET",
        course_path(bid) + "/draft-meta",
        params={"outline_bid": outline} if outline else None,
    )
    value = result.get("revision") if isinstance(result, dict) else None
    if type(value) is not int or value < 0:
        raise CLIError("service", "平台没有返回有效版本号；停止保存，请重新拉取")
    return value


def load_manifest(root, server, bid=None):
    path = local_path(root, MANIFEST)
    if not path.is_file():
        raise CLIError(
            "input", "目录尚未绑定学校课程，请先 online pull 或 create-from-dir"
        )
    value = json.loads(path.read_text(encoding="utf-8"))
    if (
        not isinstance(value, dict)
        or value.get("schema_version") != 1
        or value.get("server") != server
        or (bid is not None and value.get("course_bid") != bid)
    ):
        raise CLIError("input", "课程目录的平台或课程身份不匹配；不会自动切换目标")
    identifier(value.get("course_bid"))
    if not isinstance(value.get("course"), dict) or not isinstance(
        value.get("lessons"), list
    ):
        raise CLIError("input", "课程同步记录损坏，请使用新目录拉取")
    if type(value["course"].get("revision")) is not int:
        raise CLIError("input", "课程同步记录缺少版本基线")
    seen = set()
    for item in value["lessons"]:
        if not isinstance(item, dict) or type(item.get("revision")) is not int:
            raise CLIError("input", "课时同步记录缺少版本基线")
        identifier(item.get("outline_bid"))
        filename = item.get("file")
        if (
            not isinstance(filename, str)
            or not filename.startswith("lessons/")
            or filename in seen
        ):
            raise CLIError("input", "课时文件映射不合法或重复")
        local_path(root, filename)
        seen.add(filename)
    return value


def _flatten(tree):
    if not isinstance(tree, list):
        raise CLIError("service", "课程章节结构响应无效")
    flat = []

    def walk(nodes, parent=""):
        for node in nodes:
            if not isinstance(node, dict):
                raise CLIError("service", "课程章节节点无效")
            bid = identifier(node.get("bid"))
            children = node.get("children") or []
            if not isinstance(children, list):
                raise CLIError("service", "课程子节点列表无效")
            flat.append(
                {
                    "bid": bid,
                    "name": node.get("name", ""),
                    "parent_bid": parent,
                    "chapter": not parent or bool(children),
                }
            )
            walk(children, bid)

    walk(tree)
    return flat


def snapshot(client, bid):
    base = course_path(bid)
    before = revision(client, bid)
    detail = client.request("GET", base + "/detail")
    nodes = _flatten(client.request("GET", base + "/outlines"))
    for node in nodes:
        if node["chapter"]:
            continue
        number = revision(client, bid, node["bid"])
        version = client.request(
            "GET", base + f"/outlines/{node['bid']}/mdflow/history/{number}"
        )
        if (
            not isinstance(version, dict)
            or version.get("version_id") != number
            or not isinstance(version.get("content"), str)
        ):
            raise CLIError("service", "课时历史快照无效；本地文件未更新")
        node.update(content=version["content"], revision=number)
    if revision(client, bid) != before:
        raise CLIError("conflict", "读取期间课程已变化；本地文件未更新，请重新拉取")
    return detail, nodes, before


def pull(client, bid, root, *, dry_run=False):
    root = Path(root)
    existing = (
        load_manifest(root, client.server, bid) if (root / MANIFEST).exists() else None
    )
    detail, nodes, number = snapshot(client, bid)
    files = {
        "README.md": "# " + detail["name"] + "\n",
        "course-description.md": detail.get("description") or "",
        "course-prompt.md": detail.get("system_prompt") or "",
    }
    previous = (
        {item["outline_bid"]: item["file"] for item in existing["lessons"]}
        if existing
        else {}
    )
    used = set(previous.values())
    lessons = []
    structures = {
        n["bid"]: {"title": n["name"], "lessons": []} for n in nodes if n["chapter"]
    }
    for node in nodes:
        if node["chapter"]:
            continue
        filename = previous.get(node["bid"])
        if not filename:
            index = 1
            while f"lessons/lesson-{index:02d}.md" in used:
                index += 1
            filename = f"lessons/lesson-{index:02d}.md"
        used.add(filename)
        files[filename] = node["content"]
        lessons.append(
            {
                "outline_bid": node["bid"],
                "file": filename,
                "revision": node["revision"],
                "sha256": digest(node["content"]),
            }
        )
        if node["parent_bid"] not in structures:
            raise CLIError("service", "仅支持章节与课时两层课程结构")
        structures[node["parent_bid"]]["lessons"].append(
            {"title": node["name"], "file": filename.removeprefix("lessons/")}
        )
    files["structure.json"] = (
        json.dumps(
            {"chapters": [structures[n["bid"]] for n in nodes if n["chapter"]]},
            ensure_ascii=False,
            indent=2,
        )
        + "\n"
    )
    manifest = {
        "schema_version": 1,
        "server": client.server,
        "course_bid": bid,
        "course": {
            "revision": number,
            "name": detail["name"],
            "description": files["course-description.md"],
            "system_prompt": files["course-prompt.md"],
        },
        "lessons": lessons,
        "structure_sha256": digest(files["structure.json"]),
    }
    # Validate all paths before touching any file, including symlinked destinations.
    destinations = {name: local_path(root, name) for name in [*files, MANIFEST]}
    if dry_run:
        return {
            "dry_run": True,
            "course_bid": bid,
            "files": list(files),
            "remote_writes": False,
        }
    backups = []
    for filename, content in files.items():
        dest = destinations[filename]
        if dest.exists() and dest.read_text(encoding="utf-8") != content:
            backup = dest.with_name(dest.name + f".local-{uuid.uuid4().hex[:8]}.bak")
            atomic_text(backup, dest.read_text(encoding="utf-8"))
            backups.append(str(backup))
        atomic_text(dest, content)
    write_json(destinations[MANIFEST], manifest)
    return {
        "course_bid": bid,
        "course_dir": str(root),
        "lessons": len(lessons),
        "backups": backups,
    }


def authored_metadata(root):
    root = Path(root)
    title = local_path(root, "README.md").read_text(encoding="utf-8").splitlines()[0]
    if not title.startswith("#") or not title.lstrip("# ").strip():
        raise CLIError("input", "README.md 第一行必须是课程标题，如 # 分数入门")
    return {
        "name": title.lstrip("# ").strip(),
        "description": local_path(root, "course-description.md").read_text(
            encoding="utf-8"
        ),
        "system_prompt": local_path(root, "course-prompt.md").read_text(
            encoding="utf-8"
        ),
    }


def status(client, root):
    manifest = load_manifest(root, client.server)
    bid = manifest["course_bid"]
    changes = []
    if revision(client, bid) != manifest["course"]["revision"]:
        changes.append({"scope": "course", "remote_changed": True})
    for key, value in authored_metadata(root).items():
        if value != manifest["course"].get(key):
            changes.append({"scope": key, "local_changed": True})
    for item in manifest["lessons"]:
        changes.append(
            {
                "file": item["file"],
                "local_changed": digest(
                    local_path(root, item["file"]).read_text(encoding="utf-8")
                )
                != item["sha256"],
                "remote_changed": revision(client, bid, item["outline_bid"])
                != item["revision"],
            }
        )
    structure_changed = (
        digest((Path(root) / "structure.json").read_text(encoding="utf-8"))
        != manifest["structure_sha256"]
    )
    return {
        "course_bid": bid,
        "changes": changes,
        "structure_changed": structure_changed,
        "clean": not structure_changed
        and not any(c.get("local_changed") or c.get("remote_changed") for c in changes),
    }


def check_revision(client, bid, expected, outline=None):
    if type(expected) is not int or expected < 0:
        raise CLIError("input", "必须提供有效版本基线")
    if revision(client, bid, outline) != expected:
        raise CLIError(
            "conflict", "远端版本已变化；本地修改已保留，请在新目录拉取后合并再保存"
        )


def update_metadata(client, bid, payload, expected, *, dry_run=False):
    if not isinstance(payload, dict) or not payload:
        raise CLIError("input", "请提供要修改的课程字段")
    if dry_run:
        return {
            "dry_run": True,
            "method": "POST",
            "path": course_path(bid) + "/detail",
            "data": payload,
            "base_revision": expected,
        }
    check_revision(client, bid, expected)
    result = client.request("POST", course_path(bid) + "/detail", payload)
    return {
        "result": result,
        "concurrency": "course metadata uses a preflight check, not atomic compare-and-swap",
    }


def update_content(client, bid, outline, content, expected, *, dry_run=False):
    path = course_path(bid) + f"/outlines/{identifier(outline)}/mdflow"
    payload = {"data": content, "base_revision": expected}
    if dry_run:
        return {"dry_run": True, "method": "POST", "path": path, "data": payload}
    check_revision(client, bid, expected, outline)
    result = client.request("POST", path, payload)
    if not isinstance(result, dict) or type(result.get("new_revision")) is not int:
        raise CLIError(
            "service",
            "保存已请求，但新版本号未确认；请先查询状态",
            details={"outline_bid": outline},
        )
    saved = client.request("GET", path + f"/history/{result['new_revision']}")
    if not isinstance(saved, dict) or saved.get("content") != content:
        raise CLIError("service", "保存后正文读回不一致；请先核对远端，不要重试覆盖")
    return result


def save(client, root, *, dry_run=False):
    root = Path(root)
    manifest = load_manifest(root, client.server)
    bid = manifest["course_bid"]
    if (
        digest((root / "structure.json").read_text(encoding="utf-8"))
        != manifest["structure_sha256"]
    ):
        raise CLIError(
            "input",
            "save 只做定点内容更新；结构修改请使用 online outline 命令后重新拉取",
        )
    meta = {
        k: v
        for k, v in authored_metadata(root).items()
        if v != manifest["course"].get(k)
    }
    contents = [
        (item, local_path(root, item["file"]).read_text(encoding="utf-8"))
        for item in manifest["lessons"]
    ]
    pending = [
        (item, content)
        for item, content in contents
        if digest(content) != item["sha256"]
    ]
    if dry_run:
        return {
            "dry_run": True,
            "course_bid": bid,
            "metadata": meta,
            "lessons": [i["outline_bid"] for i, _ in pending],
            "remote_writes": False,
        }
    # Check every baseline before the first mutation. Later checks still protect each step.
    check_revision(client, bid, manifest["course"]["revision"])
    for item, _ in pending:
        check_revision(client, bid, item["revision"], item["outline_bid"])
    completed = []
    try:
        if meta:
            update_metadata(client, bid, meta, manifest["course"]["revision"])
            completed.append({"scope": "metadata"})
            manifest["course"].update(meta)
            # Keep the old course revision until all steps finish. A partial save
            # cannot accidentally bless an unrelated concurrent metadata update.
            write_json(local_path(root, MANIFEST), manifest)
        for item, content in pending:
            result = update_content(
                client, bid, item["outline_bid"], content, item["revision"]
            )
            completed.append(
                {"outline_bid": item["outline_bid"], "revision": result["new_revision"]}
            )
            item.update(revision=result["new_revision"], sha256=digest(content))
            write_json(local_path(root, MANIFEST), manifest)
        # Verify saved fields before advancing the preflight metadata baseline.
        detail = client.request("GET", course_path(bid) + "/detail")
        if any((detail.get(k) or "") != v for k, v in authored_metadata(root).items()):
            raise CLIError("conflict", "保存后课程字段与本地不一致；请拉取核对")
        manifest["course"]["revision"] = revision(client, bid)
        write_json(local_path(root, MANIFEST), manifest)
    except CLIError as exc:
        exc.details = {
            "course_bid": bid,
            "completed": completed,
            "next": "查询状态并合并版本后续做；不要重跑整课创建",
        }
        raise
    return {"course_bid": bid, "completed": completed}


def creation_inputs(root):
    root = Path(root)
    metadata = authored_metadata(root)
    structure = json.loads((root / "structure.json").read_text(encoding="utf-8"))
    if (
        not isinstance(structure, dict)
        or not isinstance(structure.get("chapters"), list)
        or not structure["chapters"]
    ):
        raise CLIError("input", "structure.json 必须包含非空 chapters 数组")
    seen = set()
    for chapter in structure["chapters"]:
        if (
            not isinstance(chapter, dict)
            or not isinstance(chapter.get("title"), str)
            or not chapter["title"].strip()
            or not isinstance(chapter.get("lessons"), list)
            or not chapter.get("lessons")
        ):
            raise CLIError("input", "每章必须有标题和至少一个课时")
        for lesson in chapter["lessons"]:
            if not isinstance(lesson, dict):
                raise CLIError("input", "课时定义必须是对象")
            filename = lesson.get("file")
            if (
                not isinstance(filename, str)
                or not isinstance(lesson.get("title"), str)
                or not lesson["title"].strip()
            ):
                raise CLIError("input", "每个课时必须提供 file 和 title")
            path = local_path(root / "lessons", filename)
            if not path.is_relative_to(root.resolve()):
                raise CLIError("input", "课时文件不能通过符号链接越出课程目录")
            if filename in seen:
                raise CLIError("input", "课时文件不能重复")
            seen.add(filename)
            lesson["content"] = path.read_text(encoding="utf-8")
    return metadata, structure


def create_directory(client, root, *, dry_run=False):
    root = Path(root)
    manifest_path = local_path(root, MANIFEST)
    if manifest_path.exists():
        load_manifest(root, client.server)
        raise CLIError("input", "目录已绑定课程，请使用 online save；不会新建替代课程")
    metadata, structure = creation_inputs(root)
    fingerprint = digest(
        json.dumps([metadata, structure], ensure_ascii=False, sort_keys=True)
    )
    if dry_run:
        return {
            "dry_run": True,
            "metadata": metadata,
            "chapters": [
                {"title": c["title"], "lessons": [x["title"] for x in c["lessons"]]}
                for c in structure["chapters"]
            ],
            "publish": False,
        }
    journal_path = local_path(root, ".school-create.json")
    journal = (
        json.loads(journal_path.read_text(encoding="utf-8"))
        if journal_path.exists()
        else {"server": client.server, "fingerprint": fingerprint, "completed": {}}
    )
    if (
        journal.get("server") != client.server
        or journal.get("fingerprint") != fingerprint
    ):
        raise CLIError("input", "创建记录与平台或本地内容不一致；请先核对已有草稿")
    if journal.get("pending"):
        raise CLIError(
            "conflict",
            "上一步创建结果未确认，请先核对平台；不会自动重复请求",
            details=journal,
        )

    def step(key, method, path, data):
        if key in journal["completed"]:
            return journal["completed"][key]
        journal["pending"] = key
        write_json(journal_path, journal)
        result = client.request(method, path, data)
        journal["completed"][key] = result
        journal.pop("pending")
        write_json(journal_path, journal)
        return result

    try:
        course = step(
            "course",
            "PUT",
            "/api/online/shifu/shifus",
            {"name": metadata["name"], "description": metadata["description"]},
        )
        bid = identifier(course.get("bid"))
        base = course_path(bid)
        if "initial_outlines" not in journal:
            initial = client.request("GET", base + "/outlines")
            if initial:
                if len(initial) != 1 or len(initial[0].get("children", [])) != 1:
                    raise CLIError(
                        "conflict", "新课初始结构不是一个章节和课时；请先核对已有草稿"
                    )
                first = initial[0]["children"][0]
                if first.get("children"):
                    raise CLIError("conflict", "新课初始结构不受支持；请先核对已有草稿")
                content = client.request(
                    "GET", base + f"/outlines/{identifier(first['bid'])}/mdflow"
                )
                if content not in ("", None):
                    raise CLIError(
                        "conflict", "默认课时已有内容，不能作为空白新课继续创建"
                    )
            journal["initial_outlines"] = initial
            write_json(journal_path, journal)
        initial = journal["initial_outlines"]
        step(
            "metadata",
            "POST",
            base + "/detail",
            {"system_prompt": metadata["system_prompt"]},
        )
        lessons = []
        for cindex, chapter in enumerate(structure["chapters"]):
            default_chapter = initial[0] if initial and cindex == 0 else None
            chapter_result = step(
                f"chapter:{cindex}",
                "POST" if default_chapter else "PUT",
                base
                + "/outlines"
                + ("/" + identifier(default_chapter["bid"]) if default_chapter else ""),
                {"name": chapter["title"]},
            )
            chapter_bid = identifier(chapter_result.get("bid"))
            for lindex, lesson in enumerate(chapter["lessons"]):
                key = f"lesson:{cindex}:{lindex}"
                default_lesson = (
                    default_chapter["children"][0]
                    if default_chapter and lindex == 0
                    else None
                )
                node = step(
                    key,
                    "POST" if default_lesson else "PUT",
                    base
                    + "/outlines"
                    + (
                        "/" + identifier(default_lesson["bid"])
                        if default_lesson
                        else ""
                    ),
                    {"name": lesson["title"]}
                    if default_lesson
                    else {"name": lesson["title"], "parent_bid": chapter_bid},
                )
                outline = identifier(node.get("bid"))
                result = step(
                    key + ":content",
                    "POST",
                    base + f"/outlines/{outline}/mdflow",
                    {
                        "data": lesson["content"],
                        "base_revision": revision(client, bid, outline),
                    },
                )
                lessons.append(
                    {
                        "outline_bid": outline,
                        "file": "lessons/" + lesson["file"],
                        "revision": result["new_revision"],
                        "sha256": digest(lesson["content"]),
                    }
                )
        # All writes are complete; verify immutable snapshots before claiming success.
        detail, nodes, number = snapshot(client, bid)
        actual = {n["bid"]: n.get("content") for n in nodes}
        if any(
            digest(actual.get(item["outline_bid"]) or "") != item["sha256"]
            for item in lessons
        ) or any((detail.get(k) or "") != v for k, v in metadata.items()):
            raise CLIError("conflict", "创建后读回内容不一致，请核对已有草稿")
        write_json(
            local_path(root, MANIFEST),
            {
                "schema_version": 1,
                "server": client.server,
                "course_bid": bid,
                "course": {**metadata, "revision": number},
                "lessons": lessons,
                "structure_sha256": digest(
                    (root / "structure.json").read_text(encoding="utf-8")
                ),
            },
        )
        return {
            "course_bid": bid,
            "completed": list(journal["completed"]),
            "published": False,
        }
    except CLIError as exc:
        exc.details = {
            "journal": str(journal_path),
            "completed": journal["completed"],
            "pending": journal.get("pending"),
        }
        raise
