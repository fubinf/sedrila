# `sedrila` use for instructors

## 1. Preparations

All commands assume a Bash shell.
The sedrila tool assumes a Unix environment.
Under Windows, use WSL.

### Set up `gpg`

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


### Make entry in `sedrila.yaml`

- Send the course organizer your `instructor` entry for your course's `sedrila.yaml`.
  Find a copy of `sedrila.yaml` at `https://courseserver.example.org/path/course/_sedrila.yaml`
  to see what such an entry looks like.
- In that entry, `gitaccount` is your username in the git service used in the course
  and `webaccount` is your username on the webserver serving the course content.


### Set up your workstation

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


## 2. Checking a submission  TODO_2_hofmann: check and correct, add details if needed

- Checking a submission is triggered by the email that the student sent you.
  Copy the repository URL `repo_url`from that email.
- Execute `sedrila instructor --get repo_url`
  to pull the latest commits of that student (or clone the repo if there is no local copy yet)
  and change the current directory into that student's working directory.
- ...
- Alternatively, ...
