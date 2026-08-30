"""
Contract tests: any SandboxService implementation (mock or real) MUST
pass these. This is what lets Member 1 trust that swapping
MockSandboxService -> DockerSandboxService won't break the Agent.

Run just the mock (always works, no Docker needed):
    pytest tests/contract/test_sandbox_contract.py -k mock

Run against the real Docker sandbox (needs Docker + built image):
    pytest tests/contract/test_sandbox_contract.py -k real
"""
from __future__ import annotations

import pytest

from app.core.schemas.sandbox import SandboxRequest
from app.sandbox.mock import MockSandboxService


@pytest.fixture
def mock_service():
    return MockSandboxService()


@pytest.fixture
def real_service():
    pytest.importorskip("docker")
    from app.sandbox.service import DockerSandboxService
    try:
        return DockerSandboxService()
    except RuntimeError as e:
        pytest.skip(f"Docker not available in this environment: {e}")


async def _assert_contract_shape(result):
    # These assertions define the contract itself - they must hold
    # for EVERY implementation, mock or real.
    assert result.status in ("success", "failed", "timeout", "blocked")
    assert isinstance(result.stdout, str)
    assert isinstance(result.stderr, str)
    assert isinstance(result.duration_ms, int)
    assert result.duration_ms >= 0
    assert result.security.network_isolated is True
    assert result.job_id


@pytest.mark.asyncio
async def test_mock_contract_shape(mock_service):
    request = SandboxRequest(code="print('hello')")
    result = await mock_service.execute(request)
    await _assert_contract_shape(result)
    assert result.status == "success"


@pytest.mark.asyncio
async def test_real_contract_shape(real_service):
    request = SandboxRequest(code="print('hello')")
    result = await real_service.execute(request)
    await _assert_contract_shape(result)
    assert result.status == "success"
    assert "hello" in result.stdout
