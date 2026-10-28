import io
import subprocess
import sys
import tarfile
import zipfile
from pathlib import Path


def test_distribution_gate_rejects_server_source(tmp_path):
    artifact = tmp_path / "bad-0.1.0-py3-none-any.whl"
    with zipfile.ZipFile(artifact, "w") as archive:
        archive.writestr("school_cli/api.py", "# server source must never ship")
    tool = Path(__file__).resolve().parents[1] / "tools/check_distribution.py"
    result = subprocess.run(
        [sys.executable, str(tool), str(tmp_path)], capture_output=True, text=True
    )
    assert result.returncode == 1
    assert "school_cli/api.py" in result.stdout


def test_distribution_gate_rejects_private_environment(tmp_path):
    artifact = tmp_path / "bad-0.1.0.tar.gz"
    with tarfile.open(artifact, "w:gz") as archive:
        content = b"private fixture content"
        member = tarfile.TarInfo("bad-0.1.0/.env")
        member.size = len(content)
        archive.addfile(member, io.BytesIO(content))
    tool = Path(__file__).resolve().parents[1] / "tools/check_distribution.py"
    result = subprocess.run(
        [sys.executable, str(tool), str(tmp_path)], capture_output=True, text=True
    )
    assert result.returncode == 1
    assert "private fixture content" not in result.stdout
