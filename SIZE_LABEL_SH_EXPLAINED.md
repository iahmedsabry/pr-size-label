# size-label.sh — Line-by-line explanation and reasoning

This document explains `size-label.sh` line-by-line with the reasoning behind each line and the overall logic. It's intended as a learning aid to understand how the script works and why it's written the way it is.

File purpose in one sentence
- Compute the total changed lines in a GitHub Pull Request and add a `size/*` label (e.g., `size/S`, `size/M`) based on configurable thresholds.

Prerequisites
- bash (POSIX-like shell)
- curl (HTTP requests)
- jq (JSON parsing in shell)

Why this script exists
- GitHub Actions can run small scripts to automate repository tasks. This script labels PRs by size to help reviewers and CI systems prioritize work.

---

Below, each original script line (or small related block) is shown followed by an explanation and the reason it exists.

Note: lines that are pure comments in the original script are often grouped with the related code block.

---

#!/usr/bin/env bash

Explanation:
- This is the shebang. It tells the OS to run this file using the `bash` interpreter by locating it via `env`.
- Reasoning: Using `env` makes the script more portable across systems where bash might be in different locations (for example `/usr/bin/bash` vs `/bin/bash`).

set -euo pipefail

Explanation (this is actually three flags combined):
- `set -e`: Exit immediately if any command returns a non-zero status (abort on first error).
- `set -u`: Treat unset variables as an error and exit (helps catch typos and missing env vars).
- `set -o pipefail`: If a pipeline fails (any command in pipeline fails), the pipeline's exit status is the failure, not the last command’s status.

Reasoning:
- These are defensive flags to make the script fail fast and avoid subtle bugs or silent failures. They make debugging and correctness easier.

# Compute PR change size and add a size/* label accordingly.
# Requirements: bash, curl, jq
# Env:
#   - GITHUB_TOKEN (required)
#   - GITHUB_EVENT_PATH (required)
#   - INPUT_SIZES (optional JSON map: {"0":"XS","20":"S",...})
#   - IGNORED (optional newline-separated globs; lines starting with '!' are inclusions)
#   - GITHUB_API_URL (optional; defaults to https://api.github.com)
#   - DEBUG_ACTION (optional: enable debug logs)

Explanation:
- These comments document the script's purpose and environment variables. Helpful for users and other developers.
- Reasoning: Good scripts document required dependencies and configuration; this is especially important for CI scripts.

debug() { [[ -n "${DEBUG_ACTION:-}" ]] && echo "[debug] $*" >&2 || true; }

Explanation:
- Defines a helper function `debug` that prints debug messages to STDERR if `DEBUG_ACTION` environment variable is non-empty.
- `${DEBUG_ACTION:-}` expands to the value of `DEBUG_ACTION` or empty if unset.
- `[[ -n ... ]]` checks if non-empty.
- `echo "[debug] $*" >&2` writes the message to standard error.
- `|| true` ensures the function doesn't cause an error if debug prints are disabled.

Reasoning:
- Centralizes debug printing so the script can be more verbose during troubleshooting without changing the code.

err() { echo "$*" >&2; }

Explanation:
- Defines `err` to print messages to STDERR. Used for error messages.

Reasoning:
- Keeps error printing consistent and explicit (to STDERR).

require_env() { local n="$1"; [[ -n "${!n:-}" ]] || { err "Missing required env: $n"; exit 1; }; }

Explanation:
- A function that checks whether an environment variable (named by the first argument) is set and non-empty.
- `${!n}` is indirect expansion (value of variable whose name is in `n`).
- If the variable is empty/unset, prints an error and exits with code 1.

Reasoning:
- Validates essential inputs early and provides a clear error message instead of letting the script fail later with a cryptic error.

require_env GITHUB_TOKEN
require_env GITHUB_EVENT_PATH

Explanation:
- Enforces the presence of `GITHUB_TOKEN` and `GITHUB_EVENT_PATH`.
- `GITHUB_TOKEN` is required to call the GitHub API (to add labels).
- `GITHUB_EVENT_PATH` points to the JSON file GitHub Actions provides describing the event (the PR details).

Reasoning:
- These are essential for the script to function; checking them up-front avoids running unnecessary work.

API_BASE="${GITHUB_API_URL:-https://api.github.com}"

Explanation:
- Sets `API_BASE` to `GITHUB_API_URL` if provided; otherwise default to `https://api.github.com`.
- Uses parameter expansion with default value `${var:-default}`.

Reasoning:
- Allows running against GitHub Enterprise or a different API endpoint if needed.

event_json="$(cat "$GITHUB_EVENT_PATH")"

Explanation:
- Reads the event JSON file into a shell variable `event_json`.
- `$(cat ...)` captures the file's content in a string.

Reasoning:
- The script needs to parse this JSON to determine PR number, repo, owner, and action. Keeping the JSON content in a variable avoids repeated file reads.

# Validate event type
action="$(jq -r '.action // empty' <<<"$event_json")"
if [[ "$action" != "opened" && "$action" != "synchronize" && "$action" != "reopened" ]]; then
  echo "Action will be ignored: ${action:-null}"
  exit 0
fi

Explanation:
- Uses `jq` to extract `.action` from the event JSON. If `.action` is null/absent, returns an empty string due to `// empty`.
- Only proceeds for the actions: `opened`, `synchronize`, or `reopened`.
- Otherwise, prints that the action will be ignored and exits successfully (exit 0).

Reasoning:
- The script is designed to run on PR events where sizing makes sense. Many other events exist; ignoring them avoids unnecessary API calls and changes.

owner="$(jq -r '.pull_request.base.repo.owner.login' <<<"$event_json")"
repo="$(jq -r '.pull_request.base.repo.name' <<<"$event_json")"
pr_number="$(jq -r '.pull_request.number' <<<"$event_json")"
[[ -n "$owner" && -n "$repo" && -n "$pr_number" && "$owner" != null && "$repo" != null && "$pr_number" != null ]] || {
  err "Invalid pull_request context in GITHUB_EVENT_PATH"; exit 1; }

Explanation:
- Extracts the repository owner login, repo name, and pull request number from the event JSON using `jq -r` (raw string output).
- The conditional checks all three are non-empty and not the literal `null` string, otherwise exits with an error.

Reasoning:
- These values are needed to fetch PR files and later post labels. The check guards against unexpected event shapes.

# Sizes config
if [[ -n "${INPUT_SIZES:-}" ]]; then
  sizes_json="$INPUT_SIZES"
else
  sizes_json='{"0":"XS","10":"S","30":"M","100":"L","500":"XL","1000":"XXL"}'
fi
debug "Sizes: $sizes_json"

Explanation:
- If `INPUT_SIZES` is provided (a JSON map), use it. Otherwise use a default size threshold mapping.
- `debug` prints the chosen sizes mapping when debugging is enabled.

Reasoning:
- Allows customization of size thresholds via environment variable while providing sensible defaults.

# IGNORED handling (basic globbing; treats ** as *)
normalize_pattern() { local p="$1"; echo "${p//\*\*/\*}"; }

Explanation:
- Defines `normalize_pattern` that replaces `**` with `*` in a glob pattern.
- The `${var//find/replace}` syntax replaces all occurrences.

Reasoning:
- Simplifies pattern handling by normalizing patterns; the script uses bash glob matching which doesn't support `**` exactly the same as some other tools.

is_ignored_path() {
  local path="$1"
  [[ -z "$path" || "$path" == "/dev/null" ]] && return 0
  local ignore=false
  if [[ -n "${IGNORED:-}" ]]; then
    while IFS= read -r line; do
      [[ -z "$line" || "$line" == \#* ]] && continue
      if [[ "$line" == !* ]]; then
        local patt; patt="$(normalize_pattern "${line:1}")"
        [[ "$path" == $patt ]] && return 1
      else
        local patt; patt="$(normalize_pattern "$line")"
        if [[ "$ignore" == false && "$path" == $patt ]]; then
          ignore=true
        fi
      fi
    done <<<"$IGNORED"
  fi
  [[ "$ignore" == true ]]
}

Explanation (long function — explained step by step):
- `is_ignored_path` determines whether a file path should be ignored based on the `IGNORED` variable.
- If `path` is empty or `/dev/null`, returns 0 (true, considered ignored). This handles deleted files or missing values.
- If `IGNORED` is set, loop over each line of `IGNORED`.
  - Skip empty lines or comment lines (starting with `#`).
  - If a line starts with `!`, this is treated as an inclusion (negation of ignore) — normalize the pattern and if it matches the `path`, return 1 (meaning "not ignored").
  - Otherwise treat it as an ignore pattern; if it matches, set a flag `ignore=true`.
- At the end, return true if `ignore` is true; otherwise false.

Reasoning:
- The script supports a simple ignore list with `!` to re-include specific patterns (common in gitignore semantics). This reduces noise by excluding files that should not affect size labeling (e.g., docs/*.md).

# Sum changed lines from PR files
changed_lines=0
per_page=100
page=1
while :; do
  url="${API_BASE}/repos/${owner}/${repo}/pulls/${pr_number}/files?per_page=${per_page}&page=${page}"
  resp="$(curl -sfSL -H "Authorization: Bearer ${GITHUB_TOKEN}" -H "Accept: application/vnd.github.raw+json" "$url")" || {
    err "Failed to fetch PR files (page $page)"; exit 1; }
  count_page="$(jq 'length' <<<"$resp")"
  [[ "$count_page" -eq 0 ]] && break
  while IFS= read -r row; do
    filename="$(jq -r '.filename' <<<"$row")"
    prev_filename="$(jq -r '.previous_filename // empty' <<<"$row")"
    changes="$(jq -r '.changes' <<<"$row")"
    if is_ignored_path "$prev_filename" && is_ignored_path "$filename"; then
      continue
    fi
    [[ "$changes" =~ ^[0-9]+$ ]] && changed_lines=$((changed_lines + changes)) || true
  done < <(jq -c '.[]' <<<"$resp")
  [[ "$count_page" -lt "$per_page" ]] && break
  page=$((page + 1))
done

Explanation (this block is the main logic that sums changed lines):
- `changed_lines=0`: initialize accumulator.
- `per_page=100` and `page=1`: prepare pagination parameters to fetch files from GitHub's API.
- `while :; do` is an infinite loop that breaks when pages are exhausted.
- `url=...`: constructs the API URL to list PR files with pagination.
- `curl -sfSL`:
  - `-s` silent mode (no progress),
  - `-f` fail silently on HTTP errors (non-2xx causes non-zero exit),
  - `-S` show error message with `-s` if it fails,
  - `-L` follow redirects.
  - Authorization header includes the `GITHUB_TOKEN`.
  - Accept header requests raw JSON via `application/vnd.github.raw+json`.
- If curl fails, print an error and exit (due to `||` control flow).
- `count_page` gets number of files returned on this page using `jq 'length'`.
- If there are zero files, break the loop.
- The inner `while IFS= read -r row; do ... done < <(jq -c '.[]' <<<"$resp")` iterates over each file object in the JSON array (compact JSON objects per line).
  - Extract `filename`, `previous_filename` (if present), and `changes`.
  - If both the previous filename and current filename are ignored (i.e., `is_ignored_path` returns true for both), skip counting that file.
  - If `changes` is numeric, add it to `changed_lines`.
- If the number of items returned is less than `per_page`, we are on the last page and break.
- Otherwise, increment `page` and fetch the next page.

Reasoning:
- GitHub PR file listings can be paginated; this code handles that.
- It sums the `changes` value for each file which is the number of changed lines in that file.
- It respects ignore patterns to exclude files that shouldn't affect size labeling.
- Using `jq -c '.[]'` and `read` avoids storing a huge JSON blob in memory per entry and is robust in shell scripting.

echo "Changed lines: $changed_lines"

Explanation:
- Prints the computed total changed lines to the log/console.

Reasoning:
- Useful for debugging and visibility in CI logs.

# Compute size label
size_label=""
mapfile -t thresholds < <(jq -r 'keys[]' <<<"$sizes_json" | sort -n)
for t in "${thresholds[@]}"; do
  if [[ "$changed_lines" -ge "$t" ]]; then
    value="$(jq -r --arg t "$t" '.[$t]' <<<"$sizes_json")"
    size_label="size/${value}"
  fi
done

Explanation:
- `size_label` starts empty.
- `mapfile -t thresholds < <(...)` reads the keys from `sizes_json` (the thresholds) and sorts them numerically into the bash array `thresholds`.
- Loop over thresholds: for each threshold `t` (e.g., "0", "10", "30"), check if `changed_lines` >= threshold.
- If yes, retrieve the mapped size string via `jq` and set `size_label="size/${value}"`.
- Because we iterate thresholds in increasing order and always overwrite `size_label` when condition matches, the final value will correspond to the highest threshold that is <= `changed_lines`.

Reasoning:
- This is a simple threshold-based mapping: find the largest threshold less than or equal to changed lines and use its label.
- Sorting ensures thresholds are considered in numeric ascending order.

echo "Matching label: $size_label"
[[ -n "$size_label" ]] || { err "No size label computed"; exit 1; }

Explanation:
- Print the chosen label.
- If no label was computed (shouldn't happen because `0` threshold normally exists), error out.

Reasoning:
- Defensive check to avoid posting an empty label to the GitHub API.

# Add label
payload="$(jq -n --arg l "$size_label" '{labels: [$l]}')"
curl -sfSL -X POST \
  -H "Authorization: Bearer ${GITHUB_TOKEN}" \
  -H "Content-Type: application/json" \
  "${API_BASE}/repos/${owner}/${repo}/issues/${pr_number}/labels" \
  -d "$payload" >/dev/null

echo "Added label: ${size_label}"

Explanation:
- Build a JSON payload like `{ "labels": ["size/M"] }` using `jq -n` (constructs JSON in shell safely).
- POST the payload to the issues labels endpoint for the repository and PR number. On GitHub, adding labels to issues and PRs uses the issues API.
- `>/dev/null` discards the HTTP response body — script prints only the success message below.
- Finally, prints a confirmation message.

Reasoning:
- Uses authenticated request to add the label. `jq` is used to safely produce JSON rather than trying to write raw strings (avoids quoting issues).

---

High-level logic summary
- Validate required environment variables.
- Read the GitHub event payload.
- If the event action is a PR open/update/reopen, extract owner/repo/number.
- Determine thresholds from `INPUT_SIZES` or defaults.
- Fetch all PR files via the GitHub API (paginated).
- Sum the `changes` field across files, ignoring files matched by `IGNORED` rules.
- Determine which size bucket the total changed lines falls into.
- Post the corresponding `size/*` label to the PR (via the issues API).

Practical tips and notes for learning
- Defensive bash flags (`set -euo pipefail`) are essential for reliable scripts.
- Use helper functions (`debug`, `err`, `require_env`) to keep the script DRY and readable.
- Prefer `jq` for JSON handling in shell scripts — it's much safer and clearer than string manipulations.
- Use `curl -f` (fail on HTTP error) and explicit error messages to make failures actionable in CI logs.
- When working with pagination, keep `per_page` reasonable (100 is GitHub's max) and loop until fewer items are returned.
- Avoid blindly trusting input shapes—validate or fail fast with informative messages.

Edge cases and suggested improvements
- The ignore matching uses simple bash globbing; it may not behave exactly like gitignore. Consider integrating a library or stricter matching if needed.
- The script uses `curl` and `jq`. The repo also contains a Python port (`size_label.py`) which avoids the need for `jq` and can be easier to maintain in complex logic.
- The script discards the response from the label POST. For debugging, consider not discarding the body or logging HTTP status codes.
- If `INPUT_SIZES` contains non-numeric keys, `jq -r 'keys[]' | sort -n` could produce unexpected results; adding validation would help.
- For large PRs with many files, this approach counts the `changes` field supplied by GitHub which is the number of changed lines per file; if you need different logic (e.g., to exclude whitespace-only changes), you’d have to fetch diffs or compute differently.

Quick example workflow (GitHub Actions)
- Set up a workflow that triggers on `pull_request_target` and runs this script with `GITHUB_TOKEN` and optional `INPUT_SIZES` and `IGNORED` environment variables.

Local testing tip
- To test locally, create a minimal `event.json` that mimics GitHub's PR event shape and point `GITHUB_EVENT_PATH` to it. Use a token that has repository access (be careful with secrets!).

Closing notes
- This script is a compact and pragmatic shell-based automation useful for labeling PRs by size. For learning, porting pieces into a higher-level language (Python/Node.js) can be a good exercise to understand when shell is appropriate vs when richer tooling is preferable.

If you want, I can:
- Create an `event.example.json` to test locally,
- Add an alternative `README` snippet showing how to run the shell script directly,
- Or produce a line-by-line annotated version where each original line is repeated verbatim followed by the explanation (even more literal mapping).

Tell me which of these extras you'd like and I'll add them next.
