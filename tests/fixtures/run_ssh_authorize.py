#!/usr/bin/env python3
"""Test-only adapter that invokes the real SSH authorization module.

The installed app always uses its fixed root-owned GTK askpass path. Only this
test subprocess replaces the module's ASKPASS constant with a temporary,
noninteractive file, so CI can exercise main() without an installed .deb.
"""
import importlib.util
import os
from pathlib import Path
import subprocess
import sys

source = Path(__file__).resolve().parents[2] / "src" / "ssh-authorize.py"
spec = importlib.util.spec_from_file_location("now_ssh_authorize_fixture", source)
module = importlib.util.module_from_spec(spec)
spec.loader.exec_module(module)

askpass = os.environ["NOW_TEST_ASKPASS"]
if not Path(askpass).is_file():
    raise SystemExit("Test askpass fixture missing")
module.ASKPASS = askpass
sys.argv = [str(source), *sys.argv[1:]]
try:
    module.main()
except (OSError, ValueError, subprocess.CalledProcessError,
        subprocess.TimeoutExpired) as error:
    print("AUTHORIZATION_FAILED: " + type(error).__name__)
    sys.exit(1)
