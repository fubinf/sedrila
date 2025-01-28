# `sedrila` use for instructors

## 1. Preparations

All commands assume a Bash shell.
The sedrila tool assumes a Unix environment.
Under Windows, use WSL. `sedrila` does not work natively in Windows.

### 1.1 Set up `gpg`

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
- Set a useful timeout (e.g. 4 hours) how long `gpg-agent` should keep the passphrase before
  you need to enter it again.  
  [HREF::https://superuser.com/questions/624343/keep-gnupg-credentials-cached-for-entire-user-session]

### 1.2 Make entry in `sedrila.yaml`

- Send the course organizer your `instructor` entry for your course's `sedrila.yaml`.
  Find a copy of `sedrila.yaml` at `https://courseserver.example.org/path/course/sedrila.yaml`
  to see what such an entry looks like.
- In that entry, `gitaccount` is your username in the git service used in the course
  and `webaccount` is your username on the webserver serving the course content.
  The beginning and end line markers for the pubkey are optional.


### 1.3 Set up your workstation

Those steps are quality of life aspects only. You can use sedrila without having done this if you
are in an environment where they might cause any issues, even though there shouldn't be any.

#### 1.3.1a Old version (soon to be removed, to be used with `instructor1`)

- During your work as instructor of a sedrila course, 
  you need a directory tree into which you will clone and checkout the git repositories
  of all participating students.
  You can give it any name you want. 
  Here, we refer to it as `SEDRILA_INSTRUCTOR_REPOS_HOME`.
  If you don't have this set, sedrila will assume you are inside of that directory while working.
- Create that top-level directory now.
- Extend your `.bashrc` (or rather `.bash_profile`, if you have one) to include
  `export SEDRILA_INSTRUCTOR_REPOS_HOME=/path/to/repos_home`
- You also need to indicate to sedrila which course URLs you are going to process,
  so it can help you reject all other instances of the course, even if you have been
  an instructor for them in the past.
  To do that, extend your `.bashrc` (or rather `.bash_profile`, if you have one) to include
  a space-separated list of possible URLs, like this:
  `export SEDRILA_INSTRUCTOR_COURSE_URLS="https://our.server/course/semester1 https://our.server/course/semester2"`
- By default, sedrila will spawn a subshell for you to work in during grading. If you want to use
  another command than that, set `SEDRILA_INSTRUCTOR_COMMAND` environment variable accordingly.

#### 1.3.1b New version 

- During your work as instructor of a sedrila course, 
  you need a directory tree into which you will clone and checkout the git repositories
  of all participating students.
  If you work for several such courses, their student directories need to be kept separate.
  Therefore, create a single root-level directory called as you like (e.g. `sedrila/`)
  and create a per-course top-level directory within it, named after the month in which the
  course started (e.g. `2026-04/` for a course starting in April 2026).
- When you call `sedrila instructor`, you need to be in one of these directories.
- Extend your `.bashrc` (or rather `.bash_profile`, if you have one) to set the
  environment variable `EDITOR` to point to the text editor you want to use when 
  `sedrila` starts one. Example: `EDITOR=/usr/bin/emacs`.


### 1.4 Receiving the student repos

- The SeDriLa needs to tell the students to create a git repo on some git server
  and provide read and push rights to each instructor named in the course.
- When they do this, the git server will send you an email message with a link to the repo,
  typically also containing instructions how to clone the repo.
  DO NOT FOLLOW THOSE INSTRUCTIONS AS THEY STAND!
- For use with `sedrila`, we need to clone the repos into a working directory that is
  named according to the students' git username (not the repo name as would be the default;
  those repos will mostly have similar names).  
  So instead of `git clone git@github.com:myaccount/mysedrilacourse.git`  
  do a `git clone git@github.com:myaccount/mysedrilacourse.git myaccount`  
- You need to perform these clone operations manually before you can work on those students' repos
  using `sedrila`.


## 2. Checking a submission  

### 2.1a Old version (soon to be removed, to be used with `instructor1`)

1. Generally speaking, checking a submission is conceptually split into three steps, each of which 
can be skipped via corresponding arguments to `sedrila instructor`.
Those steps are "get", "check" and "put".

2. Checking a submission is triggered by the email that the student sent you.
This email will contain a command of the form `sedrila instructor repo_url`.
If you enter this command, sedrila will change into the folder of that student and will make
sure to pull or clone if necessary; the "get" step. It and can be
skipped if you don't have access to the repository.
It will then spawn a subshell.

3. In this subshell, you are free to do whatever you need in order to assess whether the given
tasks from the student in `submission.yaml` are to be accepted or rejected.
If you open `sedrila` (without any arguments) in this subshell, it will provide an interactive
menu to accept or deny certain tasks, but you can also modify the file by hand.
This is the "check" step and is equivalent to the command `sedrila instructor --interactive --no-get --no-put`.  

4. If you exit the subshell, sedrila will automatically create a signed commit for you, containing
the current state of the `submission.yaml` file and push that.
You are free to do multiple commits for a single submission mail by the student.
This is the "put" part.
If you prefer not to use the subshell, you can just directly provide the `--interactive` flag.

An alternative flow might be the following:

- `sedrila instructor repo_url --no-check --no-put` to fetch the repo.
- `sedrila instructor repo_url --interactive --no-get --no-put` to actually do grading.
- `sedrila instructor repo_url --no-get --no-check` to create the commit and push it.

Providing `repo_url` is optional if you are already in the directory of the repo.
For reducing the confusion in case of mistakes, we recommend to always provide `repo_url`.

In case you mis-graded something and the student has already worked on top of that,
you can make overrides by prefixing the marks with OVERRIDE_, i.e. OVERRIDE_ACCEPT
or OVERRIDE_REJECT. This will replace a previous wrong grade with an ACCEPT or
REJECT respectively. An entry with OVERRIDE_ACCEPT will make a previous REJECT
count as ACCEPT instead.

There is an `--override` argument that will make the interactive mode only show
previous tasks and will automatically add the required prefix. This will also
work as an argument in the subshell, i.e. `sedrila --override` will work.

### 2.1b New version

Call `sedrila instructor student1 student2`,
where `student1` and `student2` are two students' git usernames
and therefore also the names of directories in the course-level top directory
in which the call needs to be made.  
You can call `sedrila` with any number of directories theoretically,
but the ideal case is two, where these students form a work pair and make
corresponding submissions at the same time.
Working with more than four directories at once is hardly practical.

- When `sedrila` starts, it will ask, for each directory, whether it should `git pull` the repo.
  Usually your answer is yes if there is a fresh submission, but perhaps no upon continueing calls later.
- `sedrila` provides a simple menu-driven command loop for calling various tools for
  marking submission items as accepted or rejected: 
    - the `sedrila viewer` (used in the browser and usually the nicest choice once 
      accept/reject functionality will be implemented which right now it is not)
    - interactive dialog in the terminal
    - the text editor of your choice
- When you are done, select `push` to commit and push some or all of the submissions.

(Some details from the above Old version are also relevant for the New version.)