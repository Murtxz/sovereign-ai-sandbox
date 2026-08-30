"""
Low-level Docker execution. This is the ONLY file in the whole system
that should import the `docker` package or know what a container is.

Everything above this (service.py, and everything above that) only
ever sees SandboxRequest / SandboxResult.
"""
from __future__ import annotations

import time
from dataclasses import dataclass

import docker
from docker.errors import ContainerError, DockerException, ImageNotFound
from docker.types import Ulimit

from app.sandbox.workspace import Workspace
from app.security.policy import SandboxPolicy


@dataclass
class RawExecutionResult:
    status: str          # "success" | "failed" | "timeout" | "blocked" | "infra_error"
    exit_code: int | None
    stdout: str
    stderr: str
    duration_ms: int


class DockerRunner:
    def __init__(self, policy: SandboxPolicy):
        self.policy = policy
        try:
            self._client = docker.from_env()
        except DockerException as e:
            raise RuntimeError(
                "Cannot reach the Docker daemon. Is Docker running, and is "
                "your user in the 'docker' group (or are you running with "
                "sudo)? Original error: " + str(e)
            ) from e

    def ensure_image(self) -> None:
        """Fail fast and loudly if the sandbox runtime image hasn't been
        built yet, instead of failing confusingly deep inside a run()."""
        try:
            self._client.images.get(self.policy.image)
        except ImageNotFound as e:
            raise RuntimeError(
                f"Sandbox image '{self.policy.image}' not found. Build it "
                f"first with: docker build -t {self.policy.image} "
                f"docker/sandbox-image/"
            ) from e

    def run(
        self,
        workspace: Workspace,
        timeout_seconds: int,
        memory_mb: int,
        cpu_limit: float,
    ) -> RawExecutionResult:
        started = time.monotonic()

        container = None
        try:
            container = self._client.containers.run(
                image=self.policy.image,
                command=["python", "/workspace/input/script.py"],
                detach=True,
                # --- network isolation ---
                network_mode=self.policy.network_mode,  # "none"
                # --- filesystem isolation ---
                volumes={
                    str(workspace.input_dir): {"bind": "/workspace/input", "mode": "ro"},
                    str(workspace.output_dir): {"bind": "/workspace/output", "mode": "rw"},
                },
                working_dir="/workspace",
                read_only=self.policy.read_only_root_fs,
                tmpfs={"/tmp": "size=64m"},  # writable scratch space that isn't disk-backed
                # --- identity / privilege ---
                user=self.policy.run_as_user,
                cap_drop=["ALL"] if self.policy.drop_all_capabilities else [],
                security_opt=["no-new-privileges"] if self.policy.no_new_privileges else [],
                # --- resource limits ---
                mem_limit=f"{memory_mb}m",
                memswap_limit=f"{memory_mb}m",  # prevents swap = mem_limit is a hard ceiling
                nano_cpus=int(cpu_limit * 1_000_000_000),
                pids_limit=self.policy.pids_limit,
                ulimits=[Ulimit(name="nofile", soft=64, hard=64)],
                # --- misc hardening ---
                stdin_open=False,
                tty=False,
                remove=False,  # we remove manually after collecting logs
            )

            try:
                exit_status = container.wait(timeout=timeout_seconds)
                exit_code = exit_status.get("StatusCode")
                timed_out = False
            except Exception:
                # docker-py raises on client-side wait timeout; the
                # container itself is still running and must be killed.
                timed_out = True
                exit_code = None

            if timed_out:
                try:
                    container.kill()
                except DockerException:
                    pass
                stdout, stderr = self._collect_logs(container)
                duration_ms = int((time.monotonic() - started) * 1000)
                return RawExecutionResult(
                    status="timeout",
                    exit_code=None,
                    stdout=stdout,
                    stderr=stderr or "Execution timed out",
                    duration_ms=duration_ms,
                )

            stdout, stderr = self._collect_logs(container)
            duration_ms = int((time.monotonic() - started) * 1000)

            if exit_code == 0:
                status = "success"
            elif self._looks_like_network_block(stderr):
                status = "blocked"
            else:
                status = "failed"

            return RawExecutionResult(
                status=status,
                exit_code=exit_code,
                stdout=self._truncate(stdout),
                stderr=self._truncate(stderr),
                duration_ms=duration_ms,
            )

        except ContainerError as e:
            duration_ms = int((time.monotonic() - started) * 1000)
            return RawExecutionResult(
                status="failed",
                exit_code=getattr(e, "exit_status", 1),
                stdout="",
                stderr=str(e),
                duration_ms=duration_ms,
            )
        finally:
            if container is not None:
                try:
                    container.remove(force=True)
                except DockerException:
                    pass

    def _collect_logs(self, container) -> tuple[str, str]:
        try:
            stdout = container.logs(stdout=True, stderr=False).decode(
                "utf-8", errors="replace"
            )
            stderr = container.logs(stdout=False, stderr=True).decode(
                "utf-8", errors="replace"
            )
        except DockerException:
            stdout, stderr = "", ""
        return stdout, stderr

    def _truncate(self, text: str) -> str:
        limit = self.policy.max_output_bytes
        if len(text.encode("utf-8")) > limit:
            return text[:limit] + "\n...[output truncated]"
        return text

    @staticmethod
    def _looks_like_network_block(stderr: str) -> bool:
        markers = (
            "Network is unreachable",
            "Temporary failure in name resolution",
            "Connection refused",
            "Name or service not known",
            "Errno 101",
            "Errno -3",
        )
        return any(m in stderr for m in markers)
