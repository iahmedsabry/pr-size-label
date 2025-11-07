# size_label.py — Line-by-line explanation and reasoning

This file explains `size_label.py` line-by-line with the reasoning behind each line and the overall logic. It's intended as a learning resource for anyone who wants to understand how the script works and why it was written the way it is.

File purpose in one sentence
- Compute the total changed lines in a GitHub Pull Request and add a `size/*` label (for example, `size/S`, `size/M`) according to configurable thresholds.

Prerequisites
- Python 3.6+ (3.8+ recommended)
- No external packages required — the script uses only the standard library.

For each code section below, I show the original code (or block) followed by an explanation and reasoning for why the code is written that way.

---

#!/usr/bin/env python3

Explanation:
- Shebang tells POSIX-like systems which interpreter to use when running the script directly.
- The module-level docstring briefly states the script's purpose.

Reasoning:
- Using `env` makes locating `python3` portable across systems. The docstring helps quick discovery and auto-generated docs.

from __future__ import annotations

import json
import os
import sys
from fnmatch import fnmatch
from typing import Dict, Iterable, List, Optional, Tuple
from urllib.error import HTTPError, URLError
from urllib.request import Request, urlopen

Explanation:
- `__future__ import annotations` defers evaluation of annotations into strings (PEP 563), making forward references and type hints lighter at runtime.
- Standard library imports used in the script:
  - `json` for (de)serializing JSON.
  - `os`, `sys` for env and I/O operations.
  - `fnmatch.fnmatch` for glob-style pattern matching (used for IGNORED patterns).
  - `typing` for type annotations improving readability and helping static tools.
  - `urllib.request` and `urllib.error` for making HTTP requests to GitHub without external deps.

Reasoning:
- Avoids third-party dependencies (like `requests`) to make the action lightweight and portable in CI.


def debug(message: str) -> None:
    if os.environ.get("DEBUG_ACTION"):
        print(f"[debug] {message}", file=sys.stderr)

Explanation:
- `debug` writes messages to STDERR if the `DEBUG_ACTION` environment variable is set.

Reasoning:
- Keeps debug logs separate from normal output. Using env toggles verbosity without code changes.


def err(message: str) -> None:
    print(message, file=sys.stderr)

Explanation:
- `err` is a convenience wrapper to print error messages to STDERR.

Reasoning:
- Centralizes error printing, making it easier to change behavior (for example to log to a file) later.


def require_env(name: str) -> str:
    value = os.environ.get(name)
    if not value:
        err(f"Missing required env: {name}")
        sys.exit(1)
    return value

Explanation:
- Reads an environment variable and exits with an error if it's missing or empty.

Reasoning:
- Fail-fast validation of required inputs avoids later obscure failures.


def normalize_pattern(pattern: str) -> str:
    return pattern.replace("**", "*")

Explanation:
- Normalizes double-star `**` to single `*` because `fnmatch` doesn't treat `**` specially.

Reasoning:
- Keeps behavior simple and predictable when translating ignore patterns to `fnmatch`.


def parse_ignored(raw: str) -> List[str]:
    patterns: List[str] = []
    for line in raw.splitlines():
        stripped = line.strip()
        if not stripped or stripped.startswith("#"):
            continue
        patterns.append(normalize_pattern(stripped))
    return patterns

Explanation:
- Converts the `IGNORED` multi-line string into a list of normalized patterns, skipping empty lines and comments.

Reasoning:
- Mirrors how `.gitignore`-style files are commonly written: comments and blank lines are ignored.


def should_ignore(path: Optional[str], patterns: Iterable[str]) -> bool:
    if not path or path == "/dev/null":
        return True

    ignore = False
    for pattern in patterns:
        if pattern.startswith("!"):
            if fnmatch(path, pattern[1:]):
                return False
        else:
            if not ignore and fnmatch(path, pattern):
                ignore = True
    return ignore

Explanation:
- `should_ignore` determines if a given path should be ignored based on the provided patterns.
- Special-case: if `path` is falsy or `/dev/null`, treat as ignored (useful for deleted files or absent previous filename).
- Patterns starting with `!` are inclusions (negate an ignore); if matched return False (do not ignore).
- Otherwise, if any non-negated pattern matches set `ignore=True` and continue; final return is `ignore`.

Reasoning:
- Simple include/exclude logic consistent with common ignore-file semantics.
- Using `fnmatch` provides simple glob matching without adding a new dependency.


def github_request(url: str, token: str, *, method: str = "GET", payload: Optional[Dict] = None) -> str:
    headers = {
        "Authorization": f"Bearer {token}",
        "Accept": "application/vnd.github.raw+json",
    }
    data_bytes = None
    if payload is not None:
        headers["Content-Type"] = "application/json"
        data_bytes = json.dumps(payload).encode("utf-8")

    request = Request(url, data=data_bytes, headers=headers, method=method)
    try:
        with urlopen(request) as response:
            return response.read().decode("utf-8")
    except HTTPError as exc:
        err(f"GitHub API request failed ({exc.code}): {exc.reason}")
        body = exc.read().decode("utf-8", errors="replace") if exc.fp else ""
        if body:
            debug(f"Response body: {body}")
        sys.exit(1)
    except URLError as exc:
        err(f"GitHub API request failed: {exc.reason}")
        sys.exit(1)

Explanation (long):
- Builds and sends an HTTP request using `urllib.request.Request` and `urlopen`.
- Adds Authorization header with the `GITHUB_TOKEN` and requests a raw JSON media type.
- If `payload` is provided, sets `Content-Type: application/json` and serializes the payload as bytes.
- Returns the response body as a decoded string on success.
- On `HTTPError` (e.g., non-2xx response), log a useful message including status code and reason, optionally log the response body when debugging, then exit.
- On `URLError` (e.g., network issues), log and exit.

Reasoning:
- Using the standard library keeps the script lightweight and avoids extra installation steps in CI environments.
- Explicit error handling provides clearer failure diagnostics than letting exceptions bubble.
- The function centralizes GitHub request behavior, making retries and additional headers easier to add later.


def load_sizes_config(raw: Optional[str]) -> Dict[str, str]:
    if raw:
        try:
            config = json.loads(raw)
        except json.JSONDecodeError as exc:
            err(f"Invalid INPUT_SIZES JSON: {exc}")
            sys.exit(1)
        if not isinstance(config, dict):
            err("INPUT_SIZES must be a JSON object")
            sys.exit(1)
        return {str(k): str(v) for k, v in config.items()}
    return {"0": "XS", "10": "S", "30": "M", "100": "L", "500": "XL", "1000": "XXL"}

Explanation:
- Loads `INPUT_SIZES` (if provided) and validates it's a JSON object mapping thresholds to labels.
- Coerces keys and values to strings to keep later processing predictable.
- If not provided, returns the default mapping.

Reasoning:
- Validating input early prevents subtle errors later when keys aren't valid integers or the JSON is malformed.
- Returning a mapping of strings keeps the representation predictable and easy to handle later in the code.


def compute_label(changed: int, sizes: Dict[str, str]) -> Optional[str]:
    thresholds: List[Tuple[int, str]] = []
    for key, value in sizes.items():
        try:
            thresholds.append((int(key), value))
        except ValueError:
            debug(f"Skipping non-integer size threshold: {key}")
    thresholds.sort()

    label = None
    for threshold, size in thresholds:
        if changed >= threshold:
            label = f"size/{size}"
    return label

Explanation:
- Converts configured size keys to integers (skipping any non-integer keys with a debug message).
- Sorts thresholds numerically.
- Iterates through sorted thresholds in ascending order and sets `label` to the last threshold that is <= `changed` (so highest matching threshold).
- Returns the label, or `None` if none matched.

Reasoning:
- Robustly handles bad config by skipping non-integer keys rather than crashing.
- Sorting ensures the largest matched threshold is used.


def main() -> None:
    token = require_env("GITHUB_TOKEN")
    event_path = require_env("GITHUB_EVENT_PATH")

    api_base = os.environ.get("GITHUB_API_URL", "https://api.github.com")
    debug(f"API base: {api_base}")

    try:
        with open(event_path, "r", encoding="utf-8") as fh:
            event = json.load(fh)
    except FileNotFoundError:
        err("GITHUB_EVENT_PATH does not exist")
        sys.exit(1)
    except json.JSONDecodeError as exc:
        err(f"Invalid JSON in GITHUB_EVENT_PATH: {exc}")
        sys.exit(1)

    action = event.get("action")
    if action not in {"opened", "synchronize", "reopened"}:
        print(f"Action will be ignored: {action or 'null'}")
        return

    pr = event.get("pull_request", {})
    owner = pr.get("base", {}).get("repo", {}).get("owner", {}).get("login")
    repo = pr.get("base", {}).get("repo", {}).get("name")
    number = pr.get("number")
    if not all([owner, repo, number]):
        err("Invalid pull_request context in GITHUB_EVENT_PATH")
        sys.exit(1)

Explanation (first part of main):
- Validates `GITHUB_TOKEN` and `GITHUB_EVENT_PATH` and reads the event JSON into a Python object.
- Handles file-not-found and invalid JSON errors explicitly.
- Checks the action to only proceed for the expected PR lifecycle events.
- Extracts `owner`, `repo`, and `number` from the `pull_request` object in a defensive manner.
- Validates these required values exist.

Reasoning:
- Performs early validation with structured error handling and clear messages.
- Using Python's dict `get` chain keeps code robust against missing fields.


    ignored_patterns = parse_ignored(os.environ.get("IGNORED", ""))
    if ignored_patterns:
        debug(f"Ignored patterns: {ignored_patterns}")

    sizes = load_sizes_config(os.environ.get("INPUT_SIZES"))
    debug(f"Sizes: {json.dumps(sizes, sort_keys=True)}")

    changed_lines = 0
    per_page = 100
    page = 1

    while True:
        url = f"{api_base}/repos/{owner}/{repo}/pulls/{number}/files?per_page={per_page}&page={page}"
        debug(f"Fetching PR files from {url}")
        response_text = github_request(url, token)
        try:
            files = json.loads(response_text)
        except json.JSONDecodeError as exc:
            err(f"Failed to parse PR files response: {exc}")
            sys.exit(1)

        if not files:
            break

        for item in files:
            filename = item.get("filename")
            previous_filename = item.get("previous_filename")
            if should_ignore(previous_filename, ignored_patterns) and should_ignore(filename, ignored_patterns):
                continue

            changes = item.get("changes")
            if isinstance(changes, int):
                changed_lines += changes
            else:
                debug(f"Skipping file with non-integer change count: {filename}")

        if len(files) < per_page:
            break
        page += 1

Explanation (main loop):
- Parses `IGNORED` and `INPUT_SIZES` from environment and prints debug info when requested.
- Uses pagination to iterate over all PR files via the GitHub API.
- For each file entry:
    - Extracts `filename` and `previous_filename`.
    - Skips the file if both the previous and current filename match ignore patterns.
    - Adds the `changes` count (if integer) to `changed_lines`.
- Breaks out of pagination loop when the returned page has fewer items than `per_page`.

Reasoning:
- Implements clean, structured pagination and summing logic.
- `json.loads` is used to parse API responses. The code defends against malformed responses.


    print(f"Changed lines: {changed_lines}")

    label = compute_label(changed_lines, sizes)
    print(f"Matching label: {label or ''}")
    if not label:
        err("No size label computed")
        sys.exit(1)

    payload = {"labels": [label]}
    post_url = f"{api_base}/repos/{owner}/{repo}/issues/{number}/labels"
    github_request(post_url, token, method="POST", payload=payload)
    print(f"Added label: {label}")

Explanation (final part of main):
- Logs the computed changed lines and the matching label.
- If there is no matching label (should be rare if `0` threshold exists), the script exits with an error.
- Constructs a JSON payload and posts it to the issues labels endpoint to add the label to the PR.

Reasoning:
- Uses clear Python data structures for payload construction and posting.


if __name__ == "__main__":
    main()

Explanation:
- Standard Python entry point. Runs `main()` when the script is executed as a program.

---

High-level logic summary
- Validate required environment variables and read the GitHub event JSON.
- Ensure the event action is relevant to PR sizing.
- Build ignored patterns list and size thresholds mapping.
- Fetch the list of files changed in the PR (paginated) and sum the `changes` count for each non-ignored file.
- Compute the appropriate `size/*` label based on thresholds.
- Post the label to GitHub using the issues API.

Why the Python approach is beneficial
- Better error handling: exceptions and structured try/except blocks produce clearer messages and stack traces compared to shell pipelines.
- Easier to test and maintain: functions can be unit-tested (e.g., `compute_label`, `parse_ignored`).
- No need for external tools like `jq` or `curl` (though the standard library HTTP API is slightly more verbose than `requests`).
- More portable on systems where `jq` might not be available.

Edge cases and suggested improvements
- `fnmatch` matching is simple and may not match gitignore semantics (for example, directory recursion). If you need full gitignore compatibility, consider using `pathspec` or implementing gitignore parsing.
- `github_request` currently exits on HTTP errors. Consider adding retry/backoff logic for transient 5xx errors or network hiccups.
- Logging: consider using the `logging` module for structured logs instead of `print` — this allows different verbosity levels and easier integration with log collectors.
- Tests: add unit tests for `compute_label`, `parse_ignored`, and `should_ignore`.
- Security: be careful when logging environment variables like `GITHUB_TOKEN` — avoid printing secrets.

Local testing tips
- Create an `event.example.json` file that mimics the shape of GitHub's PR event (including `pull_request.base.repo.owner.login`, `pull_request.base.repo.name`, and `pull_request.number`).
- Run locally by exporting the environment variables, for example on Windows PowerShell:

```powershell
$env:GITHUB_TOKEN = 'ghp_...'
$env:GITHUB_EVENT_PATH = 'C:\path\to\event.example.json'
python .\size_label.py
```

On Unix/macOS:

```bash
export GITHUB_TOKEN='ghp_...'
export GITHUB_EVENT_PATH=./event.example.json
python3 size_label.py
```

Next steps (optional)
- I can add `event.example.json` to the repo to make local testing easier.
- I can add a few unit tests (using `unittest` or `pytest`) for the helper functions.
- I can add retry logic or a small wrapper that uses `requests` with retries for simpler HTTP code (would add a dependency).

If you'd like, I will now create `event.example.json` and a small test file for `compute_label`. Just tell me which of those you'd prefer and I'll add them next.
