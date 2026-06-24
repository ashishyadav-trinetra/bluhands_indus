"""Generate an RS256 JWT keypair into ``secrets/`` (cross-platform, no OpenSSL).

Usage:
    python scripts/generate_keys.py            # create if missing
    python scripts/generate_keys.py --force    # overwrite existing keys
"""

from __future__ import annotations

import argparse
from pathlib import Path

from cryptography.hazmat.primitives import serialization
from cryptography.hazmat.primitives.asymmetric import rsa

SECRETS_DIR = Path(__file__).resolve().parent.parent / "secrets"
PRIVATE_PATH = SECRETS_DIR / "jwt_private.pem"
PUBLIC_PATH = SECRETS_DIR / "jwt_public.pem"


def generate(force: bool = False) -> None:
    """Write a 2048-bit RSA keypair as PEM files into ``secrets/``."""
    SECRETS_DIR.mkdir(parents=True, exist_ok=True)

    if (PRIVATE_PATH.exists() or PUBLIC_PATH.exists()) and not force:
        print(f"Keys already exist in {SECRETS_DIR} (use --force to overwrite).")
        return

    key = rsa.generate_private_key(public_exponent=65537, key_size=2048)

    PRIVATE_PATH.write_bytes(
        key.private_bytes(
            encoding=serialization.Encoding.PEM,
            format=serialization.PrivateFormat.PKCS8,
            encryption_algorithm=serialization.NoEncryption(),
        )
    )
    PUBLIC_PATH.write_bytes(
        key.public_key().public_bytes(
            encoding=serialization.Encoding.PEM,
            format=serialization.PublicFormat.SubjectPublicKeyInfo,
        )
    )
    print(f"Wrote:\n  {PRIVATE_PATH}\n  {PUBLIC_PATH}")


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description="Generate RS256 JWT keys.")
    parser.add_argument("--force", action="store_true", help="overwrite existing keys")
    generate(parser.parse_args().force)
