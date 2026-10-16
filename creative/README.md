# OptiPlex Studio — standalone creative web tools

Independent optiplex creative web services. The Studio synth and its persistent SQLite projects remain in the separate `studio/` Compose stack. This stack does not edit Caddy.

* **Recorder — AudioMass** — multi-track browser audio editor, `127.0.0.1:18766`. Upstream `pkalogiros/AudioMass`, commit `21f5ee1362a47be6f0dbe6e4969a15e43d21b044`, MIT.
* **Previs — CozyClay** — static browser 3D scene-blocking and camera/animation surface, `127.0.0.1:18769/app/`. Pinned `NomaDamas/CozyClay` commit `1738d7f8ed8fe4c4ffdc9c6d97bc25792512f763`, AGPL-3.0-or-later. Optional AI/agent/motion backends are *not* run or exposed; features requiring them will be unavailable.
* **Hub — OptiPlex Studio** — dashboard, `127.0.0.1:18768`; links to externally configured HTTPS subdomains.
* **Pixel — Piskel** — browser sprite and pixel-animation editor, `127.0.0.1:18767`. Upstream `piskelapp/piskel`, commit `bef52beb312e771bf0cbb915d873e8d638842d7a`, Apache 2.0.

Deployment (on OptiPlex): `cd creative && docker compose up -d --build`

Sanity checks (on OptiPlex): `for port in 18766 18767 18768 18769; do curl --retry 5 --retry-delay 1 -fsSI http://127.0.0.1:$port/; done` (for CozyClay's actual editor, open `/app/`).

All services bind **localhost only**. For a temporary private test on another machine, use SSH `-L` port forwarding. Dedicated HTTPS domain/routes should be configured separately in Caddy after DNS exists and should be kept separate from the Studio project API.

**Important**: These upstream apps primarily edit files in the browser. Hosting them on the server **does not synchronize project files**. Export project files and store them in shared private server storage until proper per-app save/open integration is built. Recording from the microphone requires a browser secure context (e.g. HTTPS or `localhost`). Do not use these as the only copy of work.

**Upcoming**: Native Godot streamed through Wolf, Blockbench, Wick Editor (old tooling), openDAW, durable WebDAV/files interface with account access and versioned backups. Don't publicly expose writeable filesystems or use unverified Docker images.
