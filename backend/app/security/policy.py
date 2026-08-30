"""
Centralized security policy for the sandbox.

Every hard limit lives here, in one place, instead of being scattered
across docker_runner.py. When you (or a teammate) ask "what are our
actual limits?", this file is the answer.
"""
from __future__ import annotations

from pydantic import BaseModel


class SandboxPolicy(BaseModel):
    # --- Image ---
    image: str = "sovereign-sandbox-runtime:latest"

    # --- Resource limits ---
    default_timeout_seconds: int = 30
    max_timeout_seconds: int = 120
    default_memory_mb: int = 512
    max_memory_mb: int = 2048
    default_cpu_limit: float = 1.0
    max_cpu_limit: float = 2.0
    pids_limit: int = 64          # blocks fork bombs
    max_output_bytes: int = 5_000_000  # 5 MB stdout/stderr cap

    # --- Filesystem ---
    read_only_root_fs: bool = True
    workspace_root: str = "/tmp/sovereign-sandbox-workspaces"

    # --- Network ---
    network_mode: str = "none"    # Docker's fully-isolated network driver

    # --- Identity / capabilities ---
    run_as_user: str = "65534:65534"   # 'nobody' - never root
    drop_all_capabilities: bool = True
    no_new_privileges: bool = True

    # --- Filesystem denylist (defense in depth, not the primary control) ---
    # The primary control is namespace isolation (container has its own
    # filesystem, distinct from the host). This is an extra static check
    # on generated code before it's even sent to Docker.
    denied_code_substrings: tuple[str, ...] = (
        "os.system(",
        "subprocess.Popen(",
        "ctypes.CDLL",
        "/proc/1/",
        "docker.sock",
    )


DEFAULT_POLICY = SandboxPolicy()
