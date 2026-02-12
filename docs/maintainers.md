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
- If `files=` field is present: maps file names to paths via the `.files` file,
  copies them into the isolated test directory, and substitutes file names in commands with their actual paths
- Executes commands and compares output
- Generates report: `program_test_report.md` in `targetdir_i`

Examples:

- `sedrila maintainer --check-programs -- /tmp/progtest`
- `sedrila maintainer --batch --check-programs -- /tmp/progtest` (batch mode)

When using `--batch`, test progress is suppressed and failures are summarized at the end for quick CI error identification.

### 5.1 @TEST_SPEC block format

`@TEST_SPEC` blocks contain metadata for automated testing.
Placement and syntax:

- Should be at `.prot` file start (recommended for clarity)
- Block starts with line containing only `@TEST_SPEC`
- Block ends at first blank line
- Inside block: one `key=value` per line, no spaces around `=`
- `lang` and `deps` can span multiple lines (subsequent lines without `=` are appended as separate commands)
- No comments allowed inside @TEST_SPEC block

Supported fields (all optional):

`lang=<install command>`: Language runtime installation command(s) for the target system (e.g., Debian 12).
Can span multiple lines (subsequent lines without `=` are appended as separate install commands).
Examples: `lang=apt-get install -y golang-go`, `lang=apt-get install -y python3-pip`

`deps=<install command>`: Package dependency installation command(s).
Can span multiple lines (subsequent lines without `=` are appended as separate install commands).
Examples: `deps=pip install numpy requests`, `deps=go get github.com/lib/pq`

`files=<list>`: Comma-separated list of additional files used by the program (short names only, e.g., `helper.py`).
Create a corresponding `.files` file in the **altdir** directory (same location as `.prot` file, e.g., `altdir/ch/Sprachen/Go/go-test.files`) with one file path per line.

The `.files` file supports three path formats per line:

- Simple filename (e.g., `data.json`): resolved relative to the `.files` file's directory, for when `.files`, `.prot`, and the referenced file are all in the same directory
- Relative path (e.g., `subdir/data.json`): resolved relative to the `.files` file's directory
- Variable path (e.g., `../../../$itreedir/Sprachen/Go/go-test.go`): `$itreedir` is substituted with the actual path from `sedrila.yaml`

Both the `.files` file and all declared files must exist; missing entries cause errors.

Example with single line `lang`, multiple lines `deps` and `.files`:

```
@TEST_SPEC
lang=apt-get install -y python3-pip
deps=pip install numpy
pip install requests>=2.0
files=py-test.json

@PROT_SPEC
command_re=^python myscript\.py py-test\.json$
output_re=Hello World

$ python myscript.py py-test.json
Hello World
```

During test execution, each command (`$` line) and expected output are extracted as a single test.
Commands execute sequentially in the isolated directory; test passes only if all commands match.
Before testing, generated files are cleaned up to ensure a fresh environment (databases, logs, cache directories).
The temporary directory is removed after testing completes, preventing test failures from residual files.

Dependency chain warnings: If a task appears in a dependency chain between two tasks with `@TEST_SPEC`
but lacks `@TEST_SPEC` itself, a warning is issued during `sedrila author` build and `sedrila maintainer --check-programs`.
Example: `Task 'go-pointers' is missing @TEST_SPEC but appears in dependency chain: go-functions -> go-pointers -> go-http-server`.
These warnings don't interrupt the build or testing; they just indicate potential gaps in test coverage.

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
If multiple tasks have same `lang=` declarations, only unique commands are installed (deduplication).

Package dependencies:

The `deps=` field specifies per-task package dependencies that differ from other tasks in the same taskgroup. Examples:

- `deps=pip install fastapi uvicorn` → install Python packages specific to this task
- `deps=go get github.com/lib/pq@v1.10.0` → install Go dependencies specific to this task

Tasks without a `deps=` field will use only the taskgroup's language runtime without additional dependencies.

The `deps=` field also supports multi-line commands (subsequent lines without `=` are appended).

**Note**: If `.prot` file already contains dependency installation commands in the `@PROT_SPEC` blocks (e.g., `pip install`, `npm install`), these commands will be executed automatically during CI runs. In such cases, you don't need to redundantly declare them in `lang=` or `deps=` fields in `@TEST_SPEC`.

For local testing, need to manually install declared dependencies. For CI, use `--collect` to get the full list.

Installation and execution in CI:

All tests execute serially in a single container with all language runtimes and dependencies installed upfront.
Execution order respects task dependencies (`assumes` and `requires`) via topological sorting.
Each test runs in a temporary isolated directory with only required files; the directory is automatically cleaned up after testing (success or failure).


### 5.3 Automated vs. Manual Testing

Test execution mode is determined automatically by `@PROT_SPEC` block content:

**Automated**: When `@PROT_SPEC` includes `output_re` or `exitcode`, commands execute and output is validated against the specified rules.
Use for deterministic programs with stable or pattern-matchable output.

**Manual**: When `@PROT_SPEC` has neither `output_re` nor `exitcode`, test execution is skipped.
Use for non-deterministic output, interactive programs, timing-dependent behavior, or environment-specific results.
The `manual=` field documents why automated testing is not possible for that protocol block.

