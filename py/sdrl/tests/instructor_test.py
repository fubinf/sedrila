import os
import shutil
import tempfile

import git
import sdrl.course
import sdrl.repo as r
import sdrl.subcmd.instructor as sut  # system under test

TEST_REPO = "git@github.com:fubinf/sedrila-test1.git"
METADATA_FILE = f"{os.path.dirname(__file__)}/data/{sdrl.course.METADATA_FILE}"

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


def test_instructor_parts():
    """Deep-integrationey test. Accesses external server, creates+deletes directories etc."""
    with TempDirEnvironContextMgr(HOME=".") as mgr:
        os.environ[sut.REPOS_HOME_VAR] = mgr.newdir  # will not be unpatched; not a problem
        #----- test clone:
        sut.checkout_student_repo(TEST_REPO, home=mgr.newdir)  # will clone
        assert os.getcwd().endswith(git.username_from_repo_url(TEST_REPO))
        #----- test pull:
        sut.checkout_student_repo(TEST_REPO, home=mgr.newdir)  # will pull and get "Already up to date."
        assert os.getcwd().endswith(git.username_from_repo_url(TEST_REPO))
        #----- make pseudo-coursedir:
        os.mkdir('out')
        shutil.copy(METADATA_FILE, 'out')
        #----- read data from repo:
        course = sdrl.course.Course(f"out/{sdrl.course.METADATA_FILE}", read_contentfiles=False)
        r.compute_student_work_so_far(course)
        entries, workhours_total, timevalue_total = r.student_work_so_far(course)
        print(entries)
        assert False