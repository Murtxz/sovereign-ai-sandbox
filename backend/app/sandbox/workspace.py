"""
Per-job workspace on the HOST filesystem.

Layout:
    workspace_root/<job_id>/
        input/    (mounted read-only into the container)
        output/   (mounted read-write into the container)

Only these two directories are ever mounted into a container. Nothing
else on the host is ever exposed - this is the single most important
rule in this whole module. Never write a docker call that mounts
anything outside a job's own workspace.
"""
from __future__ import annotations

import shutil
import uuid
from dataclasses import dataclass
from pathlib import Path

from app.core.schemas.common import FileRef
from app.security.policy import SandboxPolicy


@dataclass
class Workspace:
    job_id: str
    root: Path
    input_dir: Path
    output_dir: Path

    def script_path(self) -> Path:
        return self.input_dir / "script.py"

    def cleanup(self) -> None:
        shutil.rmtree(self.root, ignore_errors=True)


def create_workspace(
    code: str,
    input_files: list[FileRef],
    policy: SandboxPolicy,
) -> Workspace:
    job_id = str(uuid.uuid4())
    root = Path(policy.workspace_root) / job_id
    input_dir = root / "input"
    output_dir = root / "output"

    input_dir.mkdir(parents=True, exist_ok=True)
    output_dir.mkdir(parents=True, exist_ok=True)
    # Output dir must be writable by the sandbox's unprivileged user.
    output_dir.chmod(0o777)

    ws = Workspace(job_id=job_id, root=root, input_dir=input_dir, output_dir=output_dir)

    # Write the generated code as the only executable file present.
    ws.script_path().write_text(code)

    # Copy in only explicitly approved input files - never symlink,
    # never mount the source path directly, to avoid accidentally
    # exposing more of the host than intended.
    for f in input_files:
        src = Path(f.path)
        if not src.is_file():
            raise FileNotFoundError(f"declared input file not found: {src}")
        dst = input_dir / f.filename
        shutil.copyfile(src, dst)

    return ws
