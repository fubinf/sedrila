"""
Simple technical base operations for handling git repos.
Some of it built scruffily by calling git directly, other parts using the GitPython library.
"""
import datetime as dt
import getpass
import os
import re
import subprocess as sp
import typing as tg

import git

import base as b

LOG_FORMAT_SEPARATOR = '\t'
LOG_FORMAT = "%h%x09%ae%x09%at%x09%GF%x09%G?%x09%s"  # see notes at attributes of Commit or git help log "Pretty Formats"


class Commit(tg.NamedTuple):
    hash: str  # %h
    author_email: str  # %ae
    author_date: dt.datetime  # converted from %at
    key_fingerprint: str  # %GF if proper %G? else "-"
    subject: str  # %s (first line of commit msg)


def git_add(filename: str):
    cmd = f"git add {filename}"    
    b.info(cmd)
    os.system(cmd)    


def clone(repo_url: str, targetdir: str):
    os.system(f"git clone {repo_url} {targetdir}")


def make_commit(*filenames, msg, **kwargs):
    for filename in filenames:
        git_add(filename)
    signed = kwargs.pop('signed', False)
    cmd = f"git commit {'-S' if signed else ''} -m '{msg}'"
    b.info(cmd)
    os.system(cmd)


def commits_of_local_repo(*, chronological: bool) -> tg.Sequence[Commit]:
    """Returns all commits in youngest-first order (like git log), or reversed (if chronological)."""
    gitcmd = ["git", "log", f"--format=format:{LOG_FORMAT}"]
    gitrun = sp.run(gitcmd, capture_output=True, encoding='utf8', text=True)
    result = []
    for line in gitrun.stdout.split('\n'):
        try:
            hash_, email, tstamp, fngrprnt, goodness, subj = tuple(line.split(LOG_FORMAT_SEPARATOR))
        except ValueError:
            continue  # an empty repo will result in a format error, but we do not lose anything here
        if fngrprnt and goodness not in "GXYU":  
            # accept good sigs G, expired sigs X, expired keys Y, unknown validity U
            fngrprnt = "-"  # treat as unsigned
        c = Commit(hash_, email, dt.datetime.fromtimestamp(int(tstamp), tz=dt.timezone.utc),
                   fngrprnt, subj)
        result.append(c)
    return list(reversed(result)) if chronological else result


def contents_of_file_version(refid: str, filename: str, encoding=None) -> tg.AnyStr:
    raw = sp.check_output(f"git show {refid}:{filename}", shell=True)
    if encoding:
        return raw.decode(encoding=encoding)
    else:
        return raw


def discard_commits(howmany: int):
    os.system(f"git reset --hard HEAD~{howmany}")


def find_most_recent_commit(regexp: str) -> tg.Optional[Commit]:
    gitlog = commits_of_local_repo(chronological=False)
    for commit in gitlog:
        if re.fullmatch(regexp, commit.subject):
            return commit
    return None


def is_modified(file: str) -> bool:
    """git status: Whether file's content differs from that in the index."""
    repo = git.Repo(odbt=git.GitCmdObjectDB)
    diff = repo.head.commit.diff(other=None, paths=[file])  # diff HEAD vs. working copy
    for _ in diff:  # diff has length 0 or 1
        return True  # if length 1
    return False
    

def origin_remote_of_local_repo() -> str:
    """The local repo's 'origin' remote, which we assume to exist and to be the relevant remote."""
    git_remote = sp.check_output("git remote -v show", shell=True).decode('utf8')
    # e.g.:  origin  git@github.com:myaccount/myrepo.git (fetch)
    fetchremote_regexp = r"origin\s+(\S+)\s+\(fetch\)"
    mm = re.search(fetchremote_regexp, git_remote)
    if not mm:
        b.critical(f"cannot find 'origin' URL in  git remote  output:\n{git_remote}")
    return mm.group(1)


def pull(silent=False):
    if silent:
        try:
            pull_output = sp.check_output("git pull --ff-only", 
                                          stderr=sp.STDOUT, text=True, shell=True)
        except sp.CalledProcessError as err:
            print(f"{os.getcwd()}: {err.stdout}")  # TODO 2: or should we terminate with b.critical()?
    else:
        os.system("git pull --ff-only")


def push():
    os.system("git push")


def remote_url():
    result = sp.run(["git", "config", "--get", "remote.origin.url"], stdout=sp.PIPE)
    return result.stdout.decode("utf-8").strip()

    
def username_from_repo_url(repo_url: str) -> str:
    # a repo_url is git@server:useraccount/reponame.git or git@server:useraccount/subset/reponame.git
    repo_url_regexp = r":([\w_\.-]+)/"
    mm = re.search(repo_url_regexp, repo_url)
    if repo_url.startswith("http") or not mm:
        #for testing purposes, local paths are allowed but default to the current user
        if os.path.isdir(repo_url):
            return getpass.getuser()
        if not mm:
            repo_url_regexp = r"/([\w_\.-]+)/([\w_\.-]+).git"
            mm = re.search(repo_url_regexp, repo_url)
        if mm and mm.group(1):
            return mm.group(1)
        b.critical(f"Git url '{repo_url}' is not usable.\nNeed one like 'git@server:useraccount/reponame.git'.")
    return mm.group(1) if mm else None  # tests will patch b.critical away
