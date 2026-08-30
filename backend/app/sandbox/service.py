"""
DockerSandboxService - the real, production implementation of the
SandboxService contract. This is what app/main.py wires in once
Docker is ready, replacing MockSandboxService with ZERO changes
needed in Member 1's Agent code.
"""
from __future__ import annotations

import asyncio
import logging

from app.core.interfaces.sandbox import SandboxService
from app.core.schemas.sandbox import (
    NetworkStatus,
    SandboxRequest,
    SandboxResult,
    SecurityStatus,
)
from app.sandbox.docker_runner import DockerRunner
from app.sandbox.workspace import create_workspace
from app.security.policy import DEFAULT_POLICY, SandboxPolicy
from app.telemetry.audit import AuditLogger

logger = logging.getLogger("sandbox")


class DockerSandboxService(SandboxService):
    def __init__(
        self,
        policy: SandboxPolicy | None = None,
        audit_logger: AuditLogger | None = None,
        cleanup_workspace: bool = True,
    ):
        self.policy = policy or DEFAULT_POLICY
        self.runner = DockerRunner(self.policy)
        self.audit = audit_logger or AuditLogger()
        self.cleanup_workspace = cleanup_workspace
        # Fail fast at startup, not on the first real request.
        self.runner.ensure_image()

    async def execute(self, request: SandboxRequest) -> SandboxResult:
        self._static_check(request.code)

        timeout = min(request.timeout_seconds, self.policy.max_timeout_seconds)
        memory = min(request.memory_limit_mb, self.policy.max_memory_mb)
        cpu = min(request.cpu_limit, self.policy.max_cpu_limit)

        workspace = create_workspace(request.code, request.input_files, self.policy)

        try:
            raw = await asyncio.to_thread(
                self.runner.run,
                workspace,
                timeout,
                memory,
                cpu,
            )

            output_files = [p.name for p in workspace.output_dir.iterdir() if p.is_file()]

            result = SandboxResult(
                status=raw.status,
                exit_code=raw.exit_code,
                stdout=raw.stdout,
                stderr=raw.stderr,
                output_files=output_files,
                duration_ms=raw.duration_ms,
                network=NetworkStatus(
                    network_isolated=self.policy.network_mode == "none",
                    packets_out=0,
                    bytes_out=0,
                    dns_requests=0,
                    blocked_attempts=1 if raw.status == "blocked" else 0,
                ),
                security=SecurityStatus(
                    network_isolated=self.policy.network_mode == "none",
                    filesystem_restricted=self.policy.read_only_root_fs,
                    resource_limits_active=True,
                    ran_as_non_root=self.policy.run_as_user != "0:0",
                ),
                job_id=workspace.job_id,
            )

            self.audit.record(request=request, result=result)
            return result

        finally:
            if self.cleanup_workspace:
                workspace.cleanup()

    def _static_check(self, code: str) -> None:
        """Defense-in-depth only. The real security boundary is the
        container (network=none, read-only fs, dropped caps, no root).
        This just catches obviously hostile patterns early and cheaply,
        and MUST NOT be relied upon as the primary control."""
        for pattern in self.policy.denied_code_substrings:
            if pattern in code:
                logger.warning("Static check rejected code containing: %s", pattern)
                raise ValueError(
                    f"Code rejected by static policy check (pattern: {pattern!r})"
                )
