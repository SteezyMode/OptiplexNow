#!/usr/bin/env python3
"""Isolated pilot for SubDuet English/Japanese SRT pairing (not a Jellyfin installer)."""
from __future__ import annotations
import argparse
import os
from pathlib import Path
import re
import secrets
import subprocess
import sys

REPO = "https://github.com/NLINEA/SubDuet.git"
TAG = "v0.1.0b15"
VIDEO_EXTENSIONS = frozenset({".mkv", ".mp4", ".avi", ".m4v", ".mov", ".ts", ".webm"})
COMPOSE = '''name: now-bilingual-pilot
services:
  worker:
    build:
      context: ./SubDuet
    restart: unless-stopped
    env_file: ./paircue.env
    user: "\${PUID:?missing PUID}:\${PGID:?missing PGID}"
    ports:
      - "127.0.0.1:9294:9292"
    volumes:
      - "\${MEDIA_PATH:?missing MEDIA_PATH}:/media:rw"
      - "./state:/state:rw"
    read_only: true
    tmpfs:
      - /tmp:size=256m,mode=1777
    security_opt:
      - no-new-privileges:true
    cap_drop:
      - ALL
'''


def clean_path(value: str, *, name: str) -> Path:
    if not value or re.search(r'[\r\n\x00"\\:$]', value):
        raise ValueError(f"{name}: path has unsupported characters")
    p = Path(value).expanduser()
    if p.is_symlink():
        raise ValueError(f"{name}: symbolic-link directory refused")
    return p.resolve(strict=False)


def find_sample(root: Path) -> str:
    if not root.is_dir():
        raise ValueError("Media root is not an existing directory")
    for media in root.iterdir():
        if media.is_symlink() or not media.is_file() or media.suffix.lower() not in VIDEO_EXTENSIONS:
            continue
        en = media.with_name(media.stem + ".en.srt")
        ja = media.with_name(media.stem + ".ja.srt")
        if all(p.is_file() and not p.is_symlink() and p.stat().st_size for p in (en, ja)):
            return media.name
    raise ValueError("Copy one video and matching Movie.en.srt + Movie.ja.srt into the test folder")


def env_line(name: str, value: str) -> str:
    if re.search(r'[\r\n\x00"\\$]', value):
        raise ValueError(f"Unsafe value for {name}")
    return f'{name}="{value}"\n'


def build_env(media: Path, uid: int, gid: int, token: str) -> str:
    vals = {
        "MEDIA_PATH": str(media), "PUID": str(uid), "PGID": str(gid),
        "PAIRCUE_PLATFORM": "filesystem", "PAIRCUE_MEDIA_ROOT": "/media",
        "PAIRCUE_STATE_DIR": "/state", "PAIRCUE_SCAN_INTERVAL_SECONDS": "30",
        "PAIRCUE_SOURCE_LANGUAGE": "en", "PAIRCUE_TARGET_LANGUAGE": "ja",
        "PAIRCUE_BILINGUAL_ORDER": "source-first",
        "PAIRCUE_SYNC_ENABLED": "false", "PAIRCUE_TRANSLATION_ENABLED": "false",
        "PAIRCUE_TRANSCRIPTION_ENABLED": "false",
        "PAIRCUE_SUBTITLE_DOWNLOAD_ENABLED": "false",
        "PAIRCUE_WEBHOOK_ENABLED": "false", "PAIRCUE_API_HOST": "0.0.0.0",
        "PAIRCUE_API_PORT": "9292", "PAIRCUE_PORT": "9294",
        "PAIRCUE_TRUSTED_HOSTS": "localhost,127.0.0.1",
        "PAIRCUE_API_TOKEN": token,
    }
    return "".join(env_line(k, v) for k, v in vals.items())


def prepare(media_root: str, workspace: str) -> tuple[Path, str]:
    if os.geteuid() == 0:
        raise ValueError("Run as your regular Linux account, not root")
    media = clean_path(media_root, name="media-root")
    sample = find_sample(media)
    work = clean_path(workspace, name="workspace")
    if work == media or work in media.parents or media in work.parents:
        raise ValueError("Workspace and media test folder must not contain one another")
    if work.exists():
        raise ValueError("Workspace already exists; refusing to change an existing installation")
    work.mkdir(mode=0o700, parents=True, exist_ok=False)
    (work / "state").mkdir(mode=0o700)
    config = work / "paircue.env"
    fd = os.open(config, os.O_WRONLY | os.O_CREAT | os.O_EXCL, 0o600)
    with os.fdopen(fd, "w", encoding="utf-8") as f:
        f.write(build_env(media, os.getuid(), os.getgid(), secrets.token_urlsafe(32)))
    (work / "compose.yaml").write_text(COMPOSE, encoding="utf-8")
    return work, sample


def run_cmd(args: list[str]) -> None:
    subprocess.run(args, check=True)


def docker_args(work: Path, *args: str) -> list[str]:
    return ["docker", "compose", "-f", str(work / "compose.yaml"), "--env-file", str(work / "paircue.env"), *args]


def start(work: Path) -> None:
    if not (work / "compose.yaml").is_file() or not (work / "paircue.env").is_file():
        raise ValueError("No prepared pilot found; run prepare first")
    source = work / "SubDuet"
    if not source.exists():
        run_cmd(["git", "clone", "--depth", "1", "--branch", TAG, REPO, str(source)])
    if not (source / ".git").exists():
        raise ValueError("SubDuet source does not look like a Git checkout")
    head = subprocess.check_output(["git", "-C", str(source), "rev-parse", "HEAD"], text=True).strip()
    tag = subprocess.check_output(["git", "-C", str(source), "rev-list", "-n", "1", TAG], text=True).strip()
    if not head or head != tag:
        raise ValueError(f"SubDuet checkout is not at {TAG}; refusing to start")
    run_cmd(docker_args(work, "build", "worker"))
    run_cmd(docker_args(work, "run", "--rm", "worker", "subduet", "doctor"))
    run_cmd(docker_args(work, "up", "-d", "worker"))


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description="Safe, optional English/Japanese SubDuet pilot")
    sub = parser.add_subparsers(dest="command", required=True)
    default_work = str(Path.home() / ".local/share/bilingual-subtitles-pilot")
    prep = sub.add_parser("prepare", help="Create separate config without starting Docker")
    prep.add_argument("--media-root", required=True, help="Folder with a COPY of a movie and .en/.ja.srt")
    prep.add_argument("--workspace", default=default_work)
    for command in ("start", "stop", "status"):
        p = sub.add_parser(command)
        p.add_argument("--workspace", default=default_work)
    args = parser.parse_args(argv)
    try:
        if args.command == "prepare":
            work, name = prepare(args.media_root, args.workspace)
            print(f"Prepared pilot in {work}\nTest movie: {name}\nNothing installed or started. Run 'start' when ready.")
        else:
            work = clean_path(args.workspace, name="workspace")
            if args.command == "start":
                start(work)
                print("Pilot started; inspect the copied folder for a .mul.srt and review the result.")
            else:
                if not (work / "compose.yaml").is_file() or not (work / "paircue.env").is_file():
                    raise ValueError("No prepared pilot found")
                run_cmd(docker_args(work, "down" if args.command == "stop" else "ps"))
    except (ValueError, OSError, subprocess.CalledProcessError) as exc:
        print(f"Pilot: {exc}", file=sys.stderr)
        return 1
    return 0

if __name__ == "__main__":
    sys.exit(main())
