"""Simple facade for asymmetric encryption/decryption."""
import typing as tg

import gnupg


def encrypt_gpg(plaintext: bytes, fingerprints: tg.Iterable[str]) -> bytes:
    """
    Encrypts data asymmetrically with each of the pubkeys that has one of the given fingerprints 
    in the GPG local keyring.
    """
    gpg = gnupg.GPG()  # uses ~/.gnupg by default
    encrypted = gpg.encrypt(plaintext, fingerprints, always_trust=True)
    if not encrypted.ok:
        raise RuntimeError("Encryption failed: " + encrypted.status)
    return encrypted.data


def decrypt_gpg(ciphertext: bytes) -> bytes:
    """
    Decrypts data asymmetrically that was GPG-encrypted with encrypt_gpg().
    Raises exception if no secret key is found in the local keychain for 
    any of the pubkeys used in encryption.
    """
    gpg = gnupg.GPG()  # uses ~/.gnupg by default
    decrypted = gpg.decrypt(ciphertext, always_trust=True)
    if not decrypted.ok:
        raise RuntimeError("Decryption failed: " + decrypted.status)
    return decrypted.data
