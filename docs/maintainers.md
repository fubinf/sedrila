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
<!-- LINK_CHECK: status=403 -->
[Restricted Resource](https://example.com/restricted)

<!-- LINK_CHECK: content="Welcome" -->
[Must contain text](https://example.com/)

<!-- LINK_CHECK: status=302, timeout=30, ignore_cert=true -->
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

- Scans `.prot` files in `altdir` for `@PROGRAM_CHECK` blocks
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


### 5.1 Operating environment and dependencies

Program testing requires language runtimes and package dependencies specified via `@PROGRAM_CHECK` blocks.

**Base requirements:**

- **Python**: 3.11 or higher (required for sedrila itself)
- **itreedir**: Must exist as a directory with program source files

**Language runtimes:**

The `lang=` field in each `@PROGRAM_CHECK` block declares which language/runtime is required.
For example:

- `lang=Python 3.11` → requires Python 3.11 to be available on `PATH`
- `lang=Go 1.23` → requires Go 1.23 compiler
- `lang=Node.js 18` → requires Node.js 18

For local test, need to install required language runtimes in local environment.
For CI, We specify languages manually in the CI config because language setup there is static, 
can not be installed automatically. And installing runtimes via package commands is more complicated 
than using the CI’s built-in language configuration.

**Package dependencies:**

The `deps=` field (optional) specifies packages to install. Examples:

- `deps=pip install numpy requests>=2.0` → install via pip
- `deps=go get github.com/lib/pq@v1.10.0` → install via go get

For local testing, need to manually install declared dependencies. For CI, use `--collect`:

```bash
sedrila maintainer --collect > deps.json
# Outputs: {"dependencies": ["pip install numpy", ...], "languages": {"Python": "3.11", ...}}
```

CI workflows use `--collect` to extract dependencies, then install them before running tests.


### 5.2 Test types and behavior

The `typ=` field in `@PROGRAM_CHECK` determines how a program is tested.

**direct**: Automated output verification

Commands are executed automatically and output is compared:

- All declared commands must execute successfully
- Actual output must match expected output (with whitespace normalization)
- Test passes only if ALL commands match

Use `typ=direct` for deterministic programs with stable output.

**manual**: Manual verification required

Test execution is skipped; program marked "Manual Review Required" in report.
Requires `manual_reason=` field explaining why manual testing is needed.

Use `typ=manual` for:

- Non-deterministic output (timestamps, memory addresses)
- Interactive programs requiring user input
- Timing-dependent behavior
- Programs with environment-specific results

### 5.3 @PROGRAM_CHECK block format

`@PROGRAM_CHECK` blocks contain metadata for automated testing. They should appear
at the beginning of a `.prot` file for clarity, but can appear anywhere in the file.

**Placement and syntax:**

- Should be at `.prot` file start (recommended for clarity)
- Block starts with line containing only `@PROGRAM_CHECK`
- Block ends at first blank line
- Inside block: one `key=value` per line, no spaces around `=`
- `deps` field can span multiple lines (subsequent lines without `=` are appended as separate commands)
- No comments allowed inside @PROGRAM_CHECK block

Example:

```
@PROGRAM_CHECK
lang=Python 3.11
deps=pip install numpy
pip install requests>=2.0
typ=direct

$ python myscript.py
Hello World
```

**Required fields:**

`lang=<language and version>` - Language runtime and version.
Examples: `lang=Python 3.11`, `lang=Go 1.23`

`typ=<test type>` - One of: `direct`, `manual`

**Optional fields:**

`deps=<install command>` - Package installation command.
Examples: `deps=pip install numpy requests`, `deps=go get github.com/lib/pq`

`manual_reason=<text>` - Required when `typ=manual`. Explains why manual testing is needed.
Example: `manual_reason=Output contains timestamps`

`files=<list>` - Comma-separated list of additional files used by the program (short names only, e.g., `helper.py`).
Create a corresponding `.files` file in the chapter directory (e.g., `ch/Sprachen/Go/task.files`) with one file path per line.
Programchecker automatically substitutes file names in test commands with their absolute paths.


### 5.4 Multi-command testing and cleanup

The program checker processes all testable commands from each `.prot` file:

- Each command (`$` line) and its expected output are extracted as a single test
- Commands are executed sequentially in the program's working directory
- Output is compared; test passes only if ALL commands match
- Detailed test reports show pass/fail status for each command

Before and after testing, generated files are automatically cleaned up to ensure a fresh environment:
- Database files (`.db`, `.sqlite`, `.sqlite3`)
- Log files (`.log`, `.shortlog`)
- Python cache directories (`__pycache__`, `*.pyc`)

This prevents test failures from residual files and ensures reproducible results across runs.
