"""Read-only, fail-closed Wolf identity review for remote owner enrollment.

This module never launches, pairs, authorizes, revokes or reconfigures Wolf.
A sole visible Wolf UI session is useful evidence for *human owner review*,
not proof that the staged SSH key and Wolf certificate came from one device.
"""
from owner_access import PolicyError, paired_client_ids, _valid_client_id


def _inventory(result, field, limit):
    if (not isinstance(result, dict) or result.get("success") is not True
            or not isinstance(result.get(field), list)
            or len(result[field]) > limit
            or any(not isinstance(item, dict) for item in result[field])):
        raise PolicyError("Invalid Wolf inventory for owner device review")
    return result[field]


def single_active_wolf_ui(wolf_api, *, expected_source=None):
    """Return one server-observed paired Wolf UI client ID, or refuse.

    Do not guess a Wolf identity from Tailscale address, nickname or client
    claims. Other active sessions/lobbies make attribution ambiguous.
    No raw app/connection/session JSON is returned: it may contain secrets.
    """
    paired = paired_client_ids(wolf_api("GET", "/api/v1/clients"))
    apps = _inventory(wolf_api("GET", "/api/v1/apps"), "apps", 256)
    candidates = [item.get("id") for item in apps
                  if item.get("title") == "Wolf UI"]
    if (len(candidates) != 1 or not isinstance(candidates[0], str)
            or not candidates[0]):
        raise PolicyError("Wolf UI application unavailable or ambiguous")
    sessions = _inventory(wolf_api("GET", "/api/v1/sessions"), "sessions", 256)
    if len(sessions) != 1:
        raise PolicyError("One active Wolf UI session is required for review")
    session = sessions[0]
    client = session.get("client_id")
    if (not _valid_client_id(client) or client not in paired
            or session.get("app_id") != candidates[0]):
        raise PolicyError("The active session is not one paired Wolf UI")
    if _inventory(wolf_api("GET", "/api/v1/lobbies"), "lobbies", 256):
        raise PolicyError("Active Wolf lobby makes device review ambiguous")
    if expected_source is not None and session.get("client_ip") != expected_source:
        raise PolicyError("Wolf stream origin differs from the staged owner device")
    return client


def approve_reviewed_owner_request(state_dir, request_id, code, selected_client,
                                   *, wolf_api, approval):
    """Apply an *already verified owner-confirmed* request, never self-approve.

    The caller MUST verify the actual remote peer against the installer-pinned
    Tailscale owner ID and require an explicit owner action. The expected client
    ID is independently derived from active Wolf state, not a claimed identity.
    """
    if approval is not True:
        raise PolicyError("Authenticated owner confirmation required")
    observed = single_active_wolf_ui(wolf_api)
    if not _valid_client_id(selected_client) or selected_client != observed:
        raise PolicyError("Owner selection does not match active Wolf UI")
    from owner_enrollment import approve_request
    return approve_request(state_dir, request_id, code, observed,
                           confirmed=True, wolf_api=wolf_api)
