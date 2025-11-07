# size_label.py — GitHub Action conversion and explanation

This document explains how `size_label.py` was converted into a reusable GitHub Action, what files were added, and a detailed, step-by-step breakdown of the action metadata and the example workflow. It's intended for learning and to let you modify or extend the action.

Files added
- `.github/actions/size-label/action.yml` — composite action that runs `size_label.py`.
- `.github/workflows/size-label.yml` — example workflow that calls the action on `pull_request_target`.

Goal
- Package the existing `size_label.py` script so it can be invoked as a reusable action from workflows, while keeping the script itself unchanged. Use a composite action to avoid adding new runtime packaging (no Docker or JS bundling required).

Why a composite action?
- Composite actions allow you to define a small, reusable action that runs several steps (checkout, setup Python, run script) without creating a Docker container or JavaScript action. They're simple to author and keep everything in the repository.

Detailed breakdown: `.github/actions/size-label/action.yml`

Contents (annotated)

name: "Size Label (Python)"
description: "Run the repository's `size_label.py` script to compute PR size and add a size/* label."
author: "Automated conversion"

inputs:
  input_sizes:
    description: 'JSON mapping of thresholds to labels (example: {"0":"XS","20":"S","50":"M"}).'
    required: false
  ignored:
    description: 'Newline-separated glob patterns to ignore (use leading "!" to re-include).'
    required: false
  debug_action:
    description: 'Set to "true" to enable debug logging.'
    required: false
  github_api_url:
    description: 'Optional GitHub API base URL (for GHES).'
    required: false

runs:
  using: "composite"
  steps:
    - name: Checkout repository
      uses: actions/checkout@v4

Explanation of the inputs section
- `input_sizes`: forwards the `INPUT_SIZES` environment variable to the script; use this to override the default thresholds.
- `ignored`: forwards the `IGNORED` env var (multi-line string) for globs to ignore.
- `debug_action`: if set to a truthy string, the script prints debug logs.
- `github_api_url`: optional base URL for GitHub Enterprise Server.

    - name: Set up Python
      uses: actions/setup-python@v4
      with:
        python-version: '3.x'

Explanation:
- Ensures a Python 3 runtime is available on the runner. This keeps the action portable across runners and avoids assuming `python3` is present.

    - name: Ensure script is executable
      shell: bash
      run: |
        # Make script executable if possible, but don't fail on platforms that don't support chmod
        chmod +x ./size_label.py || true

Explanation:
- Makes the script executable on UNIX-like runners. The `|| true` prevents failures on systems where `chmod` might not be supported.

    - name: Run size_label.py
      shell: bash
      env:
        GITHUB_TOKEN: ${{ secrets.GITHUB_TOKEN }}
        GITHUB_EVENT_PATH: ${{ github.event_path }}
        INPUT_SIZES: ${{ inputs.input_sizes }}
        IGNORED: ${{ inputs.ignored }}
        DEBUG_ACTION: ${{ inputs.debug_action }}
        GITHUB_API_URL: ${{ inputs.github_api_url }}
      run: |
        # Run the Python script that computes the label and posts it to the repo
        python3 ./size_label.py

Explanation:
- `env` maps the action inputs and important context into environment variables consumed by `size_label.py`.
- Note on `GITHUB_TOKEN`: in workflows `secrets.GITHUB_TOKEN` is automatically created and should be passed to the action. The action uses it to authenticate to the API.
- `GITHUB_EVENT_PATH` is provided by the runner (`github.event_path`) and points to the event JSON file the action reads to identify the PR.
- The `python3` invocation runs the script in the repository root.

Important security and permission notes
- The example workflow uses `pull_request_target`. That event runs in the context of the base repository, not the fork, which is required if the action needs to write labels using `GITHUB_TOKEN` from the base repository. This is why the example uses `pull_request_target` instead of `pull_request`.
- Ensure the job's permissions include `pull-requests: write` (or `contents: read` and `issues: write` depending on your policy) so the token can add labels.

Detailed breakdown: `.github/workflows/size-label.yml` (example)

Contents (annotated)

name: Label PR by size (example)

on:
  pull_request_target:

jobs:
  label-by-size:
    runs-on: ubuntu-latest
    permissions:
      contents: read
      pull-requests: write
    steps:
      - name: Run size label action
        uses: ./.github/actions/size-label
        with:
          input_sizes: '{"0":"XS","20":"S","50":"M","200":"L","800":"XL","2000":"XXL"}'
          ignored: |
            docs/**
            **/*.md
          debug_action: 'false'

Explanation:
- This workflow triggers on `pull_request_target` and runs the local action we added.
- `permissions` are set to allow reading repo contents and writing pull-request labels.
- The `with` block shows how to pass the `INPUT_SIZES` JSON and an `IGNORED` multi-line value.

Step-by-step usage
1. Commit `size_label.py` (already in the repo) and the new action files.
2. Create or update `.github/workflows/size-label.yml` in your repo (the example file is already added).
3. Push a branch and open a PR — the workflow will run and the action will call `size_label.py`.

How inputs and secrets flow
- Workflow -> action `with` inputs -> mapped to env variables in action -> `size_label.py` reads env variables.
- `GITHUB_TOKEN` is supplied from `secrets.GITHUB_TOKEN` and is made available as `GITHUB_TOKEN` env var to the script.

Why not a Docker / JavaScript action?
- Composite actions are simpler when your action's steps are just a sequence of runner steps (checkout, setup runtime, run script). They avoid the complexity of building and publishing Docker images or JS bundles. For more isolation or cross-platform guarantees, Docker actions can be better, but are more complex.

What I changed (summary)
- Added a composite action wrapper so `size_label.py` can be used like a native action in workflows.
- Added an example workflow that demonstrates recommended permissions and input usage.
- Created this explanation file that includes the action metadata and step-by-step guidance.

Optional next improvements (teaching suggestions)
- Add a small `event.example.json` file for local testing and show how to set `GITHUB_EVENT_PATH` to test locally.
- Add minimal unit tests for `compute_label`.
- Add retry/backoff around `github_request` to make the script more robust to transient network/API errors.

If you want, I can now:
- Add `event.example.json` and a short local testing guide; or
- Add a `tests/` directory with unit tests for `compute_label` and `parse_ignored` using `unittest`.

Tell me which you'd like and I'll add it next.

---

Creating and publishing `v1` (what I did and best practices)

I created a git tag `v1` in this repository and pushed it to the remote `origin` so the workflow step
`uses: iahmedsabry/size-label@v1` resolves to this repository's tagged code.

Exact commands used (run in repository root):

```bash
git tag -a v1 -m "v1: release composite action for size_label.py"
git push origin v1
```

What these commands do:
- `git tag -a v1 -m "..."` creates an annotated tag named `v1` pointing to the current commit (annotated tags include a message and metadata and are preferred for releases).
- `git push origin v1` pushes the created tag to the `origin` remote so GitHub (and other collaborators) can fetch it.

Best practices and notes
- Use annotated tags (the `-a` option) for releases because they include the tagger name, date, and a message. Lightweight tags (`git tag name`) are only a reference and don't carry metadata.
- Tag the commit that represents a stable or intended release snapshot. If you need to tag another commit, specify the commit SHA: `git tag -a v1 <commit-sha> -m "message"`.
- Use semantic versioning where appropriate (for example `v1.0.0`) — here we created a `v1` alias tag as requested; consider adding more specific semver tags for future releases.
- Push tags to the remote so workflows that reference `uses: owner/repo@v1` can resolve to the tagged revision.
- If the repository is intended to publish an action to the GitHub Marketplace, add a release note or a CHANGELOG and create a proper release on GitHub for `v1`.
- Protect your release process: consider using CI checks (tests/lint) before tagging.

Verification (what I checked)
- Locally: `git tag --list` shows `v1`.
- Remotely: `git ls-remote --tags origin` (or checking the repo on GitHub) shows `refs/tags/v1`.

If you'd like I can:
- Create a semver tag such as `v1.0.0` and push it as well, or
- Create a GitHub Release from this tag and add release notes.


---

Note about the `test-add-label.yml` workflow

Per your request, I updated the existing workflow file `.github/workflows/test-add-label.yml` to call the published action instead of running the `size_label.py` script directly. The workflow now uses the action by reference:

```yaml
- name: Run size label action (remote)
  uses: iahmedsabry/size-label@v1
  with:
    input_sizes: '{"0":"XS","20":"S","50":"M","200":"L","800":"XL","2000":"XXL"}'
    debug_action: 'true'
```

Why this change?
- Using `uses: iahmedsabry/size-label@v1` lets you call a published action (for example a repository in your account or a marketplace action). This is useful when you want to centralize the action's implementation or reuse a versioned action across repositories.

Notes on behavior and environment
- The action implementation still expects `GITHUB_TOKEN` (and `GITHUB_EVENT_PATH`) to be available; these are provided by the workflow runner automatically when the job runs (the action's composite steps reference `secrets.GITHUB_TOKEN` and `github.event_path`). You don't need to set `GITHUB_TOKEN` via `env` in your workflow step.
- Pass only the inputs the action declares (`input_sizes`, `ignored`, `debug_action`, `github_api_url`) in the `with:` block.

What I changed in the repo
- Updated `.github/workflows/test-add-label.yml` to use `uses: iahmedsabry/size-label@v1`.
- Updated this explanation file to document the updated workflow and explain the mapping.

If you'd like, I can now:
- Publish the composite action to a tag `v1` in this repo (create a `v1` tag) so `uses: iahmedsabry/size-label@v1` will resolve to this code, or
- Keep the workflow pointing at the remote repository name you specified while you publish the action yourself.

Tell me which you'd prefer and I'll do it next.
