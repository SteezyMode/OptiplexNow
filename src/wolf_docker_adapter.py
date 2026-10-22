"""Fixed Wolf Docker/socket bridge for the future host-local broker.

No network listener. Does NOT authenticate remote NOW clients. Do not wire it
to owner launch in production before upstream Wolf access-control verification.
Wolf API stdout can contain secrets: callers must not log its returned objects.
"""
import json
from pathlib import Path
import subprocess

from wolf_socket_adapter import MAX_RESPONSE, WolfSocketError, check_request

CONTAINER = "wolf"
ADAPTER_FILE = Path(__file__).with_name("wolf_socket_adapter.py")


class WolfDockerAPI:
    def __init__(self, *, runner=subprocess.run):
        self.runner = runner

    def __call__(self, method, path, body=None):
        payload = check_request(method, path, body)
        # Static, reviewed local source. No caller-provided Docker commands,
        # executable paths, Wolf UNIX socket paths, or arbitrary method/path.
        source = ADAPTER_FILE.read_text(encoding="utf-8")
        argv = [
            "docker", "exec", "-i", CONTAINER, "python3", "-c", source,
            method, path,
        ]
        try:
            proc = self.runner(
                argv, input=payload, stdout=subprocess.PIPE,
                stderr=subprocess.DEVNULL, timeout=10, check=False)
        except (OSError, subprocess.TimeoutExpired) as exc:
            raise WolfSocketError("Wolf host-local container command failed") from None
        if proc.returncode != 0:
            raise WolfSocketError("Wolf local API request was refused or unavailable")
        if not isinstance(proc.stdout, bytes) or len(proc.stdout) > MAX_RESPONSE:
            raise WolfSocketError("Wolf local API response exceeds size limit")
        try:
            result = json.loads(proc.stdout)
        except (ValueError, UnicodeDecodeError):
            raise WolfSocketError("Wolf local API returned invalid JSON") from None
        if not isinstance(result, dict):
            raise WolfSocketError("Wolf local API returned invalid response")
        return result
