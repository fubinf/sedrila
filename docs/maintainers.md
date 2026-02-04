# `sedrila` use for people defending a SeDriLa against the ravages of time

**All functionality described herein is in alpha development stage and is subject to change!**

## 1. Purpose and use cases

Course content degrades over time: External links break, example programs fail as dependencies evolve.
The `sedrila maintainer` subcommand provides automated quality checks for:

- Link checking: Validate HTTP/HTTPS URLs in markdown files
- Program testing: Run example programs and verify their output

Unlike `sedrila author` (full course build generating HTML), maintainer tools perform 
quality checks only, operating directly on source files for speed.
Use in local development, CI pipelines, or scheduled maintenance runs.

## 2. Prerequisites

For checking all files: Requires a valid `sedrila.yaml` configuration file in the current directory 
(or specify via `--config <configfile>`).
The configuration file must define `chapterdir` and other course structure settings.
For checking single files: Only that specific file needs to exist.

Function-specific requirements:

- Link checking: Active internet connection.
- Program testing: Runtime environments for tested languages, details in section 5.1.
  The course configuration must provide compatible `chapterdir`, `altdir`, and `itreedir`
  settings so that task markdowns, protocol files, and program sources can be matched.


## 3. Basic command structure

```bash
sedrila maintainer [options] targetdir
```

Function options:

- `--check-links [markdown_file]`: Check URLs for availability
- `--check-programs [program_file]`: Test programs

Common options:

- `--config <configfile>`: Specify configuration file (default: `sedrila.yaml`)
- `--include-stage <stage>`: Include parts with this and higher stage entries (default: `draft` which includes all stages)
- `--log <level>`: Set logging level (DEBUG, INFO, WARNING, ERROR, CRITICAL)
- `--batch`: Use batch/CI-friendly output

Positional arguments:

- `targetdir`: Base directory for reports (required). Reports are written to `targetdir_i` (targetdir + "_i" suffix), 
  following sedrila's convention of separating instructor content from student content.

### 3.1 CI/Batch mode

For automated testing environments, the `--batch` flag produces concise output suitable 
for CI systems like Github Actions. The exit status is non-zero (1) when tests fail and zero (0) on success.

All failed tests are summarized at the end of the output for quick error identification,
making it easy to spot issues in automated test runs.
Markdown reports are always generated regardless of output mode.

Scheduled execution runs link checking every Sunday at 03:00 UTC and program testing 
at 03:30 UTC.
Both Actions workflows use the `--batch` flag for CI-friendly output.


## 4. Link Checking: `--check-links`

Option `--check-links [markdown_file]` validates external HTTP/HTTPS links found in markdown files.

Link checking is implemented as a `maintainer` subcommand but leverages 
the `author` build system infrastructure for file identification. 

When checking all files, the command:

Creates a `Coursebuilder` instance to parse `sedrila.yaml`

Builds only the essential elements needed for file identification:

- `Sourcefile`: Registers all source files
- `Topmatter`: Parses YAML metadata from markdown files
- `MetadataDerivation`: Processes metadata and evaluates stage filtering

Extracts the list of markdown files that need checking (respecting configuration and stages)

Checks links and generates reports as build products 

- Without a file argument, it checks all course files using the build system to identify files. 
(respects `sedrila.yaml` configuration, only checks configured taskgroups). 
- With a file argument, it checks only that specific file.
- Uses the `--include-stage` option to control which development stages are checked (default: `draft`, which includes all stages).
- Checks both `chapterdir` and `altdir` directories (`altdir` discovered via path replacement).
- Uses HEAD requests by default for efficiency, falling back to GET only when content validation is needed.
- Generates a fixed-name markdown report: `link_check_report.md` in `targetdir_i`.
- Supports custom link validation rules via HTML comments in markdown files.
- Avoids checking duplicate URLs and includes comprehensive statistics in reports.
- When checking all files, use `--` to separate options from the positional `targetdir` argument.
- Link checking automatically sends HTTP requests in parallel when `--batch` is used. You can change the worker count via the `SDRL_LINKCHECK_MAX_WORKERS` environment variable (default: `230`). 
- In a local environment (like WSL), adjust the concurrency by running `export SDRL_LINKCHECK_MAX_WORKERS=Number` (For a PC, setting this value to the current number of CPU threads would be appropriate.) and then executing `sedrila maintainer --check-links`. 
  use `echo "$SDRL_LINKCHECK_MAX_WORKERS"` to check current value of this variable.
- For CI runs triggered through GitHub Actions, the `maintainer-linkchecker` workflow exposes a `max_workers` input when using the “Run workflow” button, which internally sets this environment variable before executing the command. Empirical runs show that setting `max_workers` to roughly `230` already reaches the practical performance limit; higher numbers rarely improve performance. 

Examples:

- `sedrila maintainer --check-links -- /tmp/linkcheck` (check all course files, all stages)
- `sedrila maintainer --include-stage beta --check-links -- /tmp/linkcheck` (check only beta stage)
- `sedrila maintainer --check-links ch/Chapter1/Task1.md /tmp/linkcheck` (check one specific file by using its absolute or relative path)

By default, links are considered successful if they return 2xx or 3xx status codes.
You can specify custom validation rules using HTML comments before links:

```markdown
<!-- @LINK_SPEC: status=403 -->
[Restricted Resource](https://example.com/restricted)

<!-- @LINK_SPEC: content="Welcome" -->
[Must contain text](https://example.com/)

<!-- @LINK_SPEC: status=302, timeout=30, ignore_cert=true -->
[Complex validation](https://redirect.example.com)
```

Available rule parameters:

- `status=N`: Expect specific HTTP status code (e.g., `status=404` for intentionally broken links)
- `content="text"`: Verify page contains the given text (triggers GET request instead of HEAD)
- `timeout=N`: Use custom timeout in seconds (default: 20)
- `ignore_cert=true`: Skip certificate validation

The validation rule applies (only) to the next link found.

## 5. Program Testing: `--check-programs`

Option `--check-programs -- <report_dir>` tests exemplary programs against protocol files.

Program testing executes stored commands from `.prot` files and verifies output matches expected results.

How it works:

- Scans `.prot` files in `altdir` for `@TEST_SPEC` blocks
- Extracts metadata: language, dependencies, test type
- Locates program files in `itreedir` via path replacement
- If `files=` field is present: maps short file names to absolute paths via the `.files` file,
  then substitutes file names in test commands with their absolute paths, in order to test programs
  in `.files` file automatically
- Executes commands and compares output
- Generates report: `program_test_report.md` in `targetdir_i`

Examples:

- `sedrila maintainer --check-programs -- /tmp/progtest`
- `sedrila maintainer --batch --check-programs -- /tmp/progtest` (batch mode)

Concurrency control via `SDRL_PROGCHECK_MAX_WORKERS` (default: 4, recommended for local: CPU thread count):

```bash
export SDRL_PROGCHECK_MAX_WORKERS=4
sedrila maintainer --check-programs -- /tmp/progtest
```

For CI via GitHub Actions, the workflow exposes `max_workers` input.
When using `--batch`, failed tests are summarized at the end for quick error identification in CI runs.

### 5.1 @TEST_SPEC block format

`@TEST_SPEC` blocks contain metadata for automated testing.
Placement and syntax:

- Should be at `.prot` file start (recommended for clarity)
- Block starts with line containing only `@TEST_SPEC`
- Block ends at first blank line
- Inside block: one `key=value` per line, no spaces around `=`
- `lang` and `deps` can span multiple lines (subsequent lines without `=` are appended as separate commands)
- No comments allowed inside @TEST_SPEC block

Example:

```
@TEST_SPEC
lang=apt-get install -y python3-pip
deps=pip install numpy
pip install requests>=2.0
typ=regex

@PROT_SPEC
command_re=^python myscript\.py$
output_re=Hello World

$ python myscript.py
Hello World
```

Required fields:

`typ=<test type>`: One of `regex`, `manual`

Optional fields:

`lang=<install command>`: Language runtime installation command(s) for the target system (e.g., Debian 12).
Can span multiple lines (subsequent lines without `=` are appended as separate install commands).
Examples: `lang=apt-get install -y golang-go`, `lang=apt-get install -y python3-pip`

`deps=<install command>`: Package dependency installation command(s).
Can span multiple lines (subsequent lines without `=` are appended as separate install commands).
Examples: `deps=pip install numpy requests`, `deps=go get github.com/lib/pq`

`manual_reason=<text>`: Required when `typ=manual`. Explains why manual testing is needed.
Example: `manual_reason=Output contains timestamps`

`files=<list>`: Comma-separated list of additional files used by the program (short names only, e.g., `helper.py`).
Create a corresponding `.files` file in the **altdir** directory (same location as `.prot` file, e.g., `altdir/ch/Sprachen/Go/go-test.files`) with one file path per line.

The `.files` file supports the `$` variable for relative paths. Example for `itreedir`:

```
../../../$itreedir/Sprachen/Go/go-test.go
../../../$itreedir/Sprachen/Go/go-test_extra.go
```

Programchecker automatically reads the `.files` file from altdir, substitutes `$itreedir` variable with the actual path from sedrila.yaml, and resolves relative paths.
If no `.files` file is provided or a file is not listed, programchecker looks for it in the same directory as the `.prot` file.

During test execution, each command (`$` line) and expected output are extracted as a single test.
Commands execute sequentially in the isolated directory; test passes only if all commands match.
Before testing, generated files are cleaned up to ensure a fresh environment (databases, logs, cache directories).
The temporary directory is removed after testing completes, preventing test failures from residual files.

### 5.2 Operating environment and dependencies

Program testing requires language runtimes and package dependencies specified via `@TEST_SPEC` blocks.

Base requirements:

- Python: 3.11 or higher (required for sedrila itself)
- itreedir: Must exist as a directory with program source files

Language runtimes:

The `lang=` field declares installation commands for the language/runtime environment.
Typically specified only in the first/foundational task of a taskgroup, since all tasks in the same taskgroup share the same language runtime.

Examples:

- `lang=apt-get install -y golang-go` → installs Go compiler
- `lang=curl -fL https://golang.org/dl/go1.25.5.linux-amd64.tar.gz | tar -C /usr/local -xz` → installs Go 1.25.5
- `lang=apt-get install -y python3-pip` → installs Python 3 pip

The `lang=` field supports multi-line install commands (subsequent lines without `=` are appended).
If a task group has multiple tasks with `lang=` declarations, only unique commands are installed (deduplication).

Package dependencies:

The `deps=` field specifies per-task package dependencies that differ from other tasks in the same taskgroup. Examples:

- `deps=pip install fastapi uvicorn` → install Python packages specific to this task
- `deps=go get github.com/lib/pq@v1.10.0` → install Go dependencies specific to this task

Tasks without a `deps=` field will use only the taskgroup's language runtime without additional dependencies.

The `deps=` field also supports multi-line commands (subsequent lines without `=` are appended).

For local testing, need to manually install declared dependencies. For CI, use `--collect` to get the full list.

**Installation and execution in CI**:

Two CI configuration approaches are available:

Single-Container Mode:

All taskgroups execute in a single container with all language runtimes and dependencies installed upfront.
Language runtimes are installed once at the beginning, then all taskgroups reuse the same environment.
Tasks within a taskgroup execute serially respecting `assumes` dependencies; different taskgroups execute in parallel.
Each test runs in a temporary isolated directory with only required files; the directory is automatically cleaned up after testing (success or failure).

Example with 2 taskgroups (Go, Python) and 4 workers:
- Worker 1: go-basics → go-functions → go-maps (serial)
- Worker 2: python-basics → FastAPI-GET (serial)
- Workers 3-4: idle

Multi-Container Mode:

For stricter isolation, Multi-Container Mode has also been developed. That means, each taskgroup runs in a dedicated container to avoid language-specific dependency conflicts.
Language runtime and dependencies are installed independently in each container.
Tasks within each taskgroup execute serially in the container, respecting their dependency order.
After all taskgroups complete, their reports are aggregated into a unified report.
This approach provides better isolation but involves more container overhead and is subject to GitHub API rate limits when multiple containers clone the repository simultaneously.


### 5.3 Test types

The `typ=` field in `@TEST_SPEC` determines how a program is tested.

**regex**: Pattern-based output verification

Commands are executed and output matched against regex patterns in `@PROT_SPEC` blocks.

Use `typ=regex` for deterministic programs with stable output or output with acceptable variations.

**manual**: Manual verification required

Test execution is skipped; requires `manual_reason=` field explaining why.

Use `typ=manual` for non-deterministic output, interactive programs, timing-dependent behavior, or environment-specific results.

