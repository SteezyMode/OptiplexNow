# OPTIPLEX NOW — Creative Suite, first two apps

Separate from Studio and its saved SQLite projects. Does not change any production Caddy routes.

* **Recorder — AudioMass** — multi-track browser audio editor, `127.0.0.1:18766`. Upstream `pkalogiros/AudioMass`, commit `21f5ee1362a47be6f0dbe6e4969a15e43d21b044`, MIT.
* **Pixel — Piskel** — browser sprite and pixel-animation editor, `127.0.0.1:18767`. Upstream `piskelapp/piskel`, commit `bef52beb312e771bf0cbb915d873e8d638842d7a`, Apache 2.0.

Deployment (on OptiPlex): `cd creative && docker compose up -d --build`

Sanity checks (on OptiPlex): `curl -fsSI http://127.0.0.1:18766/ && curl -fsSI http://127.0.0.1:18767/`

Both services bind **localhost only**. For a temporary private test on another machine, use SSH `-L` port forwarding. Dedicated HTTPS domain/routes should be configured separately in Caddy after DNS exists and should be kept separate from the Studio project API.

**Important**: These upstream apps primarily edit files in the browser. Hosting them on the server **does not synchronize project files**. Export project files and store them in shared private server storage until proper per-app save/open integration is built. Recording from the microphone requires a browser secure context (e.g. HTTPS or `localhost`). Do not use these as the only copy of work.

**Upcoming**: Native Godot streamed through Wolf, Blockbench, Wick Editor, openDAW, durable WebDAV/files interface with account access and versioned backups. Don't publicly expose writeable filesystems or use unverified Docker images.
