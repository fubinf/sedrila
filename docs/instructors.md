# `sedrila` use for instructors

## 1. Preparations

All commands assume a Bash shell.

## Set up `gpg`

- Install `sedrila`
- Install `gpg`:  
  On Debian/Ubuntu, do `sudo apt install gnupg`.  
  For other platforms, see [GnuPG downloads](https://gnupg.org/download/index.html).
- Generate key: `gpg --full-generate-key`  
  Use the name and email that the students should get to see.
  Make sure, the key does not expire during the course for which you intend to use it.
  The simplest approach is to generate a key that never expires.
- List keys: `gpg --list-keys`    
  Note down the key fingerprint of your public key.
  This is the 40-digit hex string shown next to your email address. 
- Export public key:  `gpg --armor --export <keyfingerprint>`  


## Make entry in `sedrila.yaml`

- Enter email, key fingerprint, and public key in your `instructor` entry in the course's `sedrila.yaml`,
  together with `gitaccount` (your username in the git service used in the course)
  and `webaccount` (your username on the webserver serving the course content).


## Set up your workstation

- During your work as instructor of a sedrila course, 
  you need a directory tree into which you will clone and checkout the git repositories
  of all participating students.
  You can give it any name you want. 
  Here, we refer to it as `SEDRILA_INSTRUCTOR_REPOS_HOME`.
- Create that top-level directory now.
- Extend your `.bashrc` (or rather `.bash_profile`, if you have one) to include
  `export SEDRILA_INSTRUCTOR_REPOS_HOME=/path/to/repos_home`
- You also need to indicate to sedrila which course URLs you are going to process,
  so it can help you reject all other instances of the course, even if you have been
  an instructor for them in the past.
  To do that, extend your `.bashrc` (or rather `.bash_profile`, if you have one) to include
  a space-separated list of possible URLs, like this:
  `export SEDRILA_INSTRUCTOR_COURSE_URLS="https://our.server/course/semester1 https://our.server/course/semester2"`
- set `SEDRILA_INSTRUCTOR_COMMAND` environment variable  TODO_2_hofmann needed? Then explain.


## 2. Checking a submission  TODO 2: add details

- receive command by email
- execute command
- follow instructions