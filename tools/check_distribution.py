"""Check that public distributions contain only the school client."""

import json
import sys
import tarfile
import zipfile
from pathlib import Path, PurePosixPath

MODULES = {
    "__init__.py",
    "cli.py",
    "cli_client.py",
    "cli_commands.py",
    "cli_config.py",
    "cli_courses.py",
    "cli_skills.py",
    "onboarding.py",
    "schemas.py",
}
SOURCE_ROOTS = {"school_cli", "skills", "tests", "tools"}
SOURCE_FILES = {
    "README.md",
    "LICENSE",
    "NOTICE",
    "pyproject.toml",
    "uv.lock",
    "install.sh",
    "install.ps1",
    ".env.example",
    ".gitignore",
    "PKG-INFO",
}


def check(directory):
    artifacts = sorted(Path(directory).glob("*.whl")) + sorted(
        Path(directory).glob("*.tar.gz")
    )
    if not artifacts:
        raise ValueError("No distributions found")
    results = []
    for artifact in artifacts:
        if artifact.suffix == ".whl":
            with zipfile.ZipFile(artifact) as archive:
                names = [name for name in archive.namelist() if not name.endswith("/")]
                for name in names:
                    parts = PurePosixPath(name).parts
                    allowed = (
                        (
                            parts[0] == "school_cli"
                            and len(parts) == 2
                            and parts[1] in MODULES
                        )
                        or (
                            parts[:2] == ("school_cli", "skills")
                            and name.endswith((".md", ".yaml"))
                        )
                        or (
                            parts[0].endswith(".dist-info")
                            and parts[0].startswith("ai_shifu_for_school_cli-")
                        )
                    )
                    if not allowed:
                        raise ValueError(f"Unexpected public wheel file: {name}")
                skills = [name for name in names if name.endswith("/SKILL.md")]
                if len(skills) != 5:
                    raise ValueError("The public wheel must contain five skills")
                metadata = next(
                    name for name in names if name.endswith(".dist-info/METADATA")
                )
                requirements = [
                    line.lower()
                    for line in archive.read(metadata).decode().splitlines()
                    if line.startswith("Requires-Dist:")
                ]
                if any(
                    any(
                        server in line
                        for server in (
                            "fastapi",
                            "uvicorn",
                            "sqlalchemy",
                            "celery",
                            "redis",
                        )
                    )
                    for line in requirements
                ):
                    raise ValueError("Server dependency found in public client")
        else:
            with tarfile.open(artifact) as archive:
                names = [
                    member.name for member in archive.getmembers() if member.isfile()
                ]
            for name in names:
                parts = PurePosixPath(name).parts[1:]
                if not parts or not (
                    parts[0] in SOURCE_ROOTS
                    or len(parts) == 1
                    and parts[0] in SOURCE_FILES
                ):
                    raise ValueError(f"Unexpected public source file: {name}")
                if any(
                    part in {".env", ".runtime", "__pycache__", ".venv"}
                    for part in parts
                ) or name.endswith((".cookies", ".sqlite3", ".pyc")):
                    raise ValueError(f"Runtime data in source distribution: {name}")
        results.append({"artifact": artifact.name, "files": len(names)})
    return results


if __name__ == "__main__":
    try:
        print(
            json.dumps(
                {
                    "ok": True,
                    "artifacts": check(sys.argv[1] if len(sys.argv) > 1 else "dist"),
                },
                indent=2,
            )
        )
    except ValueError as exc:
        print(json.dumps({"ok": False, "error": str(exc)}))
        raise SystemExit(1)
