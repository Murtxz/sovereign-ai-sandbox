"""
Sandbox contract (owned by Member 4, consumed by Member 1's Agent).

Everything the Agent needs to know about code execution lives in this
file. It must NEVER import anything from docker, subprocess, etc. -
those are Member 4's private implementation details.
"""
from __future__ import annotations

from typing import Literal

from pydantic import BaseModel, Field

from app.core.schemas.common import FileRef

SandboxStatus = Literal["success", "failed", "timeout", "blocked"]


class SandboxRequest(BaseModel):
    """What the Agent sends to run untrusted, AI-generated code."""

    code: str
    input_files: list[FileRef] = Field(default_factory=list)
    timeout_seconds: int = Field(default=30, ge=1, le=300)
    memory_limit_mb: int = Field(default=512, ge=64, le=4096)
    cpu_limit: float = Field(default=1.0, ge=0.1, le=4.0)


class NetworkStatus(BaseModel):
    """Evidence that the execution did not reach outside the machine."""

    network_isolated: bool
    packets_out: int = 0
    bytes_out: int = 0
    dns_requests: int = 0
    blocked_attempts: int = 0


class SecurityStatus(BaseModel):
    """Which controls were actually active for this run."""

    network_isolated: bool
    filesystem_restricted: bool
    resource_limits_active: bool
    ran_as_non_root: bool


class SandboxResult(BaseModel):
    """What Member 4 always returns to the Agent, regardless of what
    happened internally (Docker error, OOM kill, timeout, etc.)."""

    status: SandboxStatus
    exit_code: int | None
    stdout: str
    stderr: str
    output_files: list[str] = Field(default_factory=list)
    duration_ms: int
    network: NetworkStatus
    security: SecurityStatus
    job_id: str
