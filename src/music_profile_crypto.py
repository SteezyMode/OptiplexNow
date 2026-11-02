"""Authenticated, streaming encryption for owner-only music-server profiles.

Format v2 = MAGIC || salt(16) || nonce(12) || AES-256-GCM ciphertext || tag(16).
Key = PBKDF2-HMAC-SHA256(passphrase, salt, 600_000, 32).
All ciphertext (including the profile manifest) authenticates against HEADER.
Tar creation streams directly through encryption, never creating a plaintext
tarball on disk. Import verifies the complete ciphertext before extraction.

No passwords in CLI arguments, environment variables, or logs.
"""
from __future__ import annotations

import hashlib
import os
from pathlib import Path

from cryptography.exceptions import InvalidTag
from cryptography.hazmat.primitives.ciphers import Cipher, algorithms, modes


MAGIC = b"BRUISER-MUSIC-PROFILE\x02\n"
SALT_BYTES = 16
NONCE_BYTES = 12
TAG_BYTES = 16
ITERATIONS = 600_000
CHUNK_BYTES = 128 * 1024


def validate_passphrase(passphrase: str) -> None:
    if not isinstance(passphrase, str) or not (16 <= len(passphrase) <= 1024):
        raise ValueError("A music backup passphrase must have 16-1024 characters.")
    if "\x00" in passphrase or "\n" in passphrase or "\r" in passphrase:
        raise ValueError("Music backup passphrase contains invalid control characters.")


def _key(passphrase: str, salt: bytes) -> bytes:
    validate_passphrase(passphrase)
    return hashlib.pbkdf2_hmac("sha256", passphrase.encode("utf-8"), salt,
                              ITERATIONS, dklen=32)


class EncryptedWriter:
    """A tarfile-compatible write-only stream (mode w|gz)."""

    def __init__(self, outfile, passphrase: str):
        salt = os.urandom(SALT_BYTES)
        nonce = os.urandom(NONCE_BYTES)
        header = MAGIC + salt + nonce
        key = _key(passphrase, salt)
        self._out = outfile
        self._encryptor = Cipher(algorithms.AES(key), modes.GCM(nonce)).encryptor()
        self._encryptor.authenticate_additional_data(header)
        self._out.write(header)
        self.closed = False

    def write(self, data: bytes) -> int:
        if self.closed:
            raise ValueError("Encrypted music profile stream is closed.")
        if not isinstance(data, (bytes, bytearray, memoryview)):
            raise TypeError("Encrypted writer accepts bytes only.")
        chunk = self._encryptor.update(bytes(data))
        if chunk:
            self._out.write(chunk)
        return len(data)

    def flush(self) -> None:
        self._out.flush()

    def close(self) -> None:
        if self.closed:
            return
        tail = self._encryptor.finalize()
        if tail:
            self._out.write(tail)
        self._out.write(self._encryptor.tag)
        self._out.flush()
        self.closed = True

    def __enter__(self):
        return self

    def __exit__(self, typ, value, traceback):
        if typ is None:
            self.close()
        # If tar creation fails, do not finalize an incomplete backup.
        return False


def is_encrypted(path: Path) -> bool:
    with Path(path).open("rb") as src:
        return src.read(len(MAGIC)) == MAGIC


def decrypt_verified(source: Path, plaintext_destination: Path, passphrase: str) -> None:
    """Verify complete AES-GCM authentication before anybody extracts files.

    Destination must be a private, new, temporary 0600 file and must not
    contain an existing user's data. Caller removes it in a finally block.
    """
    validate_passphrase(passphrase)
    source = Path(source)
    length = source.stat().st_size
    header_length = len(MAGIC) + SALT_BYTES + NONCE_BYTES
    if length < header_length + TAG_BYTES:
        raise ValueError("Encrypted music profile is incomplete.")
    with source.open("rb") as reader:
        header = reader.read(header_length)
        if header[:len(MAGIC)] != MAGIC:
            raise ValueError("Not an encrypted music profile.")
        salt = header[len(MAGIC):len(MAGIC) + SALT_BYTES]
        nonce = header[-NONCE_BYTES:]
        reader.seek(-TAG_BYTES, os.SEEK_END)
        tag = reader.read(TAG_BYTES)
        reader.seek(header_length)
        decryptor = Cipher(algorithms.AES(_key(passphrase, salt)),
                           modes.GCM(nonce, tag)).decryptor()
        decryptor.authenticate_additional_data(header)
        remaining = length - header_length - TAG_BYTES
        fd = os.open(plaintext_destination, os.O_WRONLY | os.O_CREAT | os.O_EXCL,
                     0o600)
        try:
            with os.fdopen(fd, "wb") as output:
                while remaining:
                    cipherchunk = reader.read(min(remaining, CHUNK_BYTES))
                    if not cipherchunk:
                        raise ValueError("Encrypted music profile is truncated.")
                    remaining -= len(cipherchunk)
                    output.write(decryptor.update(cipherchunk))
                try:
                    output.write(decryptor.finalize())
                except InvalidTag as exc:
                    raise ValueError("Music backup passphrase is wrong or archive is damaged.") from exc
                output.flush()
                os.fsync(output.fileno())
        except BaseException:
            Path(plaintext_destination).unlink(missing_ok=True)
            raise
