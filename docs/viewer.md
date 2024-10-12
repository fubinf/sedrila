# `sedrila viewer`: browse task solution files

`sedrila viewer` is a webserver tailored to `sedrila`.
Its main purpose is helping instructors view students' solution files.
In particular, it renders command protocols such that they become easy to read.
It also helps students check the correctness of their command protocols.


## 1. Basic use

- Go to the work directory of a student repo.
- Call `sedrila viewer`.
- Visit `http://localhost:8080` in your web browser.
- Viewer reads `student.yaml` and extracts course URL, student name, and partner name.
  It reads `submission.yaml` and obtains the list of tasks mentioned therein.
- Viewer shows a listing of the files (at top) and directories (below) found in the work directory.
  All files whose names start with the name of a task mentioned in `submission.yaml` are highlighted
  in boldface. Behind them, a link to the respective task on the course webpage is shown.
- For the file links:  
    - `*.md` files will be rendered as Markdown.  
    - `*.py`, `*.html`, `*.js`, `*.java` files and many others with known syntax 
      will be rendered with syntax highlighting.  
    - `*.prot` plaintext files will be rendered in color, with highlighting of prompts and commands.
- There is no upward link from a subdirectory on the page. Use the browser's 'Back' button.
- When done, go back to the shell and stop the webserver by pressing Ctrl-C.


## 2. Options

- `--port 8003`: Make `viewer` use some other port (here: port 8003)
- `--instructor`: The task link will point at the instructor version of the website
  rather than the student version. 
  This will only work if the structure generated by `sedrila author` is kept, 
  where the instructor site is a subdirectory of the student site.

That's all.