#!/usr/bin/env python3
"""Pinned Wolf real-daemon CreateLobby contract check on disposable CI only.

Not an owner-host script, not an authentication boundary, not a Steam test.
Only executes a single disposable process-runner POST after verifying a
dedicated CI container has zero clients, sessions, and lobbies. No retries,
no Join, no actual Steam, and no raw daemon responses in output.
"""
import argparse
import json
import os
from pathlib import Path
import sys

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "src"))
import probe_real_wolf as isolated

WOLF_IMAGE = ("ghcr.io/games-on-whales/wolf@sha256:"
              "b0ef253739f9bd49b71eba7e150c955fd05990c0d409e666d89236995351551a")

REQUIRED_CREATE = frozenset((
    "profile_id", "name", "multi_user", "pin", "stop_when_everyone_leaves",
    "video_settings", "audio_settings", "client_settings",
    "runner_state_folder", "runner"))
REQUIRED_VIDEO = frozenset((
    "width", "height", "refresh_rate", "wayland_render_node",
    "runner_render_node", "video_producer_buffer_caps"))
REQUIRED_DOCKER = frozenset((
    "type", "name", "image", "mounts", "env", "devices", "ports"))
REQUIRED_JOIN = frozenset(("lobby_id", "moonlight_session_id"))


def verify_schema(schema):
    """Fail on API drift; never infer a successful real Create/Join."""
    if not isinstance(schema, dict):
        raise isolated.ProbeError("Wolf OpenAPI schema is malformed")
    paths = schema.get("paths")
    components = schema.get("components")
    schemas = components.get("schemas") if isinstance(components, dict) else None
    if not isinstance(paths, dict) or not isinstance(schemas, dict):
        raise isolated.ProbeError("Wolf OpenAPI components unavailable")
    for route in ("/api/v1/lobbies/create", "/api/v1/lobbies/join"):
        if not isinstance(paths.get(route), dict) or "post" not in paths[route]:
            raise isolated.ProbeError("Wolf lobby endpoint missing from live schema")
    def require(name, fields):
        item = schemas.get(name)
        if not isinstance(item, dict) or set(item.get("required", [])) != set(fields):
            raise isolated.ProbeError("Wolf lobby required fields have changed")
        return item

    create = require("wolf__api__CreateLobbyRequest", REQUIRED_CREATE)
    video = require("wolf__core__events__VideoSettings", REQUIRED_VIDEO)
    docker = require("wolf__config__AppDocker__tagged", REQUIRED_DOCKER)
    join = require("wolf__core__events__JoinLobbyEvent", REQUIRED_JOIN)

    runner_choices = create.get("properties", {}).get("runner", {}).get("anyOf", [])
    if not any(isinstance(x, dict) and
               x.get("$ref") == "#/components/schemas/wolf__config__AppDocker__tagged"
               for x in runner_choices):
        raise isolated.ProbeError("Wolf Docker runner schema changed")
    if docker.get("properties", {}).get("type", {}).get("enum") != ["docker"]:
        raise isolated.ProbeError("Wolf Docker runner tag changed")
    if (join.get("properties", {}).get("moonlight_session_id", {}).get("type")
            != "string"):
        raise isolated.ProbeError("Wolf Moonlight join ID representation changed")
    for key in REQUIRED_VIDEO:
        if video.get("properties", {}).get(key, {}).get("type") not in ("integer", "string"):
            raise isolated.ProbeError("Wolf video field shape changed")
    return {"schema_compatible": True, "lobby_create_required": len(REQUIRED_CREATE),
            "lobby_join_id_is_string": True, "docker_runner_required": len(REQUIRED_DOCKER)}


def dummy_create_body():
    """Harmless process runner, NOT Steam. Never touches owner profile state."""
    return {
        "profile_id": "now-ci-disposable",
        "name": "NOW Disposable Process Probe",
        "icon_png_path": None,
        "multi_user": False,
        "pin": [4, 2, 4, 2],
        "stop_when_everyone_leaves": True,
        "video_settings": {
            "width": 640, "height": 480, "refresh_rate": 30,
            "wayland_render_node": "software", "runner_render_node": "software",
            "video_producer_buffer_caps": "video/x-raw",
        },
        "audio_settings": {"channel_count": 2},
        "client_settings": None,
        "runner_state_folder": "profile-data/now-ci-disposable/process-probe",
        "runner": {"type": "process", "run_cmd": "sleep 10"},
    }


def invoke(name, method, path, docker_call):
    source = (Path(__file__).resolve().parents[1] / "src" /
              "wolf_socket_adapter.py").read_text(encoding="utf-8")
    raw = docker_call(["exec", "-i", name, "python3", "-c",
                       source, method, path])
    try:
        response = json.loads(raw)
    except (ValueError, UnicodeDecodeError):
        raise isolated.ProbeError("Wolf returned malformed JSON") from None
    if not isinstance(response, dict):
        raise isolated.ProbeError("Wolf API returned non-object")
    return response


def attempt(name, docker_call=isolated.docker, *, ci_run_id=None, runner_temp=None):
    """Perform at most one mutating Create POST on a pinned scratch CI container."""
    if ci_run_id is None:
        ci_run_id = os.getenv("GITHUB_RUN_ID")
    if runner_temp is None:
        runner_temp = os.getenv("RUNNER_TEMP")
    if not isinstance(ci_run_id, str) or not ci_run_id.isdigit() or not runner_temp:
        raise isolated.ProbeError("CI identity required for disposable lobby request")
    expected = "now-wolf-compat-" + ci_run_id
    if name != expected:
        raise isolated.ProbeError("Requested Wolf container is not this CI run")
    info = isolated.inspect_container(name, docker_call)
    scratch = [m["Source"] for m in info["Mounts"] if m.get("Type") == "bind"]
    if (info.get("Config", {}).get("Image") != WOLF_IMAGE or
            len(scratch) != 1 or
            os.path.realpath(scratch[0]) !=
            os.path.realpath(os.path.join(runner_temp, expected))):
        raise isolated.ProbeError("Unexpected pinned image or scratch directory")
    schema = invoke(name, "GET", "/api/v1/openapi-schema", docker_call)
    contract = verify_schema(schema)
    for category in ("clients", "sessions", "lobbies"):
        inventory = invoke(name, "GET", "/api/v1/" + category, docker_call)
        if (inventory.get("success") is not True or
                not isinstance(inventory.get(category), list) or
                inventory[category]):
            raise isolated.ProbeError("Disposable Wolf has nonempty " + category)

    # No duplicate POST, even after timeout/failed response: exiting the CI
    # container discards everything. Existing host lease logic remains separate.
    body = dummy_create_body()
    source = (Path(__file__).resolve().parents[1] / "src" /
              "wolf_socket_adapter.py").read_text(encoding="utf-8")
    argv = ["exec", "-i", name, "python3", "-c", source,
            "POST", "/api/v1/lobbies/create"]
    status = "rejected_or_blocked"
    try:
        raw = docker_call(argv, json.dumps(body).encode("utf-8"))
        response = json.loads(raw)
        if (isinstance(response, dict) and response.get("success") is True
                and isinstance(response.get("lobby_id"), str)
                and response["lobby_id"]):
            status = "created_disposable_lobby"
    except (isolated.ProbeError, ValueError, UnicodeDecodeError):
        pass
    return {
        "probe": "pinned_wolf_lobby_contract", **contract,
        "actual_disposable_create": status,
        "actual_join_executed": False, "actual_moonlight_session": False,
        "actual_steam_state_used": False,
    }


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--container", required=True)
    args = parser.parse_args()
    try:
        print(json.dumps(attempt(args.container), sort_keys=True))
        return 0
    except (isolated.ProbeError, OSError) as exc:
        print(json.dumps({"probe": "pinned_wolf_lobby_contract",
                          "result": "blocked", "reason": str(exc)},
                         sort_keys=True))
        return 2


if __name__ == "__main__":
    raise SystemExit(main())
