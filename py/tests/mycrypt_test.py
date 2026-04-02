import os
import tempfile

import pytest

import mycrypt


def test_asymmetric():
    """
    Requires local GPG setup for the fingerprints listed in $SEDRILA_MYCRYPTTEST_FINGERPRINTS and
    at least one of them must have a secret key.
    If that env variable is not set, the test is skipped.
    """
    fingerprintlist = os.environ.get("SEDRILA_MYCRYPTTEST_FINGERPRINTS", "")
    if not fingerprintlist:
        pytest.skip("SEDRILA_MYCRYPTTEST_FINGERPRINTS not set")
    fingerprints = fingerprintlist.split(",")
    plaintext = b"abcdefgh"
    ciphertext = mycrypt.encrypt_gpg(plaintext, fingerprints)
    decrypted = mycrypt.decrypt_gpg(ciphertext)
    assert plaintext == decrypted


def test_decrypt_garbage_raises_error():
    """decrypt_gpg raises RuntimeError when given non-GPG data."""
    with pytest.raises(RuntimeError, match="Decryption failed"):
        mycrypt.decrypt_gpg(b"this is not valid gpg ciphertext")


def test_encrypt_with_pubkey_data_unmatched_fingerprint_raises_error():
    """
    encrypt_gpg raises RuntimeError when the target fingerprint is not present
    in pubkey_data — no key gets imported, so encryption fails.
    """
    with pytest.raises(RuntimeError, match="Encryption failed"):
        mycrypt.encrypt_gpg(
            b"hello",
            fingerprints=["AAAA1111AAAA1111AAAA1111AAAA1111AAAA1111"],
            pubkey_data={"BBBB2222BBBB2222BBBB2222BBBB2222BBBB2222": "not a real key"},
        )


def test_encrypt_with_pubkey_data_temp_dir_is_cleaned_up():
    """
    encrypt_gpg cleans up the temporary GPG directory even when encryption fails.
    """
    created_dirs = []
    original_mkdtemp = tempfile.mkdtemp

    def tracking_mkdtemp(**kwargs):
        path = original_mkdtemp(**kwargs)
        created_dirs.append(path)
        return path

    import unittest.mock as mock
    with mock.patch("mycrypt.tempfile.mkdtemp", side_effect=tracking_mkdtemp):
        with pytest.raises(RuntimeError):
            mycrypt.encrypt_gpg(
                b"hello",
                fingerprints=["AAAA1111AAAA1111AAAA1111AAAA1111AAAA1111"],
                pubkey_data={"BBBB2222": "not a real key"},
            )

    assert len(created_dirs) == 1, "expected exactly one temp dir to be created"
    assert not os.path.exists(created_dirs[0]), "temp dir was not cleaned up"


def test_encrypt_with_pubkey_data_asymmetric():
    """
    Requires local GPG setup ($SEDRILA_MYCRYPTTEST_FINGERPRINTS) with at least one key
    that has both a public and a secret key available.
    Tests the isolated pubkey_data path end-to-end.
    """
    fingerprintlist = os.environ.get("SEDRILA_MYCRYPTTEST_FINGERPRINTS", "")  # comma-separated
    if not fingerprintlist:
        pytest.skip("SEDRILA_MYCRYPTTEST_FINGERPRINTS not set")
    import gnupg
    fingerprints = fingerprintlist.split(",")
    gpg = gnupg.GPG()
    pubkey_data = {}
    for fp in fingerprints:
        exported = gpg.export_keys(fp)
        if exported:
            pubkey_data[fp] = exported
    if not pubkey_data:
        pytest.skip("no exportable public keys found for given fingerprints")
    plaintext = b"isolated path test"
    ciphertext = mycrypt.encrypt_gpg(plaintext, fingerprints, pubkey_data=pubkey_data)
    decrypted = mycrypt.decrypt_gpg(ciphertext)
    assert plaintext == decrypted
