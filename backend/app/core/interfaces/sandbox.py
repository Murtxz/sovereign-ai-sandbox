"""
SandboxService interface.

Member 1 (Agent) codes against this Protocol ONLY. It never imports
MockSandboxService or DockerSandboxService directly - those get
injected at app composition time (see app/main.py).
"""
from __future__ import annotations

from typing import Protocol, runtime_checkable

from app.core.schemas.sandbox import SandboxRequest, SandboxResult


@runtime_checkable
class SandboxService(Protocol):
    async def execute(self, request: SandboxRequest) -> SandboxResult:
        """Run untrusted code and return a standardized result.

        Implementations must NEVER raise for "normal" failures like
        timeouts, network-block attempts, or non-zero exit codes -
        those are represented in the returned SandboxResult.status.
        Only raise for genuine infrastructure errors (e.g. Docker
        daemon unreachable).
        """
        ...
