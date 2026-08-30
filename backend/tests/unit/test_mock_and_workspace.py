from __future__ import annotations

from app.core.schemas.sandbox import SandboxRequest
from app.sandbox.mock import MockSandboxService
from app.sandbox.workspace import create_workspace
from app.security.policy import DEFAULT_POLICY


async def test_mock_blocks_network_code():
    service = MockSandboxService()
    result = await service.execute(SandboxRequest(code="import socket\nsocket.create_connection(('x', 1))"))
    assert result.status == "blocked"


async def test_mock_times_out_infinite_loop():
    service = MockSandboxService()
    result = await service.execute(SandboxRequest(code="while True:\n    pass"))
    assert result.status == "timeout"


async def test_mock_succeeds_on_normal_code():
    service = MockSandboxService()
    result = await service.execute(SandboxRequest(code="print('hi')"))
    assert result.status == "success"


def test_workspace_creates_isolated_dirs(tmp_path):
    policy = DEFAULT_POLICY.model_copy(update={"workspace_root": str(tmp_path)})
    ws = create_workspace(code="print(1)", input_files=[], policy=policy)
    try:
        assert ws.script_path().exists()
        assert ws.script_path().read_text() == "print(1)"
        assert ws.input_dir.exists()
        assert ws.output_dir.exists()
        # workspace must live under the configured root, nowhere else
        assert str(ws.root).startswith(str(tmp_path))
    finally:
        ws.cleanup()
    assert not ws.root.exists()
