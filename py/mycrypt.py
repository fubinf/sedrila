"""Simple facade for asymmetric encryption/decryption."""
import typing as tg
import tempfile
import shutil
import os
import subprocess

import gnupg


def encrypt_gpg(plaintext: bytes, fingerprints: tg.Iterable[str],
                pubkey_data: dict | None = None) -> bytes:
    """
    Encrypts data asymmetrically with the given fingerprints.
    If pubkey_data is provided, creates a temporary isolated GPG environment,
    imports only the needed keys, encrypts, and cleans up without touching the system keyring.
    This allows safe, isolated encryption without side effects.
    """
    fingerprints_list = list(fingerprints)
    # If pubkey_data provided, use temporary isolated GPG environment
    if pubkey_data:
        temp_gpg_home = tempfile.mkdtemp(prefix='sedrila_gpg_')
        try:
            gpg = gnupg.GPG(gnupghome=temp_gpg_home)
            for fp, pubkey_str in pubkey_data.items():
                if fp in fingerprints_list:
                    gpg.import_keys(pubkey_str)
            encrypted = gpg.encrypt(plaintext, fingerprints_list, always_trust=True)
            if not encrypted.ok:
                raise RuntimeError("Encryption failed: " + encrypted.status)
            return encrypted.data
        finally:
            shutil.rmtree(temp_gpg_home, ignore_errors=True)
    else:
        # Use system keyring
        gpg = gnupg.GPG()  # uses ~/.gnupg by default
        encrypted = gpg.encrypt(plaintext, fingerprints_list, always_trust=True)
        if not encrypted.ok:
            raise RuntimeError("Encryption failed: " + encrypted.status)
        return encrypted.data


def decrypt_gpg(ciphertext: bytes, passphrase: str | None = None) -> bytes:
    """
    Decrypts data asymmetrically that was GPG-encrypted with encrypt_gpg().
    Raises exception if no secret key is found in the local keychain for
    any of the pubkeys used in encryption.
    If passphrase is provided, uses it to unlock password-protected private keys.
    """
    # Set GPG_TTY to allow pinentry to prompt for passphrase in terminal
    env = os.environ.copy()
    if 'GPG_TTY' not in env:
        try:
            tty = subprocess.run(['tty'], capture_output=True, text=True, check=False)
            if tty.returncode == 0 and tty.stdout.strip():
                env['GPG_TTY'] = tty.stdout.strip()
        except (OSError, subprocess.SubprocessError):
            pass

    gpg = gnupg.GPG(env=env)  # uses ~/.gnupg by default
    decrypted = gpg.decrypt(ciphertext, always_trust=True, passphrase=passphrase)
    if not decrypted.ok:
        raise RuntimeError("Decryption failed: " + decrypted.status)
    return decrypted.data
