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
PEM_RE = re.compile(r"-----BEGIN [A-Z ]+-----\n(?:[A-Za-z0-9+/=\n]+)\n-----END [A-Z ]+-----\n?")


def qsettings_bytearray(value):
    if not isinstance(value, str) or not value.startswith("@ByteArray(") or not value.endswith(")"):
        raise ValueError("Moonlight Qt certificate or key is not a QSettings byte array")
    content = value[len("@ByteArray("):-1]
    # Qt INI encoding escapes newlines, backslashes, and may use CRLF.
    content = content.replace(r"\r\n", "\n").replace(r"\n", "\n")
    if len(content) > 16000 or PEM_RE.fullmatch(content) is None:
        raise ValueError("Moonlight Qt stored PEM is malformed")
    return content.encode("ascii")


def identity_from_config(path):
    file = Path(path)
    if not file.is_absolute() or file.is_symlink():
        raise ValueError("Unsafe Moonlight configuration path")
    meta = file.stat()
    if (not stat.S_ISREG(meta.st_mode) or meta.st_uid != os.geteuid()
            or meta.st_nlink != 1 or not 0 < meta.st_size <= MAX_QSETTINGS):
        raise ValueError("Unsafe Moonlight identity configuration")
    conf = configparser.ConfigParser(interpolation=None, strict=True)
    conf.optionxform = str
    with file.open("r", encoding="utf-8") as source:
        conf.read_file(source)
    if not conf.has_section("General"):
        raise ValueError("Moonlight General settings are missing")
    # The default Qt identity manager writes General/certificate and General/key
    # as QByteArray. An AppImage-specific XDG profile may be elsewhere.
    certificate = qsettings_bytearray(conf.get("General", "certificate"))
    private = qsettings_bytearray(conf.get("General", "key"))
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
    """Find one local Moonlight Qt identity without inspecting its secrets."""
    home = Path.home()
    xdg = Path(os.environ.get("XDG_CONFIG_HOME", str(home / ".config")))
    candidates = (
        xdg / "Moonlight Game Streaming Project" / "Moonlight.conf",
        home / ".var/app/com.moonlight_stream.Moonlight/config" /
            "Moonlight Game Streaming Project" / "Moonlight.conf",
    )
    found = [p for p in candidates if p.is_file() and not p.is_symlink()]
    if len(found) != 1:
        raise ValueError("Expected exactly one existing Moonlight Qt identity; "
                         "multiple profiles cannot be guessed")
    return found[0]


def enrollment_challenge(request_id, code, fingerprint):
    if (not re.fullmatch("[0-9a-f]{32}", request_id or "")
            or not re.fullmatch("[0-9]{6}", code or "")
            or not re.fullmatch("[0-9a-f]{20}", fingerprint or "")):
        raise ValueError("Invalid owner enrollment challenge")
    return ("OptiPlex NOW owner-device proof v1\n" + request_id +
            "\n" + code + "\n" + fingerprint + "\n").encode("ascii")
