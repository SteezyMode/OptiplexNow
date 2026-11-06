"""Shared fixed SSH argument vector for owner-approved Downloads clients.

Only argv construction belongs here. Each caller must validate host/user/key,
the requested action and the bounded request/response independently.
Preserve the existing forced-command transport: no shell, no admin key,
no host-provided command, no relaxed host-key policy.
"""


def restricted_ssh_argv(host, user, key):
    """Return the exact v1.22.1 Downloads SSH argv (no subprocess execution).

    This is NOT an authorization or host validation function. All call sites
    must reject unapproved targets and missing device credentials first.
    """
    return [
        "ssh", "-F", "/dev/null", "-T", "-i", str(key),
        "-o", "IdentitiesOnly=yes", "-o", "BatchMode=yes",
        "-o", "StrictHostKeyChecking=yes", "-o", "ConnectTimeout=6",
        f"{user}@{host}",
    ]
