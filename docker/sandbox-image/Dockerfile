# Minimal, hardened runtime for executing untrusted AI-generated Python.
# This image is NEVER exposed to the network at runtime (network_mode=none
# is set by the caller), but we still keep it lean and drop anything that
# could aid an attacker who found a container-escape bug.

FROM python:3.11-slim

# Only what Scenario A/B actually need. Add packages deliberately,
# not speculatively - every extra package is extra attack surface.
RUN pip install --no-cache-dir \
    pandas==2.2.2 \
    numpy==1.26.4 \
    openpyxl==3.1.2

# Remove setuid/setgid binaries as defense in depth against
# privilege-escalation inside the container.
RUN find / -xdev -perm -4000 -exec chmod a-s {} \; 2>/dev/null || true

WORKDIR /workspace

# Container is always run with --user 65534:65534 (nobody) by the
# caller, so no USER directive is required here, but we still avoid
# leaving world-writable directories around.
RUN chmod 555 /workspace

# No CMD/ENTRYPOINT - the caller always passes an explicit command
# (python /workspace/input/script.py), so there's no default behavior
# to accidentally rely on or exploit.
