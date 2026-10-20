# NOW existing-client connection demo (beta)

**Purpose:** Demonstrate that the **already existing NOW GTK system-tray client** can be installed on a second computer, connected to an **already prepared** server, and used through the same GUI. No new home screen, guest dashboard, registration website, bundled host installation, or separate NOW account is part of this demo.

## General product architecture

NOW is intended for ordinary people to install **their own clients and servers on their own compatible hardware**, without any dependence on the developer's particular OptiPlex. A NOW-compatible host can be the developer's reference system for a demo, a different personal PC, a home server, or a remote server the user is authorized to access. The product name is temporary and does not identify a fixed machine, a central backend, or a hosted service.

**The existing beta GUI is the user experience to preserve.** It currently includes the tray, Setup Wizard, Moonlight/Wolf streaming shortcuts, web/media/download links, SSH/SFTP, status, host controls, portable presets and encrypted backups. Improving initial connection must preserve these workflows and config compatibility.

## Practical minimum-flow demo

1. Install the current NOW Linux client on a **different compatible Linux computer**.
2. Use its existing **Tailscale authorization** (or complete the official Tailscale login for that computer). For a first beta demonstration, manually signing in to Tailscale before launching NOW is acceptable; seamless in-app sign-in is a later client improvement. Do **not** embed personal account credentials in the installer.
3. Open **NOW → Settings → Setup Wizard → Find server on Tailscale**. Select a **preconfigured** reachable host, regardless of its physical hardware or who operates it.
4. Complete SSH host-key/user authorization and native Moonlight pairing only where the **existing features being exercised** require them. Configure links such as Jellyfin only if that host runs those services.
5. Use the **existing tray/GUI**, launch Moonlight or service links and verify that they reach the selected server. Close and reopen NOW. Check that host settings are retained without repeating setup.
6. Test the client on the same LAN and from a different network where Tailscale routes and permissions allow it.

## Actual product gaps (do not claim solved)

- Current NOW 1.14.0 is a **Debian/Ubuntu x86-64 Linux client**. A Windows client is **not built**. Demonstrating on a Windows work laptop first requires a separate, tested Windows port; a .deb will not install there.
- Tailscale login inside NOW, fully automatic first-time Moonlight pairing, and zero-touch import of all service addresses/credentials **are not implemented**. The existing Setup Wizard/connection preset is the available beta path.
- NOW cannot bypass the server's SSH authorization, Moonlight pairing, Jellyfin login, or Tailscale device authorization. Minimize prompts by securely remembering successful setup, not by copying owner passwords or private device keys.
- The new experimental discovery helper requires a separately started host presence agent and actual Tailscale interoperability testing. It is not required for the existing Setup Wizard's legacy Tailscale device picker.
- The optional pairing-request broker is a **separate future integration**, not part of the beta client's basic host selection, tray interface or service launching.
- The guided fresh-host installer is a later, separate workstream; it must work for **any supported host**, not only a reference machine.

## Development priorities

1. **Test the existing beta client on a second Linux machine without changing the host:** installer → existing Tailscale login → existing Setup Wizard → current tray shortcuts → reconnect.
2. Fix any observed client-only errors. Preserve the current GTK appearance, config, and shortcuts.
3. Reduce the number of manual client steps and remove hardcoded assumptions about server hostnames, services, Linux usernames and local reference hardware; make host metadata optional, not a new dashboard.
4. Implement tested Windows-client support if the selected demo device runs Windows.
5. Progress fresh-host setup and advanced paired device authorization on independent branches only when they directly support the agreed user flow.

No existing production Wolf, Tailscale, Caddy, Docker, Jellyfin or Studio services should be modified merely to prove a client setup improvement.
