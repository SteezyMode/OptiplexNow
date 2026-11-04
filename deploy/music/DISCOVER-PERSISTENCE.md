# Persistent DroppedNeedle Discover repair (v2.15.0)

DroppedNeedle v2.15.0 can indefinitely defer Discover recommendation generation due to a demand-only budget of 10 external operations. See [upstream #588](https://github.com/DroppedNeedle/DroppedNeedle/issues/588) and [Bruiser #259](https://github.com/SteezyMode/OptiplexNow/issues/259).

`install_discover_hotfix.py` applies the user-validated Discover-only budget of **64** to the deployed OptiPlex `~/music-vpn/compose.json` stack. It doesn't alter the desktop .deb, credentials, library data, or music requests.

Run on the host under the existing Docker-capable `optiplex` account:

```sh
python3 deploy/music/install_discover_hotfix.py
```

The installer validates Compose and the existing `droppedneedle` service, checks the five persistent mount destinations, tags the **running container's exact immutable image ID** as a local base, and builds a small derived image with a single patched Python file. It checks the source version and the existing running hotfix, compiles the patched module, saves a backup plus manifest under `~/bruiser-repairs/discover-persistent-<UTC timestamp>/`, and changes **only** `services.droppedneedle.image` in the current `compose.json`. It recreates **only** DroppedNeedle via `docker compose ... up -d --no-deps --force-recreate droppedneedle`, verifies the image and unchanged mount fingerprint, then checks the HTTP health endpoint. If the recreation or health checks fail, it restores Compose and the original service.

This **survives restarts, Compose recreations, and updates to other images** because the production Compose file references the locally built image. Future DroppedNeedle updates are intentionally not automatic: the derived image is pinned to the known-good base until compatibility is reviewed and a replacement is tested. It is not equivalent to a comprehensive upstream fix and has not yet undergone fresh-host end-to-end acceptance.

Verify after installation:

```sh
docker inspect -f 'Image={{.Config.Image}} Status={{.State.Status}}' droppedneedle
python3 - <<'PY'
import json
from pathlib import Path
p = Path.home() / "music-vpn/compose.json"
print(json.loads(p.read_text())["services"]["droppedneedle"]["image"])
PY
```

Open Bruiser → Music → Discover to confirm recommendations. A healthy HTTP endpoint alone does not guarantee Discover populated.

## Rollback

The backup directory printed by the installer contains `compose.before.json` and `patch-manifest.json`. To revert, restore the original `services.droppedneedle.image` value from that backup in the live Compose JSON, validate it with `docker compose -f ~/music-vpn/compose.json config --quiet`, and recreate only `droppedneedle`. Leave data and config mounts untouched.
