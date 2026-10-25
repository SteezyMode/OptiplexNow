"""Proof-of-possession helper for a Moonlight Qt device certificate.

Prototype only: never uploads or returns the private key. The user-facing
client must first resolve which Moonlight identity/profile is in use.
The on-disk QSettings format is not a stable external API: any ambiguity
fails closed, and this script never changes or recreates Moonlight settings.
"""
import base64
import configparser
import os
from pathlib import Path
import re
import stat

from cryptography import x509
from cryptography.hazmat.primitives import hashes, serialization
from cryptography.hazmat.primitives.asymmetric import padding, rsa

MAX_QSETTINGS = 32768
MAX_PEM = 16000
# Qt QSettings may store the PEM as raw text, @ByteArray(...), quoted
# @ByteArray(...), or a mixture of backslash-escaped newlines.
# Look for the exact PEM block, do not assume an outer Qt wrapper.
PEM_RE = re.compile(
    r"-----BEGIN (?P<label>CERTIFICATE|PRIVATE KEY|RSA PRIVATE KEY)-----"
    r"\s*(?P<body>[A-Za-z0-9+/\s=]+?)\s*"
    r"-----END (?P=label)-----")


def qsettings_pem(value, *, expected):
    """Decode one bounded PEM without printing a Moonlight private key."""
    if not isinstance(value, str) or len(value) > MAX_PEM:
        raise ValueError("Invalid Moonlight Qt encoded identity")
    normalized = (value.replace(r"\r\n", "\n")
                  .replace(r"\n", "\n")
                  .replace(r"\r", "\r")
                  .replace("\r\n", "\n"))
    found = list(PEM_RE.finditer(normalized))
    if len(found) != 1 or found[0].group("label") not in expected:
        raise ValueError("Moonlight identity must contain exactly one PEM block")
    match = found[0]
    body = "".join(match.group("body").split())
    try:
        decoded = base64.b64decode(body, validate=True)
    except (ValueError, base64.binascii.Error) as exc:
        raise ValueError("Moonlight identity base64 is malformed") from exc
    if not 1 <= len(decoded) <= 10000:
        raise ValueError("Moonlight PEM data has invalid length")
    # Canonicalize the PEM spelling. The DER identity/public key is unchanged.
    label = match.group("label")
    wrapped = "\n".join(body[i:i + 64] for i in range(0, len(body), 64))
    return (f"-----BEGIN {label}-----\n{wrapped}\n"
            f"-----END {label}-----\n").encode("ascii")


def identity_from_config(path):
    file = Path(path)
    if not file.is_absolute() or file.is_symlink():
        raise ValueError("Unsafe Moonlight configuration path")
    # Moonlight Qt itself commonly creates a mode-0644 QSettings file.
    # Tighten an OWNED, read-only-to-others, regular file to 0600 locally.
    # Never overwrite its content, follow a symlink, take elevated privilege
    # or silently "repair" a group/world-writable untrusted identity.
    fd = os.open(file, os.O_RDONLY | getattr(os, "O_NOFOLLOW", 0))
    with os.fdopen(fd, "r", encoding="utf-8") as source:
        meta = os.fstat(source.fileno())
        if (not stat.S_ISREG(meta.st_mode) or meta.st_uid != os.geteuid()
                or meta.st_nlink != 1 or not 0 < meta.st_size <= MAX_QSETTINGS
                or meta.st_mode & 0o022):
            raise ValueError("Unsafe or writable Moonlight Qt identity configuration")
        if stat.S_IMODE(meta.st_mode) != 0o600:
            os.fchmod(source.fileno(), 0o600)
        conf = configparser.ConfigParser(interpolation=None, strict=True)
        conf.optionxform = str
        conf.read_file(source)
    if not conf.has_section("General"):
        raise ValueError("Moonlight General settings are missing")
    certificate = qsettings_pem(conf.get("General", "certificate"),
                                expected={"CERTIFICATE"})
    private = qsettings_pem(conf.get("General", "key"),
                            expected={"PRIVATE KEY", "RSA PRIVATE KEY"})
    return certificate, private


def sign_for_request(config_path, challenge):
    if not isinstance(challenge, bytes) or not 1 <= len(challenge) <= 256:
        raise ValueError("Invalid owner proof challenge")
    certificate_pem, private_pem = identity_from_config(config_path)
    cert = x509.load_pem_x509_certificate(certificate_pem)
    key = serialization.load_pem_private_key(private_pem, password=None)
    if (not isinstance(key, rsa.RSAPrivateKey)
            or cert.public_key().public_numbers() != key.public_key().public_numbers()):
        raise ValueError("Moonlight certificate/private key do not match")
    signature = key.sign(challenge, padding.PKCS1v15(), hashes.SHA256())
    return {"certificate_pem": certificate_pem.decode("ascii"),
            "signature_b64": base64.b64encode(signature).decode("ascii")}


def unique_moonlight_config():
    """Return one *identity*, not necessarily one QSettings file.

    Multiple valid native/Flatpak files with an identical certificate AND a
    corresponding usable signing key represent one cryptographic identity.
    Differing identities, stale private keys, or unsafe files fail closed.
    No Wolf/client number is guessed from the profile path.
    """
    home = Path.home()
    xdg = Path(os.environ.get("XDG_CONFIG_HOME", str(home / ".config")))
    candidates = (
        xdg / "Moonlight Game Streaming Project" / "Moonlight.conf",
        home / ".var/app/com.moonlight_stream.Moonlight/config" /
            "Moonlight Game Streaming Project" / "Moonlight.conf",
    )
    found = [p for p in candidates if p.is_file() and not p.is_symlink()]
    if not found:
        raise ValueError("No existing Moonlight Qt identity")
    from cryptography.hazmat.primitives import hashes
    identities = []
    for path in found:
        cert_pem, key_pem = identity_from_config(path)
        cert = x509.load_pem_x509_certificate(cert_pem)
        key = serialization.load_pem_private_key(key_pem, password=None)
        if (not isinstance(key, rsa.RSAPrivateKey)
                or key.public_key().public_numbers() !=
                cert.public_key().public_numbers()):
            raise ValueError("Moonlight Qt profile has mismatched keys")
        identities.append(cert.public_bytes(serialization.Encoding.DER))
    if any(data != identities[0] for data in identities[1:]):
        raise ValueError("Different Moonlight Qt identities require explicit profile selection")
    # Native first when both profiles prove the same identity.
    return found[0]


def enrollment_challenge(request_id, code, fingerprint):
    if (not re.fullmatch("[0-9a-f]{32}", request_id or "")
            or not re.fullmatch("[0-9]{6}", code or "")
            or not re.fullmatch("[0-9a-f]{20}", fingerprint or "")):
        raise ValueError("Invalid owner enrollment challenge")
    return ("OptiPlex NOW owner-device proof v1\n" + request_id +
            "\n" + code + "\n" + fingerprint + "\n").encode("ascii")
