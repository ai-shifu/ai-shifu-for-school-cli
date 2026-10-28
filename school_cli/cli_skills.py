"""Read and install the self-contained skill resources shipped in the wheel."""

from importlib.resources import files
from pathlib import Path

from .cli_client import CLIError, atomic_text


def resources():
    bundled = files("school_cli").joinpath("skills")
    if bundled.is_dir():
        return bundled
    # The repository exposes skills at its root for standard skill installers.
    source = Path(__file__).resolve().parent.parent / "skills"
    if source.is_dir():
        return source
    raise CLIError("installation", "安装包缺少 Skills，请重新安装客户端")


def list_skills():
    return sorted(
        item.name
        for item in resources().iterdir()
        if item.is_dir() and item.joinpath("SKILL.md").is_file()
    )


def read_skill(name, reference="SKILL.md"):
    if (
        name not in list_skills()
        or ".." in Path(reference).parts
        or Path(reference).is_absolute()
    ):
        raise CLIError("input", "Skill 或参考文件不存在")
    target = resources().joinpath(name, reference)
    if not target.is_file() or not reference.endswith((".md", ".yaml")):
        raise CLIError("input", "Skill 或参考文件不存在")
    return target.read_text(encoding="utf-8")


def _walk(root, prefix=""):
    for entry in root.iterdir():
        name = prefix + entry.name
        if entry.is_dir():
            yield from _walk(entry, name + "/")
        else:
            yield name, entry.read_text(encoding="utf-8")


def install_skills(destination, *, dry_run=False):
    destination = Path(destination).expanduser()
    payloads = {name: dict(_walk(resources().joinpath(name))) for name in list_skills()}
    conflicts = []
    for name, payload in payloads.items():
        folder = destination / name
        if folder.is_symlink() or (folder.exists() and not folder.is_dir()):
            conflicts.append(str(folder))
            continue
        if not folder.exists():
            continue
        existing = {
            path.relative_to(folder).as_posix(): path
            for path in folder.rglob("*")
            if path.is_file() or path.is_symlink()
        }
        for relative in existing.keys() | payload.keys():
            path = existing.get(relative)
            if (
                path is None
                or relative not in payload
                or path.is_symlink()
                or path.read_text(encoding="utf-8") != payload[relative]
            ):
                conflicts.append(str(folder / relative))
    if conflicts:
        raise CLIError(
            "conflict",
            "目标 Skill 内容不同，未覆盖任何文件；请比较后选择新目录",
            details={"files": conflicts},
        )
    if not dry_run:
        for name, payload in payloads.items():
            for relative, content in payload.items():
                target = destination / name / relative
                if not target.exists():
                    atomic_text(target, content)
    return {
        "dry_run": dry_run,
        "destination": str(destination),
        "skills": list(payloads),
    }
