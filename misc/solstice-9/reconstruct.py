#!/usr/bin/env python3
"""Rebuild the 96-byte fixture and local Ed25519 seed from decoded captures."""

from pathlib import Path

from cryptography.hazmat.primitives.asymmetric.ed25519 import Ed25519PrivateKey
from cryptography.hazmat.primitives.serialization import Encoding, PublicFormat


DATA = Path(__file__).resolve().parent / "extracted"

# Validated capture components; see decode.py and the writeup for selection rules.
CONTROLLER = bytes.fromhex(
    "f07fb429318b400792c47765179ff564"
    "02ad956f22989e77868b65099f095d66"
)
EEPROM = bytes.fromhex(
    "3fefc049a89a612a3542d30ecc3952c4"
    "b4171fe14e33a98c0dbad42301529530"
)
SUPERVISOR = bytes.fromhex(
    "6c8737ba4c7a107a4c01f44dc0f42df5"
    "8a36735d3aca1bcaba67191ffea05225"
)


def derive_seed(fixture: bytes) -> bytes:
    if len(fixture) != 96:
        raise ValueError("fixture must contain three 32-byte components")
    seed = bytearray(32)
    for index in range(32):
        rotation = index & 7
        middle = fixture[32 + index]
        rotated = ((middle << rotation) |
                   (middle >> ((-rotation) & 7))) & 0xFF
        seed[index] = (fixture[(7 + 13 * index) & 31] ^
                       fixture[95 - index] ^ rotated)
    return bytes(seed)


def main() -> None:
    fixture = CONTROLLER + EEPROM + SUPERVISOR
    seed = derive_seed(fixture)
    private_key = Ed25519PrivateKey.from_private_bytes(seed)
    public_key = private_key.public_key().public_bytes(Encoding.Raw, PublicFormat.Raw)

    (DATA / "fixture.bin").write_bytes(fixture)
    key_path = DATA / "seed.bin"
    key_path.write_bytes(seed)
    key_path.chmod(0o600)
    print(f"fixture: {DATA / 'fixture.bin'}")
    print(f"private seed: {key_path} (local, gitignored)")
    print(f"public key: {public_key.hex()}")


if __name__ == "__main__":
    main()
