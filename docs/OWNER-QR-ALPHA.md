# Owner phone QR approval — experimental Private Alpha 1 pilot

The client's Games Settings → Request Owner Approval stages a separate
restricted public key. On the currently opt-in owner Tailscale listener it
now displays a locally generated QR code only when the host explicitly reports
that phone approval is enabled. The owner opens the QR link with
their Tailscale-connected phone, checks the six-digit code and key fingerprint
shown on the requesting computer, and taps Approve.

The host checks the **phone's pinned-owner Tailscale WhoIs identity** and
independently inspects the **sole paired active Wolf UI client** before any
restricted owner key is installed. Existing owner policies and the reviewed
forced-command Games/Downloads broker remain mandatory. Ambiguous Wolf
sessions or existing active lobbies prevent approval.

**Limitations:** This does NOT pair Moonlight/Wolf automatically, register
additional users, bypass access checks, enable a new daemon, or deploy a
public website. The owner must pair the new Moonlight device first and
leave its Wolf UI stream active for review. Requests expire after 600
seconds. Phone scanning alone grants nothing. There is no cryptographic
binding between the Wolf certificate and the staged key, so verify the
requesting computer's code/fingerprint and observed Wolf session.

The client .deb depends on the local qrencode binary, generates the QR on
the client using stdin (not a web generator), and packages the host
component without starting it. The opt-in host listener binds only to
the host's Tailscale IP on TCP 18793 and requires the separate
--enable-remote-approval flag and private --owner-id-file, together with
the host's provisioned owner state and restricted broker. Missing
listener means a host-local approval fallback, not a fake QR button.
Browser content uses a strict CSP, no external scripts, no-store
responses, exact Origin/Host checks, and never exposes private keys.
The six-digit code is passed as a URL fragment, not in HTTP GET.

Before enabling on the live reference host, physically verify the
owner phone and client Tailscale access, the negative non-owner case,
Wolf pairing and sole Wolf UI proof, approval followed by restricted
Games verification, and full Steam lifecycle. CI passing is not a
substitute for these tests.
