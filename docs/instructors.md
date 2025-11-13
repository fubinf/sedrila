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
  Make sure, the key does not expire during the courses for which you intend to use it.
  The simplest approach is to generate a key that never expires.
- List keys: `gpg --list-keys`    
  Note down the key fingerprint of your public key.
  This is the 40-digit hex string shown next to your email address. 
- Export public key:  `gpg --armor --export <keyfingerprint>`  
- Set a useful timeout (e.g. 12 hours) how long `gpg-agent` should keep the passphrase before
  you need to enter it again:  
  https://superuser.com/questions/624343/keep-gnupg-credentials-cached-for-entire-user-session


### 1.2 Make entry in `sedrila.yaml`

- Send the course organizer your `instructor` entry for your course's `sedrila.yaml`.
  See the `instructors` part of your course's equivalent of
  `https://courseserver.example.org/path/course/course.json`
  to see what such an entry looks like.
- In that entry, `gitaccount` is your username in the git service used in the course
  and `webaccount` is your username on the webserver serving the course content.
  The beginning and end line markers for the pubkey are optional.


### 1.3 Set up your workstation

- During your work as instructor of a sedrila course, 
  you need a directory tree into which you will clone and checkout the git repositories
  of all participating students.
  If you work for several such courses, their student directories need to be kept separate.
  Therefore, create a single root-level directory called as you like (e.g. `sedrila/`)
  and create a per-course top-level directory within it; we suggest it be named after the month in which the
  course started (e.g. `2026-04/` for a course starting in April 2026).
- When you call `sedrila instructor`, you need to be in one of these directories.
- Extend your `.bashrc` (or rather `.bash_profile`, if you have one) to set the
  environment variable `EDITOR` to point to the text editor you want to use when 
  `sedrila` starts one. Example: `EDITOR=/usr/bin/emacs`.


### 1.4 Initial cloning of the student repos

- The SeDriLa needs to tell the students to create a git repo on some git server
  and provide read and push rights to each instructor named in the course.
- When they do this, the git server will send you an email message with a link to the repo,
  typically also containing instructions how to clone the repo.
  DO NOT FOLLOW THOSE INSTRUCTIONS AS THEY STAND!
- Instead, for use with `sedrila`, we need to clone the repos into a working directory that is
  named according to the students' git username (not the repo name as would be the default;
  those repos will mostly have similar names).  
  So instead of `git clone git@github.com:myaccount/mysedrilacourse.git`  
  do a `git clone git@github.com:myaccount/mysedrilacourse.git myaccount`
- You need to perform these clone operations manually before you can work on those students' repos
  using `sedrila`.  
  Suggestion: If you are using GitLab, when a student adds you to their repo,
  you will receive notification emails containing a string of the form
  `studentname / reponame`.
  Cloning becomes easy by copy/pasting this string onto your commandline as
  `clonesedrilarepo studentname / reponame`
  after you taught your shell this procedure:
  ```
  clonesedrilarepo() {
      gitserver=git@git.imp.fu-berlin.de  # replace this with yours
      cmd="git clone $gitserver:$1/$3.git $1"
      echo $cmd
      $cmd
  }
  ```


## 2. Checking a submission  

### 2.1 The very first time

Before you check your first submission for a given course, you need to import all
instructors' public keys into your `gpg` so that sedrila can identify the 
"submission.yaml checked" commits of all instructors, not only yourself.

To do so, go to a student directory that contains a proper `student.yaml` file
and call  
`sedrila student --import-keys .`  
This is the only time you will need to call `sedrila student` (as opposed to `sedrila instructor`).

If you do not have a student directory, create one yourself by `git init mytmp; cd mytmp`
and then following the steps described in
"Describing your course participation" in the 
[sedrila user guide for students](../students).

(On the next course, if the set of instructors is different, you can safely do the same routine again.
`gpg` can cope with keys it already has imported previously.)

### 2.2 Regular use

Call `sedrila instructor student1` or  `sedrila instructor student1 student2`,
where `student1` and `student2` are two students' git usernames
and therefore also the names of directories in the course-level top directory
in which the call needs to be made.  
You can call `sedrila` with any number of directories theoretically,
but the ideal case is two, where these students form a work pair and make
corresponding submissions at the same time.
Working with more than four directories at once is hardly practical.

When `sedrila` starts, it will `git pull` the repo and remove all entries from 'submission.yaml'
that do not say "CHECK", unless you have worked on the so-created 'submission.yaml' already
and not committed that work.

`sedrila` then provides a simple menu-driven command loop offering tools for
marking submission items as accepted or rejected: 
  - a webapp (used in the browser and usually the nicest choice)
  - calling your text editor for doing it manually
  - committing+pushing the result when you are done

Several assumptions about the SeDriLa in question are built into the webapp. In particular:

- The underlying SeDriLa prescribes submission filenames and directory structure precisely, 
  so that the directory trees can be merged naturally and corresponding files identified easily.
- For many or most submission files, their basename (without the suffix) will be the name of the
  corresponding task, so that viewer can read `submission.yaml` and then identify (and mark)
  most of those files in the directory tree that are relevant for the current submission.

Based on this, the webapp presents a joint virtual filesystem formed by merging the contents
of several students working directories, points out which students have submitted which tasks,
and (at the file level) allows viewing pairwise differences between two students' exemplars
of the same file.

### 2.3 Protocol checking

For tasks that require command-line execution logs (`.prot` files), `sedrila` provides protocol checking functionality. 
This helps instructors verify student submissions against author-provided solutions.

Basic usage:
```bash
sedrila instructor --check-protocols student_file.prot author_file.prot
```

This compares a student's protocol file with the author's solution and displays a console summary 
of passed/failed/manual-check-required entries with detailed error messages for each mismatch

Example:
```bash
sedrila instructor --check-protocols \
  student-repo/taskname.prot \
  course-repo/altdir/ch/Chapter/Taskgroup/taskname.prot
```

About Path
Todo: The final implementation of the Path handling maybe still needs further discussion; 
the current implementation is documented here: 
- `student-repo/taskname.prot`: Path to student submitted files. 
- `course-repo/.../taskname.prot`: Path to solution `prot` file.
- The CLI uses the supplied paths, whether absolute or relative 
  (resolved against the directory from which the command is executed, typically the course repository). 
  Ensure that these paths correctly reference the intended files.
- For now we keep this plain “type the paths you need” approach.

The comparison checks each command entry based on author-defined rules (`@PROT_CHECK` annotations):
- `Passed`: Command and output match according to rules
- `Failed`: Command or output mismatch
- `Manual check required`: Entries explicitly marked for instructor review

Manual check requirements:
- Entries marked with `command=manual` or `output=manual` always require manual check
- These entries pass automatically but are flagged for instructor review
- Use `manual_note` parameter to provide specific instructions for manual checking

Skip behavior:
- Entries marked with `command=skip` or `output=skip` skip checking entirely
- Skip means the check always passes without requiring manual review
- Use `skip` for commands with no meaningful output (e.g., `cd`)

Important notes:
- Failed entries show detailed error messages (e.g., "command mismatch", "output mismatch")
- Tasks with variable output (HTTP responses, timestamps, etc.) should use `output=manual` 
  rather than `output=skip` to ensure instructor review
- This feature complements (not replaces) the normal submission checking workflow
