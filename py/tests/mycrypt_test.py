import os
import tempfile

import gnupg
import pytest

import mycrypt


@pytest.fixture(scope="module")
def gpg_test_key():
    """
    Creates a temporary GPG key without passphrase in the system keyring.
    Yields the fingerprint for use in tests, then deletes the key on teardown.
    No external setup required.
    """
    gpg = gnupg.GPG()
    input_data = gpg.gen_key_input(
        key_type='RSA',
        key_length=2048,
        name_real='Sedrila Autotest',
        name_email='sedrila-autotest@localhost',
        expire_date='1d',
        no_protection=True,
    )
    key = gpg.gen_key(input_data)
    fingerprint = str(key)
    yield fingerprint
    gpg.delete_keys(fingerprint, True, expect_passphrase=False)  # secret key
    gpg.delete_keys(fingerprint)                                  # public key


def test_asymmetric(gpg_test_key):
    """Encrypt and decrypt roundtrip using a temporary key without passphrase."""
    plaintext = b"abcdefgh"
    ciphertext = mycrypt.encrypt_gpg(plaintext, [gpg_test_key])
    decrypted = mycrypt.decrypt_gpg(ciphertext)
    assert plaintext == decrypted


def test_asymmetric_with_system_key():
    """
    Optional: tests with the real passphrase-protected system key.
    Requires $SEDRILA_MYCRYPTTEST_FINGERPRINTS to be set and pinentry-mac installed.
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
    """encrypt_gpg cleans up the temporary GPG directory even when encryption fails."""
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


def test_encrypt_with_pubkey_data_asymmetric(gpg_test_key):
    """Tests the isolated pubkey_data path end-to-end using a temporary key."""
    gpg = gnupg.GPG()
    pubkey_str = gpg.export_keys(gpg_test_key)
    pubkey_data = {gpg_test_key: pubkey_str}
    plaintext = b"isolated path test"
    ciphertext = mycrypt.encrypt_gpg(plaintext, [gpg_test_key], pubkey_data=pubkey_data)
    decrypted = mycrypt.decrypt_gpg(ciphertext)
    assert plaintext == decrypted
