"""Offline builder for a Wolf named-profile Steam lobby launch.

Mirrors the documented Wolf-UI CreateLobby -> JoinLobby request shape. Does not
make network requests, create a lobby, or grant authorization. The caller MUST
remain a privileged host-side broker that authenticates the requesting device.
Wolf access-control bypass and session races still need engineering/test work.
"""
import re
import secrets

from owner_access import PolicyError, resolve_games, named_steam_profiles

RUNNER_NAME = re.compile(r"[A-Za-z0-9_.-]{1,100}\Z")
LOBBY_ID = re.compile(r"[A-Za-z0-9_-]{1,128}\Z")


def _inventory(result, field, limit):
    if (not isinstance(result, dict) or result.get("success") is not True
            or not isinstance(result.get(field), list) or
            len(result[field]) > limit or
            any(not isinstance(item, dict) for item in result[field])):
        raise PolicyError("Invalid Wolf " + field + " inventory")
    return result[field]


def _positive_int(value, max_value):
    return type(value) is int and 0 < value <= max_value


def _single_steam_app(profiles_reply, profile_id):
    candidates = named_steam_profiles(profiles_reply)
    if profile_id not in candidates:
        raise PolicyError("Authorized named Steam profile is unavailable")
    matches = [p for p in profiles_reply["profiles"] if p.get("id") == profile_id]
    if len(matches) != 1:
        raise PolicyError("Ambiguous Wolf Steam profile identity")
    apps = [a for a in matches[0]["apps"] if a.get("title") == "Steam"]
    if len(apps) != 1:
        raise PolicyError("Ambiguous Steam application in owner profile")
    app = apps[0]
    runner = app.get("runner")
    if not isinstance(runner, dict) or not RUNNER_NAME.fullmatch(str(runner.get("name", ""))):
        raise PolicyError("Unsupported Steam runner state identity")
    # State path comes from a server-verified profile and runner, never client input.
    folder = f'profile-data/{profile_id}/{runner["name"]}'
    render_node = app.get("render_node")
    if not isinstance(render_node, str) or not render_node:
        raise PolicyError("Wolf Steam render node unavailable")
    return app, runner, folder


def plan_owner_steam_lobby(
    owner_policy, client_id, clients_reply, profiles_reply,
    apps_reply, sessions_reply, lobbies_reply, *, video_caps="",
    pin_digits=None,
):
    """Prepare private lobby requests, or refuse if existing state is not idle.

    The request bodies are confidential internal host-agent data, NOT a client
    response. Returning them to a client would leak the lobby PIN and runner
    configuration. This is a preparation step, not an atomic lease/admission.
    """
    binding = resolve_games(owner_policy, client_id, clients_reply)
    profile_id = binding["wolf_profile_id"]
    app, runner, state_folder = _single_steam_app(profiles_reply, profile_id)

    apps = _inventory(apps_reply, "apps", 256)
    wolf_ui = [a for a in apps if a.get("title") == "Wolf UI"]
    if len(wolf_ui) != 1 or not isinstance(wolf_ui[0].get("id"), str):
        raise PolicyError("Ambiguous or missing Wolf UI direct application")
    app_id = wolf_ui[0]["id"]
    if not app_id:
        raise PolicyError("Wolf UI application ID missing")

    sessions = _inventory(sessions_reply, "sessions", 256)
    matches = [s for s in sessions if s.get("client_id") == client_id]
    if len(matches) != 1 or matches[0].get("app_id") != app_id:
        raise PolicyError("Owner must have one active Wolf UI Moonlight session")
    # For initial one-owner launch, refuse ANY other active session. A direct
    # legacy Steam stream may still point at the same state through old
    # symlinks, and Wolf does not expose a reliable alias-aware writer lock.
    if len(sessions) != 1:
        raise PolicyError("Another Wolf session is active; safe handoff not yet implemented")
    s = matches[0]
    if (not _positive_int(s.get("video_width"), 16384) or
            not _positive_int(s.get("video_height"), 16384) or
            not _positive_int(s.get("video_refresh_rate"), 240) or
            not _positive_int(s.get("audio_channel_count"), 16) or
            not isinstance(s.get("client_settings"), dict)):
        raise PolicyError("Active Wolf UI session settings are incomplete")

    lobbies = _inventory(lobbies_reply, "lobbies", 256)
    # A disconnected Wolf-UI lobby can retain the same Steam writable home.
    # Even if connected_sessions is empty, refuse a second writer.
    if lobbies:
        raise PolicyError("Existing Wolf lobby; reconnect or stop it safely before launching")

    if not isinstance(video_caps, str) or len(video_caps) > 512 or
            "\x00" in video_caps or "\n" in video_caps:
        raise PolicyError("Invalid host video caps")
    if pin_digits is None:
        pin_digits = [secrets.randbelow(10) for _ in range(8)]
    if (not isinstance(pin_digits, list) or len(pin_digits) != 8 or
            any(type(x) is not int or x < 0 or x > 9 for x in pin_digits)):
        raise PolicyError("Invalid private lobby PIN")

    create_body = {
        "profile_id": profile_id,
        "name": "Steam",
        "icon_png_path": app.get("icon_png_path"),
        "multi_user": False,
        # A private PIN helps prevent arbitrary joins; it does NOT restrict
        # Wolf direct app access. A host-side entitlement gateway is still needed.
        "pin": list(pin_digits),
        "stop_when_everyone_leaves": False,
        "runner_state_folder": state_folder,
        "runner": runner,
        "video_settings": {
            "width": s["video_width"],
            "height": s["video_height"],
            "refresh_rate": s["video_refresh_rate"],
            "runner_render_node": app["render_node"],
            "wayland_render_node": app["render_node"],
            "video_producer_buffer_caps": video_caps,
        },
        "audio_settings": {"channel_count": s["audio_channel_count"]},
        "client_settings": s["client_settings"],
    }
    # Wolf-UI's session identifier matches its Wolf session client_id.
    # Must be verified on a disposable physical stream before performing POST.
    return {
        "action": "prepare_private_lobby",
        "create_path": "/api/v1/lobbies/create",
        "create_body": create_body,
        "join_path": "/api/v1/lobbies/join",
        "join_template": {
            "lobby_id": None,  # populate ONLY from a validated successful create response
            "moonlight_session_id": client_id,
            "pin": list(pin_digits),
        },
        "workspace_id": binding["workspace_id"],
    }


def fill_join_lobby(plan, create_result):
    """Complete a pending join only with Wolf's valid successful lobby id."""
    if (not isinstance(create_result, dict) or create_result.get("success") is not True
            or not isinstance(create_result.get("lobby_id"), str) or
            not LOBBY_ID.fullmatch(create_result["lobby_id"])):
        raise PolicyError("Wolf failed to create a valid private lobby")
    if not isinstance(plan, dict) or plan.get("action") != "prepare_private_lobby":
        raise PolicyError("Invalid owner lobby plan")
    body = dict(plan["join_template"])
    body["lobby_id"] = create_result["lobby_id"]
    return body
