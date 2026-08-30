"""
Week-1 deliverable demo, matching the project spec's expected terminal
output:

    $ python sandbox_test.py
    Code executed safely (mock mode, no Docker required)

    $ python sandbox_test.py --real
    Code executed safely (real Docker sandbox)

Run this to sanity check your setup at any point.
"""
from __future__ import annotations

import asyncio
import sys

from app.core.schemas.sandbox import SandboxRequest


async def main(use_real: bool):
    if use_real:
        from app.sandbox.service import DockerSandboxService
        service = DockerSandboxService()
        label = "REAL Docker sandbox"
    else:
        from app.sandbox.mock import MockSandboxService
        service = MockSandboxService()
        label = "MOCK sandbox (no Docker)"

    print(f"=== Using {label} ===\n")

    tests = [
        ("Normal code", "print('hello from the sandbox')"),
        ("Network attempt", "import socket\nsocket.create_connection(('example.com', 80), timeout=3)"),
        ("Host file read attempt", "print(open('/etc/passwd').read())"),
        ("Infinite loop", "while True:\n    pass"),
    ]

    for name, code in tests:
        result = await service.execute(SandboxRequest(code=code, timeout_seconds=5))
        print(f"[{name}]")
        print(f"  status:   {result.status}")
        print(f"  stdout:   {result.stdout.strip()[:80]!r}")
        print(f"  stderr:   {result.stderr.strip()[:80]!r}")
        print(f"  duration: {result.duration_ms} ms")
        print()

    print("Code executed safely ✓")


if __name__ == "__main__":
    use_real = "--real" in sys.argv
    asyncio.run(main(use_real))
