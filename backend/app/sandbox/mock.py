"""
MockSandboxService - deterministic, instant, no Docker required.

Give this to Member 1 on day 1 so LangGraph development is never
blocked on your Docker work. Swapping this for DockerSandboxService
later requires changing exactly one line in app/main.py.
"""
from __future__ import annotations

import time
import uuid

from app.core.interfaces.sandbox import SandboxService
from app.core.schemas.sandbox import (
    NetworkStatus,
    SandboxRequest,
    SandboxResult,
    SecurityStatus,
)


class MockSandboxService(SandboxService):
    """Returns canned, contract-shaped results instantly."""

    async def execute(self, request: SandboxRequest) -> SandboxResult:
        job_id = str(uuid.uuid4())

        code = request.code

        # Simple heuristics so mock behavior is at least plausible
        # during agent development / demos.
        if "while True" in code or "while 1" in code:
            return SandboxResult(
                status="timeout",
                exit_code=None,
                stdout="",
                stderr="Execution timed out",
                output_files=[],
                duration_ms=request.timeout_seconds * 1000,
                network=NetworkStatus(network_isolated=True, blocked_attempts=0),
                security=self._security_status(),
                job_id=job_id,
            )

        if "socket" in code or "requests.get" in code or "urllib" in code:
            return SandboxResult(
                status="blocked",
                exit_code=1,
                stdout="",
                stderr="Network access denied",
                output_files=[],
                duration_ms=120,
                network=NetworkStatus(
                    network_isolated=True, blocked_attempts=1
                ),
                security=self._security_status(),
                job_id=job_id,
            )

        return SandboxResult(
            status="success",
            exit_code=0,
            stdout="[mock output] execution simulated successfully\n",
            stderr="",
            output_files=[],
            duration_ms=150,
            network=NetworkStatus(network_isolated=True, blocked_attempts=0),
            security=self._security_status(),
            job_id=job_id,
        )

    @staticmethod
    def _security_status() -> SecurityStatus:
        return SecurityStatus(
            network_isolated=True,
            filesystem_restricted=True,
            resource_limits_active=True,
            ran_as_non_root=True,
        )
