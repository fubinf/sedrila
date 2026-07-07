# `sedrila` use for people defending a SeDriLa against the ravages of time

## 1. Purpose and use cases

Course content degrades over time: External links break, example programs fail as dependencies evolve.
The `sedrila maintainer` subcommand provides automated quality checks for:

- Link checking: Validate HTTP/HTTPS URLs in Markdown files
- Program testing: Run example programs and verify their output

Unlike `sedrila author` (full course build generating HTML), maintainer tools perform 
quality checks only, operating directly on source files rather than near-duplicating the 
build process.
Use in local development, CI pipelines, or scheduled maintenance runs.

The commands assume a setup on which one _could_ run `sedrila author`
(and in fact hardcode some aspects of the default setup) and an internet connection.


## 2. Basic command structure

```bash
sedrila maintainer check-links [options] [--check singlefile] [--batch] targetdir
sedrila maintainer check-programs [options] [--batch] targetdir
sedrila maintainer collect-dependencies [options]
```

Commands:

- `check-links TARGETDIR [--check markdown_file]`: Check URLs for availability
- `check-programs TARGETDIR`: Test programs
- `collect-dependencies [-o output_file]`: Collect languages and dependencies from `@TEST_SPEC` blocks as JSON (default: stdout)

Arguments:

- `--config <configfile>`: Specify configuration file (default: `sedrila.yaml`)
- `--include-stage <stage>`: Include parts with this and higher stage entries (default: `draft` which includes all stages)
- `targetdir`: Base directory for reports. Reports are written to `targetdir_i` (targetdir + "_i" suffix),
  following sedrila's convention of separating instructor content from student content.

**CI/Batch mode:** For automated testing environments, the `--batch` flag produces concise output suitable 
for CI systems like Github Actions. The exit status is non-zero (1) when tests fail and zero (0) on success.

All failed tests are summarized at the end of the output for quick error identification,
making it easy to spot issues in automated test runs.
Markdown reports are always generated regardless of output mode.

In sedrila's original repo https://github.com/fubinf/sedrila, 
scheduled execution runs link checking and program testing once a week.
See there for example configuration and output.


## 3. Link Checking: `check-links`

- Checks both `chapterdir` and `altdir` directories (`altdir` discovered via path replacement).
- Uses HEAD requests by default for efficiency, falling back to GET only when content validation is needed.
- Generates a fixed-name Markdown report: `link_check_report.md` in `targetdir_i`.
- Supports custom link validation rules (see below).
- Avoids re-checking recurring URLs and includes comprehensive statistics in reports.
- Link checking automatically sends HTTP requests in parallel when `--batch` is used. 
  You can change the worker count via the `SDRL_LINKCHECK_MAX_WORKERS` environment variable (default: `120`).
  For CI runs triggered through GitHub Actions, the `maintainer-linkchecker` workflow exposes a 
  `max_workers` input for setting this environment variable.

**Custom rules:** By default, links are considered successful if they return 2xx or 3xx status codes.
You can specify custom validation rules using HTML comments before links.
A validation rule applies only to the next link below it. 
Syntax:

```markdown
<!-- @LINK_SPEC: status=403 -->
[Restricted Resource](https://example.com/restricted)

<!-- @LINK_SPEC: content="Welcome" -->
[Must contain this text](https://example.com/)

<!-- @LINK_SPEC: status=302, timeout=30, ignore_cert=true -->
[Complex validation](https://redirect.example.com)
```

Available rule parameters:

- `status=N`: Expect specific HTTP status code (e.g., `status=404` for intentionally broken links).
  Many servers block requests from bots like the link checker, so `status=403` will often be needed
  although the link works just fine in the webbrowser.
- `content="text"`: Verify page contains the given text (triggers GET request instead of HEAD)
- `timeout=N`: Use custom timeout in seconds (default: 20)
- `ignore_cert=true`: Skip certificate validation


## 5. Program Testing: `check-programs`

Program testing executes stored commands from `.prot` files and verifies output matches expected results.

How it works:

- Scans `.prot` files in `altdir` for `@TEST_SPEC` blocks
- Extracts metadata: language, dependencies, test type
- Locates program files in `itreedir` via path replacement
- If `files=` field is present: maps file names to paths via the `.files` file,
  copies them into the isolated test directory, and substitutes file names in commands with their actual paths
- Executes commands and compares output
- Generates report: `program_test_report.md` in `targetdir_i`


### 5.1 @TEST_SPEC block format

`@TEST_SPEC` blocks contain metadata for automated testing.
Placement and syntax:

- Should be at `.prot` file start (recommended for clarity)
- Block starts with line containing only `@TEST_SPEC`
- Block ends at first blank line
- Inside block: one `key=value` per line, no spaces around `=`
- `lang` and `deps` can span multiple lines (subsequent lines without `=` are appended as separate commands)
- No comments allowed inside @TEST_SPEC block
- Unknown keys produce a warning but do not prevent the file from being included as a test target

Supported fields (all optional):

`lang=<install command>`: Language runtime installation command(s) for the target system (e.g. Debian).
Can span multiple lines (subsequent lines without `=` are appended as separate install commands).
Examples: `lang=apt-get install -y golang-go`, `lang=apt-get install -y python3-pip`

`deps=<install command>`: Package dependency installation command(s).
Can span multiple lines (subsequent lines without `=` are appended as separate install commands).
Examples: `deps=pip install numpy requests`, `deps=go get github.com/lib/pq`

`files=<list>`: Comma-separated list of additional files used by the program (short names only, e.g., `helper.py`).
Create a corresponding `.files` file in the **altdir** directory 
(e.g., `altdir/ch/Sprachen/Go/go-test.files`) with one file path per line.

The `.files` file supports three path formats per line:

- Relative path (e.g., `subdir/data.json`): resolved relative to the `.files` file's directory
- Variable path (e.g., `$itreedir/Sprachen/Go/go-test.go`): `$itreedir` is substituted with the actual path from `sedrila.yaml`

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
but lacks `@TEST_SPEC` itself, a warning is issued during `sedrila author build` and `sedrila maintainer check-programs`.
Example: `Task 'go-pointers' is missing @TEST_SPEC but appears in dependency chain: go-functions -> go-pointers -> go-http-server`.
These warnings don't interrupt the build or testing; they just indicate potential gaps in test coverage.

### 5.2 Operating environment and dependencies

Program testing requires language runtimes and package dependencies specified via `@TEST_SPEC` blocks.

The `lang=` field declares installation commands for the language/runtime environment.
Typically specified only in the first/foundational task of a taskgroup, 
since all tasks in the same taskgroup share the same language runtime.

Examples:

- `lang=apt-get install -y golang-go` → installs Go compiler in the OS's default version
- `lang=curl -fL https://golang.org/dl/go1.25.5.linux-amd64.tar.gz | tar -C /usr/local -xz` → installs Go 1.25.5
- `lang=apt-get install -y python3-pip` → installs Python 3 pip

The `lang=` field supports multi-line install commands (subsequent lines without `=` are appended).
If multiple tasks have same `lang=` declarations, only unique commands are installed (deduplication).

The `deps=` field specifies per-task package dependencies that differ from other tasks in the same taskgroup. Examples:

- `deps=pip install fastapi uvicorn` → install Python packages specific to this task
- `deps=go get github.com/lib/pq@v1.10.0` → install Go dependencies specific to this task

Tasks without a `deps=` field will use only the taskgroup's language runtime without additional dependencies.
The `deps=` field also supports multi-line commands (subsequent lines without `=` are appended).

**Note**: If `.prot` file already contains dependency installation commands in the `@PROT_SPEC` blocks 
(e.g., `pip install`, `npm install`), these commands will be executed automatically during CI runs. 
In such cases, you don't need to redundantly declare them in `lang=` or `deps=` fields in `@TEST_SPEC`.

For local testing, you need to manually install declared dependencies. 
For CI, use `sedrila maintainer collect-dependencies` to get the full list as JSON (stdout or `-o file`).

Installation and execution in CI:

All tests execute serially in a single container with all language runtimes and dependencies installed upfront.
Execution order respects task dependencies (`assumes` and `requires`) via topological sorting.
Each test runs in a temporary isolated directory with only required files; 
the directory is automatically cleaned up after testing (success or failure).


### 5.3 Automated vs. Manual vs. Skip

Test execution mode is determined by `@PROT_SPEC` block content:

**Automated**: When `@PROT_SPEC` includes `output_re` or `exitcode`, 
commands execute and output is validated against the specified rules.
Use for deterministic programs with stable or pattern-matchable output.

**Manual**: When `@PROT_SPEC` is present but contains only `manual=<reason>` 
(no `output_re`, no `exitcode`, no `skip=1`), the block is marked as requiring human verification.
Use for non-deterministic output, interactive programs, timing-dependent behavior, or environment-specific results.
The `manual=` field is required and documents why automated testing is not possible for that protocol block.

**Skip**: A block is skipped in two cases:
- No `@PROT_SPEC` block precedes the command at all (default behavior).
- `@PROT_SPEC` explicitly declares `skip=1`.

Skipped blocks are not counted as failures and do not appear in the manual review list.


## 5. Implementation notes

`check-links`: Link checking leverages the `author` build system infrastructure for file identification.
(When checking all files, the command creates a `Coursebuilder` instance to parse `sedrila.yaml`;
builds only the essential elements needed for file identification (`Sourcefile`: Registers all source files;
`Topmatter`: Parses YAML metadata from Markdown files; 
`MetadataDerivation`: Processes metadata and evaluates stage filtering);
extracts the list of Markdown files that need checking (respecting configuration and stages)
