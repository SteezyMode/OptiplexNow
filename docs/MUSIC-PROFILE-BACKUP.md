# Music-server profile backups — encrypted v2 pilot

This is a source-only, opt-in backup migration. It does not change active
Gluetun, slskd, qBittorrent or DroppedNeedle containers, account passwords,
secret locations, service databases, or previous backup archives.

## Risk addressed

The earlier src/server-profile.py generated unencrypted tar.gz archives
including DroppedNeedle encryption keys, account database, service env files
and complete Docker inspection JSON (potentially sensitive environment data).
Restrictive filesystem modes are not encryption.

## New export behavior

- New files must end in .bmprofile and use AES-256-GCM authenticated encryption,
  with a PBKDF2-HMAC-SHA256 passphrase-derived key (600,000 iterations).
- Archive output is streamed directly through encryption, without making a
  plaintext tar.gz on disk during export. Passphrase is confirmed before
  containers are stopped and never passed as an argv or environment value.
- An authenticated v2 manifest excludes containers.json. Encrypted service
  configuration, databases and env files are still necessarily sensitive.
- Owner approval is required. Export temporarily stops the previously running
  music containers for a consistent snapshot and then restarts them.
  DO NOT run against the live host without approval and a maintenance window.
- The output remains create-only with a 0600 temp file and atomic commit.
  Existing archives are never replaced.

## Import / recovery

- The whole envelope is authenticated before extraction. Wrong passwords,
  tampering and truncation must not create a partly restored destination.
- During import only, decrypted tar content temporarily exists under a private
  0700 directory, with the tar file mode 0600; it is removed after import.
  Keep recovery on trusted disks and consider swapping/host-level backups.
- Restores only stage into a new destination directory. They neither install
  nor start Docker services and never overwrite the active music stack.
- Older v1 plaintext archives remain recoverable with explicit IMPORT LEGACY
  confirmation. No automatic deletion or conversion of prior files.

## Acceptance before claiming production-safe backups

1. Verify encrypted export and restore on a disposable four-service test
   installation; compare account/config/library hashes.
2. Test wrong and lost recovery passwords, truncation and deliberate tampering.
3. Test disk-full, interrupted export and failed Docker restart recovery.
4. Test legacy migration and retention without overwriting older archives.
5. Store the recovery passphrase in an independent human password manager,
   not inside the encrypted archive or on the same host as its only backup.
6. Keep this change in a draft PR until CI, host and disaster-restore acceptance.

The separate NOW client encrypted backup in src/backup.c is independent.
