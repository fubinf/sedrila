import os
import tempfile

import gnupg
import pytest

import mycrypt
import tests.testbase as tb


def test_asymmetric():
    """
    Tests the system-keyring path end-to-end against the repo's throwaway keypair,
    so no personal GPG key and no passphrase are involved.
    """
    with tb.throwaway_gpg_home() as fingerprint:
        plaintext = b"abcdefgh"
        ciphertext = mycrypt.encrypt_gpg(plaintext, [fingerprint])
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
    Tests the isolated pubkey_data path end-to-end against the repo's throwaway keypair:
    encryption happens in encrypt_gpg's own scratch keyring, decryption in ours.
    """
    with tb.throwaway_gpg_home() as fingerprint:
        exported = gnupg.GPG().export_keys(fingerprint)
        assert exported, "throwaway public key is not exportable"
        plaintext = b"isolated path test"
        ciphertext = mycrypt.encrypt_gpg(plaintext, [fingerprint],
                                         pubkey_data={fingerprint: exported})
        decrypted = mycrypt.decrypt_gpg(ciphertext)
    assert plaintext == decrypted
