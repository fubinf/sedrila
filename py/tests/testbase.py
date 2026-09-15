import contextlib
import os
import shutil
import subprocess
import tempfile

import gnupg

import base as b
import cache
import sdrl.directory

# The repo's own throwaway keypair (see the header comment in the .asc file), used by
# throwaway_gpg_home() so that no test needs a personal GPG key:
THROWAWAY_SECKEY_FILE = os.path.join(os.path.dirname(__file__),
                                     "..", "sdrl", "tests", "data",
                                     "prot-test-instructor-seckey.asc")
THROWAWAY_FINGERPRINT = "C72724404C29E973D851563C32529CAC47C6EB6E"

class TempDirEnvironContextMgr(tempfile.TemporaryDirectory):
    """
    Context manager which (1) creates/deletes temporary directory,
    (2) changes into it and back to original dir,
    (3) patches os.environ according to constructor **kwargs on entry
    (4) adds the temporary dir as _CONTEXT_TEMPDIR, and
    (5) unpatches environment on exit.
    None means environment variable is not set.
    Naively works with the default string encoding.
    Useful for automated tests.
    A typical usecase is a test involving the use of implicit dotfiles in $HOME.
    """
    def __init__(self, suffix=None, prefix=None, dir=None,
                 **kwargs):
        super().__init__(suffix=suffix, prefix=prefix, dir=dir)
        self.env_patch = kwargs
        self.origdir = os.getcwd()

    def __enter__(self):
        self.newdir = super().__enter__()
        self.origdir = os.getcwd()
        os.chdir(self.newdir)
        self.env_orig = dict()
        self.env_patch['_CONTEXT_TEMPDIR'] = self.newdir
        for key, newvalue in self.env_patch.items():
            origvalue = os.environ.get(key)
            self.env_orig[key] = origvalue  # value or None
            if newvalue is None:
                if origvalue is not None:
                    del os.environ[key]
            else: 
                os.environ[key] = newvalue
        return self

    def __exit__(self, exc_type, exc_val, exc_tb):
        os.chdir(self.origdir)  # avoid deletion-related problems
        super().__exit__(exc_type, exc_val, exc_tb)
        for key, oldvalue in self.env_orig.items():
            patchedvalue = os.environ.get(key)
            if oldvalue is None:
                if patchedvalue is not None:
                    del os.environ[key]
            else:
                os.environ[key] = oldvalue



@contextlib.contextmanager
def throwaway_gpg_home():
    """
    Context manager which (1) creates/deletes a temporary GNUPGHOME containing only the
    repo's throwaway keypair, (2) points $GNUPGHOME at it and restores the original value
    on exit, and (3) kills only that home's gpg-agent, never the user's.
    Yields the fingerprint of the throwaway key, as reported by the import.
    Lets tests encrypt and decrypt without any personal key and without touching ~/.gnupg.
    Unlike TempDirEnvironContextMgr, it does not chdir: callers are often already chdir'd.
    """
    gpghome = tempfile.mkdtemp(prefix="sedrila_testgpg_")
    os.chmod(gpghome, 0o700)  # gpg refuses a home others can read
    env_orig = os.environ.get("GNUPGHOME")  # value or None
    try:
        os.environ["GNUPGHOME"] = gpghome
        result = gnupg.GPG(gnupghome=gpghome).import_keys(b.slurp(THROWAWAY_SECKEY_FILE))
        fingerprints = set(result.fingerprints)
        assert fingerprints == {THROWAWAY_FINGERPRINT}, \
            f"{THROWAWAY_SECKEY_FILE} holds {fingerprints}, not {THROWAWAY_FINGERPRINT}"
        yield THROWAWAY_FINGERPRINT
    finally:
        if env_orig is None:
            del os.environ["GNUPGHOME"]
        else:
            os.environ["GNUPGHOME"] = env_orig
        subprocess.run(["gpgconf", "--homedir", gpghome, "--kill", "gpg-agent"],
                       check=False, capture_output=True)
        shutil.rmtree(gpghome, ignore_errors=True)


def get_directory() -> sdrl.directory.Directory:
    return sdrl.directory.Directory(cache.SedrilaCache("", False))