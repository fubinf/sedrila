import os

import pytest

import mycrypt

def test_symmetric():
    plaintext = b"abcdefgh"
    ciphertext, key = mycrypt.encrypt_sym(plaintext)
    print("plaintext:", plaintext)
    print("ciphertext:", ciphertext)
    print("key:", key)
    decrypted = mycrypt.decrypt_sym(ciphertext, key)
    print("decrypted text:", decrypted)
    assert plaintext == decrypted


def test_asymmetric():
    """
    Requires local GPG setup for the fingerprints listed in $SEDRILA_MYCRYPTTEST_FINGERPRINTS and
    at least one of them must have a secret key.
    If that env variable is not set, the test is silently skipped.
    """
    fingerprintlist = os.environ.get("SEDRILA_MYCRYPTTEST_FINGERPRINTS", "")
    if not fingerprintlist:
        return
    fingerprints = fingerprintlist.split(",")
    plaintext = b"abcdefgh"
    ciphertext = mycrypt.encrypt_gpg(plaintext, fingerprints)
    print("plaintext:", plaintext)
    print("ciphertext:", ciphertext)
    decrypted = mycrypt.decrypt_gpg(ciphertext)
    print("decrypted text:", decrypted)
    assert plaintext == decrypted
