"""
Audit logging for every sandbox execution.

This is what lets the team later say "we didn't just configure
isolation, we can prove what happened on every single run" - one
JSON line per execution, easy to grep, easy to ship to the security
dashboard Member 5 builds.
"""
from __future__ import annotations

import hashlib
import json
import logging
from datetime import datetime, timezone
from pathlib import Path

from app.core.schemas.sandbox import SandboxRequest, SandboxResult

logger = logging.getLogger("sandbox.audit")


class AuditLogger:
    def __init__(self, log_path: str = "/tmp/sovereign-sandbox-workspaces/audit.log"):
        self.log_path = Path(log_path)
        self.log_path.parent.mkdir(parents=True, exist_ok=True)

    def record(self, request: SandboxRequest, result: SandboxResult) -> None:
        entry = {
            "timestamp": datetime.now(timezone.utc).isoformat(),
            "job_id": result.job_id,
            "code_hash": hashlib.sha256(request.code.encode()).hexdigest(),
            "code_length": len(request.code),
            "input_files": [f.filename for f in request.input_files],
            "timeout_seconds": request.timeout_seconds,
            "status": result.status,
            "exit_code": result.exit_code,
            "duration_ms": result.duration_ms,
            "output_files": result.output_files,
            "security": result.security.model_dump(),
            "network": result.network.model_dump(),
        }
        with self.log_path.open("a") as f:
            f.write(json.dumps(entry) + "\n")

        if result.status in ("blocked", "timeout"):
            logger.warning("sandbox execution flagged: %s", entry)
        else:
            logger.info("sandbox execution: job_id=%s status=%s", result.job_id, result.status)
