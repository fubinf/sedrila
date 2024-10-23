"""Technical operations for reading information from git repos."""
import dataclasses
import datetime as dt
import getpass
import os
import re
import subprocess as sp
import typing as tg

import base as b

LOG_FORMAT_SEPARATOR = '\t'
LOG_FORMAT = "%h%x09%ae%x09%at%x09%GF%x09%s"  # see notes at attributes of Commit or git help log "Pretty Formats"

class Commit(tg.NamedTuple):
    hash: str  # %h
    author_email: str  # %ae
    author_date: dt.datetime  # converted from %at
    key_fingerprint: str  # %GF
    subject: str  # %s


def add(filename: str):
    os.system(f"git add {filename}")    


def clone(repo_url: str, targetdir: str):
    os.system(f"git clone {repo_url} {targetdir}")


def commit(*filenames, msg, **kwargs):
    for filename in filenames:
        add(filename)
    signed = kwargs.pop('signed', False)
    os.system(f"git commit {'-S ' if signed else ''}-m'{msg}'")


def commits_of_local_repo(reverse=False, with_insertions_deletions=False) -> tg.Sequence[Commit]:
    """Returns all commits in youngest-first order (like git log), or reversed."""
    if with_insertions_deletions:
        return commits_of_local_repo_with_insertions_deletions(reverse)
    gitcmd = ["git", "log", f"--format=format:{LOG_FORMAT}"]
    gitrun = sp.run(gitcmd, capture_output=True, encoding='utf8', text=True)
    result = []
    for line in gitrun.stdout.split('\n'):
        hash_, email, tstamp, fngrprnt, subj = tuple(line.split(LOG_FORMAT_SEPARATOR))
        c = Commit(hash_, email, dt.datetime.fromtimestamp(int(tstamp), tz=dt.timezone.utc),
                   fngrprnt, subj)
        result.append(c)
    return list(reversed(result)) if reverse else result


def commits_of_local_repo_with_insertions_deletions(reverse=False):
    gitcmd = ["git", "log", f"--format=format:{LOG_FORMAT}", "--shortstat"]
    # produces a 3-line block per commit:
    # d0ac3d8 author@domain       1725618158              Testabgrenzung.md: feedback to question the need for this task again at the end
    #  1 file changed, 2 insertions(+), 1 deletion(-)
    # 
    # where line 1 is TAB-delimited, line2 is text in varying formats, and line3 is empty.
    gitrun = sp.run(gitcmd, capture_output=True, encoding='utf8', text=True)
    result = []
    for block in gitrun.stdout.split('\n\n'):
        print("#####", block, block.split('\n'))
        lines = block.split('\n')  # infoline, statline, emptyline
        hash_, email, tstamp, fngrprnt, subj = tuple(lines[0].split(LOG_FORMAT_SEPARATOR))
        mm = re.search(r'((?P<files>\d+) file.+)?((?P<insertions>\d+) insertion.+)?((?P<deletions>\d+) deletion)?',
                       lines[1])
        if mm:
            files = int(mm.group("files")) if mm.group("files") else 0
            insertions = int(mm.group("insertions")) if mm.group("insertions") else 0
            deletions = int(mm.group("deletions")) if mm.group("deletions") else 0
        else:
            files = insertions = deletions = 0
        c = Commit(hash_, email, 
                   dt.datetime.fromtimestamp(int(tstamp), tz=dt.timezone.utc),
                   fngrprnt, subj,
                   files, insertions, deletions)
        result.append(c)
    return list(reversed(result)) if reverse else result


def contents_of_file_version(refid: str, filename: str, encoding=None) -> tg.AnyStr:
    raw = sp.check_output(f"git show {refid}:{filename}", shell=True)
    if encoding:
        return raw.decode(encoding=encoding)
    else:
        return raw


def discard_commits(howmany: int):
    os.system(f"git reset --hard HEAD~{howmany}")


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
                                          stderr=sp.STDOUT, shell=True).decode('utf8')
        except sp.CalledProcessError as err:
            print(err.stdout)
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
