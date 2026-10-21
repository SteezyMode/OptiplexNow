"""Minimal, local-only Docker adapter for a future NOW Host deployment controller.

There is intentionally no command-line deployment entry point. The adapter is
not wired into the application, and the runtime controller keeps live use
disabled pending clean-host acceptance. No shell invocation or remote daemon.
"""
from __future__ import annotations

import json
import os
from pathlib import Path
import re
import shutil
import stat
import subprocess

MAX_RESULT = 32768
ID_RE = re.compile(r"^[0-9a-f]{64}$")
PROJECT = "optiplex-now-host-pilot"
PROFILE = "now-manual-review-required"
OWNED = "prototype"
LOCAL_SOCKET = Path("/var/run/docker.sock")


class DockerError(RuntimeError):
    pass


def valid_id(value: str) -> str:
    if not isinstance(value, str) or not ID_RE.fullmatch(value):
        raise DockerError("Invalid Docker container identifier")
    return value


class LocalDocker:
    """Limited allowlisted Docker operations, never a generic Docker shell."""

    # An explicit local socket avoids accidentally addressing DOCKER_HOST or
    # user-selected remote Docker contexts. Access still carries root-equivalent
    # privileges and must not be granted to ordinary NOW client users.
    def __init__(self, *, executable: str | None = None,
                 socket_path: Path = LOCAL_SOCKET):
        found = executable or shutil.which("docker")
        if not found or not Path(found).is_absolute():
            raise DockerError("Local Docker executable not available")
        try:
            mode = socket_path.stat().st_mode
        except OSError as exc:
            raise DockerError("Local Docker socket unavailable") from exc
        if not stat.S_ISSOCK(mode) or socket_path != LOCAL_SOCKET:
            raise DockerError("Only the system Docker Unix socket is permitted")
        self.executable = found
        self.base = [found, "--host", "unix:///var/run/docker.sock"]
        self.env = {key: value for key, value in os.environ.items()
                    if not (key.startswith("DOCKER_") or key.startswith("COMPOSE_"))}
        self.env["DOCKER_CONFIG"] = "/nonexistent/now-host-docker-config"

    def _call(self, args: list[str], *, timeout: int = 12) -> str:
        try:
            result = subprocess.run(
                self.base + args, env=self.env, stdin=subprocess.DEVNULL,
                stdout=subprocess.PIPE, stderr=subprocess.PIPE, text=True,
                timeout=timeout, check=False,
            )
        except (OSError, subprocess.TimeoutExpired) as exc:
            raise DockerError("Docker command failed or timed out") from exc
        if result.returncode != 0:
            # Never leak daemon stderr, environment, Docker config or user data.
            raise DockerError("Docker operation failed")
        if len(result.stdout) > MAX_RESULT:
            raise DockerError("Docker response exceeds limit")
        return result.stdout

    def project_ids(self) -> tuple[str, ...]:
        value = self._call(
            ["ps", "--all", "--no-trunc", "--filter", f"label=com.docker.compose.project={PROJECT}",
             "--format", "{{.ID}}"])
        ids = [valid_id(x.strip()) for x in value.splitlines() if x.strip()]
        if len(ids) != len(set(ids)):
            raise DockerError("Duplicate Docker container identity")
        return tuple(ids)

    def has_image(self, image: str) -> bool:
        if (not isinstance(image, str) or
                not re.fullmatch(r"ghcr\.io/games-on-whales/wolf@sha256:[0-9a-f]{64}",
                                 image)):
            raise DockerError("Invalid immutable Wolf image")
        try:
            value = self._call(["image", "inspect", "--format", "{{.Id}}", image])
        except DockerError:
            return False
        return bool(re.fullmatch(r"sha256:[0-9a-f]{64}", value.strip()))

    def has_driver_volume(self, name: str) -> bool:
        if name != "now-nvidia-driver-vol":
            raise DockerError("Unexpected driver volume name")
        try:
            output = self._call(["volume", "inspect", "--format", "{{.Name}}", name])
        except DockerError:
            return False
        return output.strip() == name

    def inspect_owned(self, container_id: str, expected_image: str) -> dict:
        """Require exact full ID, managed labels AND immutable image.

        Labels are an organizational boundary, not proof against another
        process with administrative Docker access. The caller must separately
        match the full ID to its durable per-attempt journal.
        """
        cid = valid_id(container_id)
        if (not isinstance(expected_image, str) or
                not re.fullmatch(
                    r"ghcr\.io/games-on-whales/wolf@sha256:[0-9a-f]{64}",
                    expected_image)):
            raise DockerError("Expected pinned Wolf image is missing")
        inspected_id = self._call([
            "inspect", "--type", "container", "--format", "{{.Id}}", cid]).strip()
        if inspected_id != cid:
            raise DockerError("Full container identity changed")
        actual_image = self._call([
            "inspect", "--type", "container", "--format",
            "{{.Config.Image}}", cid]).strip()
        if actual_image != expected_image:
            raise DockerError("Managed container image digest does not match")
        value = self._call([
            "inspect", "--type", "container", "--format",
            "{{json .Config.Labels}}", cid])
        try:
            labels = json.loads(value)
        except ValueError as exc:
            raise DockerError("Malformed Docker ownership response") from exc
        if not isinstance(labels, dict) or any(
            labels.get(key) != expected for key, expected in (
                ("com.docker.compose.project", PROJECT),
                ("com.docker.compose.service", "wolf"),
                ("io.optiplex-now.managed", OWNED),
                ("io.optiplex-now.role", "streaming"),
            )
        ):
            raise DockerError("Unowned or ambiguous container; refusing operation")
        state_value = self._call([
            "inspect", "--type", "container", "--format",
            "{{json .State}}", cid])
        try:
            state = json.loads(state_value)
        except ValueError as exc:
            raise DockerError("Malformed Docker state response") from exc
        if not isinstance(state, dict) or not isinstance(state.get("Running"), bool):
            raise DockerError("Docker state is incomplete")
        health = state.get("Health")
        status = health.get("Status") if isinstance(health, dict) else None
        if status is not None and status not in (
                "starting", "healthy", "unhealthy"):
            raise DockerError("Unrecognized Docker health status")
        return {
            "id": cid,
            "image": actual_image,
            "running": state["Running"],
            "health": status if status is not None else "not_configured",
        }

    def start_once(self, compose_file: Path) -> None:
        """Create/start Wolf, but never pull images or recreate existing services."""
        # The runtime controller validates the parent workspace and file
        # before calling this adapter. This is not a public generic command.
        self._call([
            "compose", "-p", PROJECT, "-f", str(compose_file),
            "--profile", PROFILE, "up", "--detach", "--no-deps",
            "--no-build", "--no-recreate", "--pull", "never", "wolf",
        ], timeout=45)

    def remove_owned(self, container_id: str, expected_image: str) -> None:
        """Cleanup of an exact journal-listed, positively identified ID only.

        No volume deletion. Caller must hold the exclusive NOW transaction
        lock, match the journal and prove this is the only current project ID.
        """
        cid = valid_id(container_id)
        identity = self.inspect_owned(cid, expected_image)
        if identity["id"] != cid or identity["image"] != expected_image:
            raise DockerError("Unexpected container identity; refusing removal")
        self._call(["rm", "--force", cid], timeout=20)
