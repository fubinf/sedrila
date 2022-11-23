import os
import tempfile

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
