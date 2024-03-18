# `sedrila` use for instructors

## 1. Preparations  TODO 2: add details

- install `sedrila`
- install and setup `gpg`
  - install

    ```bash
    sudo apt install gnupg
    ```

    of follow instrauction on [GnuPG](https://gnupg.org/download/index.html)

  - generate key
  
    ```bash
    gpg --full-generate-key
    ```

  - list keys

    ```bash
    gpg --list-keys
    ```

  - export public key

    ```bash
    gpg --armor --export [public-id from prev step] > public_key.asc
    ```

  - import public keys from student

    ```bash
    gpg --import [path to the file with public keys]
    ```

    Nice to know:

  - encrypt mail

    ```bash
    gpg --encrypt --recipient [recipient key-id] [filename]
    ```

  - sign mail
  
    ```bash
    gpg --sign [filename]
    ```

- create key pair
- report fingerprint to course author (main instructor)
- create repos dir and set `SEDRILA_INSTRUCTOR_REPOS_HOME` environment variable
- set `SEDRILA_INSTRUCTOR_COMMAND` environment variable


## 2. Checking a submission  TODO 2: add details

- receive command by email
- execute command
- follow instructions