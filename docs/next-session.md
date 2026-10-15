# Next session

Project: personal OptiPlex Now Linux launcher and server management.

Main branch is the working 1.11.9 client. Draft PR #1 adds a Wolf NVIDIA driver maintenance helper to the future 1.12.0 package. The PR is not merged or released, and automated driver recovery has not been end-to-end tested.

Before deployment, review and test the helper, its rollback path, and the Debian package build. Do not assume that the server's optional systemd drop-in was enabled; check on the host. Keep remote client installs separate from host service installation.

Next development targets: reliable maintenance agent, existing-server adoption, new-server provisioning, modular services, backups and recovery. Preserve all game, media and service data. Avoid marketing copy. Use feature branches and draft pull requests for unfinished work.

When troubleshooting on the reference Linux server, provide one terminal command at a time.
