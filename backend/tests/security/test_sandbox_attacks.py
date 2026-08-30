"""
Security test matrix for the real Docker sandbox.

Run on a machine with Docker installed and the image built:
    docker build -t sovereign-sandbox-runtime:latest docker/sandbox-image/
    pytest tests/security/test_sandbox_attacks.py -v

Every test here represents a row in the security testing matrix from
the project spec. If any of these fail, do NOT move on to wiring the
Agent up to the real sandbox - fix this first.
"""
from __future__ import annotations

import pytest

from app.core.schemas.sandbox import SandboxRequest


@pytest.fixture
def sandbox():
    pytest.importorskip("docker")
    from app.sandbox.service import DockerSandboxService
    try:
        return DockerSandboxService()
    except RuntimeError as e:
        pytest.skip(f"Docker not available: {e}")


@pytest.mark.asyncio
async def test_normal_code_succeeds(sandbox):
    result = await sandbox.execute(SandboxRequest(code="print(2 + 2)"))
    assert result.status == "success"
    assert result.exit_code == 0
    assert "4" in result.stdout


@pytest.mark.asyncio
async def test_network_socket_connection_is_blocked(sandbox):
    code = (
        "import socket\n"
        "s = socket.create_connection(('93.184.216.34', 80), timeout=3)\n"
        "print('CONNECTED - THIS SHOULD NOT HAPPEN')\n"
    )
    result = await sandbox.execute(SandboxRequest(code=code, timeout_seconds=10))
    assert result.status in ("blocked", "failed")
    assert "CONNECTED" not in result.stdout


@pytest.mark.asyncio
async def test_dns_resolution_is_blocked(sandbox):
    code = (
        "import socket\n"
        "socket.gethostbyname('example.com')\n"
        "print('RESOLVED - THIS SHOULD NOT HAPPEN')\n"
    )
    result = await sandbox.execute(SandboxRequest(code=code, timeout_seconds=10))
    assert result.status in ("blocked", "failed")
    assert "RESOLVED" not in result.stdout


@pytest.mark.asyncio
async def test_root_filesystem_is_read_only(sandbox):
    code = (
        "open('/malicious_write_test.txt', 'w').write('pwned')\n"
        "print('WROTE - THIS SHOULD NOT HAPPEN')\n"
    )
    result = await sandbox.execute(SandboxRequest(code=code))
    assert result.status == "failed"
    assert "WROTE" not in result.stdout
    assert "Read-only file system" in result.stderr or "Errno 30" in result.stderr


@pytest.mark.asyncio
async def test_infinite_loop_times_out(sandbox):
    result = await sandbox.execute(
        SandboxRequest(code="while True:\n    pass\n", timeout_seconds=3)
    )
    assert result.status == "timeout"
    assert result.duration_ms < 15_000  # killed promptly, not hung


@pytest.mark.asyncio
async def test_memory_bomb_is_contained(sandbox):
    code = (
        "x = []\n"
        "while True:\n"
        "    x.append('A' * 10_000_000)\n"
    )
    result = await sandbox.execute(
        SandboxRequest(code=code, timeout_seconds=15, memory_limit_mb=128)
    )
    # Either OOM-killed (failed, nonzero exit) or hits the timeout first -
    # both are acceptable, what's NOT acceptable is "success" or hanging
    # the host.
    assert result.status in ("failed", "timeout")


@pytest.mark.asyncio
async def test_fork_bomb_is_contained(sandbox):
    code = (
        "import os\n"
        "while True:\n"
        "    os.fork()\n"
    )
    result = await sandbox.execute(SandboxRequest(code=code, timeout_seconds=10))
    assert result.status in ("failed", "timeout")


@pytest.mark.asyncio
async def test_writing_to_output_dir_is_allowed(sandbox):
    code = "open('/workspace/output/result.txt', 'w').write('ok')\n"
    result = await sandbox.execute(SandboxRequest(code=code))
    assert result.status == "success"
    assert "result.txt" in result.output_files
