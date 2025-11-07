#!/usr/bin/env python3

from __future__ import annotations

import json
import os
import sys
from fnmatch import fnmatch
from typing import Dict, Iterable, List, Optional, Tuple
from urllib.error import HTTPError, URLError
from urllib.request import Request, urlopen


def debug(message: str) -> None:
    if os.environ.get("DEBUG_ACTION"):
        print(f"[debug] {message}", file=sys.stderr)


def err(message: str) -> None:
    print(message, file=sys.stderr)


def require_env(name: str) -> str:
    value = os.environ.get(name)
    if not value:
        err(f"Missing required env: {name}")
        sys.exit(1)
    return value


def normalize_pattern(pattern: str) -> str:
    return pattern.replace("**", "*")


def parse_ignored(raw: str) -> List[str]:
    patterns: List[str] = []
    for line in raw.splitlines():
        stripped = line.strip()
        if not stripped or stripped.startswith("#"):
            continue
        patterns.append(normalize_pattern(stripped))
    return patterns


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


if __name__ == "__main__":
    main()


