# `sedrila maintainer` - Course Maintenance

The `sedrila maintainer` subcommand provides lightweight tools for maintaining course quality
without building the course. It operates directly on source files for faster execution.

## Usage

Basic command structure:

```bash
sedrila maintainer [options]
```

Unlike `sedrila author`, the maintainer does not:
- Build HTML files
- Process templates or macros
- Generate student/instructor websites
- Create cache files

Instead, it performs quality checks directly on source markdown and protocol files.

## Options

Common options:
- `--config <configfile>`: Specify configuration file (default: `sedrila.yaml`)
- `--log <level>`: Set logging level (DEBUG, INFO, WARNING, ERROR, CRITICAL)

### Link Checking

- Option `--check-links [markdown_file]` validates external HTTP/HTTPS links found in markdown files.
  Without an argument, it checks all course files. With a file argument, it checks only that specific file.
  Uses HEAD requests by default for efficiency, falling back to GET only when content validation is needed.
  Generates fixed-name reports: `link_check_report.json` and `link_check_report.md` in the current directory.
  Supports custom validation rules via HTML comments in markdown files (see examples below).
  Avoids checking duplicate URLs and includes comprehensive statistics in the main report.
  Examples: 
  - `sedrila maintainer --check-links` (check all course files)
  - `sedrila maintainer --check-links ch/Chapter1/Task1.md` (check specific file)

#### Link validation rules

By default, links are considered successful if they return 2xx or 3xx status codes.
You can specify custom validation rules using HTML comments before links:

```markdown
<!-- LINK_CHECK: status=403 -->
[Restricted Resource](https://example.com/restricted)

<!-- LINK_CHECK: content="Welcome" -->
[Must contain text](https://example.com/)

<!-- LINK_CHECK: status=302, timeout=30, ignore_ssl=true -->
[Complex validation](https://redirect.example.com)
```

Available rule parameters:
- `status=N`: Expect specific HTTP status code (e.g., `status=404` for intentionally broken links)
- `content="text"`: Verify page contains specific text (triggers GET request instead of HEAD)
- `timeout=N`: Use custom timeout in seconds
- `ignore_ssl=true`: Skip SSL certificate validation

The validation rule applies to the next link found and is then reset.

**Important:** There is no central whitelist for trusted domains. If a link is expected to return
non-2xx/3xx status codes (e.g., 403), you must explicitly declare this with a `LINK_CHECK` comment.
The checker will still make the request to verify the actual status code.

