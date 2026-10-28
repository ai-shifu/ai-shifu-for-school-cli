import os
import subprocess
from pathlib import Path

import pytest


@pytest.mark.skipif(
    os.name == "nt", reason="POSIX installer; PowerShell is checked in Windows CI"
)
def test_shell_installer_uses_public_client_archive_and_supports_skip_setup(tmp_path):
    root = Path(__file__).resolve().parents[1]
    fake = tmp_path / "bin"
    fake.mkdir()
    log = tmp_path / "calls"
    uv = fake / "uv"
    uv.write_text(f'''#!/bin/sh
printf '%s\\n' "$*" >> "{log}"
if [ "$*" = "tool dir --bin" ]; then printf '%s\\n' "{fake}"; fi
''')
    uv.chmod(0o755)
    client = fake / "ai-shifu-for-school"
    client.write_text(
        '#!/bin/sh\n[ "$1" = "--version" ] || exit 9\nprintf "0.1.0\\n"\n'
    )
    client.chmod(0o755)
    result = subprocess.run(
        ["sh", str(root / "install.sh"), "--skip-setup"],
        env={**os.environ, "PATH": str(fake) + os.pathsep + os.environ["PATH"]},
        capture_output=True,
        text=True,
    )
    assert result.returncode == 0, result.stderr
    commands = log.read_text()
    assert (
        "https://github.com/ai-shifu/ai-shifu-for-school-cli/archive/refs/heads/main.zip"
        in commands
    )
    assert "--python 3.12" in commands
    assert "tool update-shell" in commands
    assert "setup" in result.stdout
    assert subprocess.run(["sh", "-n", str(root / "install.sh")]).returncode == 0
