## size_label.py

Labels PRs by size based on total changed lines. Adds `size/XS`, `size/S`, `size/M`, `size/L`, `size/XL`, or `size/XXL`.

This repository now includes a Python implementation: `size_label.py` (a port of the original `size-label.sh`). The Python script uses only the standard library and does not require extra packages.

### Defaults
- Thresholds: `{0: XS, 10: S, 30: M, 100: L, 500: XL, 1000: XXL}`
- Events handled: `opened`, `synchronize`, `reopened`

### Prerequisites
- Python 3 (3.6+ recommended).
- No additional Python packages required — the script uses the standard library for HTTP requests.

### Usage (GitHub Actions)
Create `.github/workflows/size-label.yml` and call the Python script:

```yaml
name: Test Size Label Script

on:
  pull_request_target:

jobs:
  label-by-size:
    runs-on: ubuntu-latest
    permissions:
      contents: read
      pull-requests: write
    steps:
      - name: Checkout repository
        uses: actions/checkout@v4

      - name: Run size_label.py
        env:
          GITHUB_TOKEN: ${{ secrets.GITHUB_TOKEN }}
          INPUT_SIZES: >
            {"0":"XS","20":"S","50":"M","200":"L","800":"XL","2000":"XXL"}
          # Optional:
          # IGNORED: |
          #   docs/**
          #   **/*.md
          # DEBUG_ACTION: "true"
        run: |
          python3 size_label.py
```

If you prefer to use the script directly on a runner that has `python` mapped to Python 3, you can use `python size_label.py` instead of `python3`.

### PowerShell (local) example
If you run the script locally on Windows PowerShell, set the required environment variables and run:

```powershell
$env:GITHUB_TOKEN = 'ghp_...'
$env:GITHUB_EVENT_PATH = 'path\to\event.json'
$env:INPUT_SIZES = '{"0":"XS","20":"S","50":"M","200":"L","800":"XL","2000":"XXL"}'
python .\size_label.py
```

### Notes
- `GITHUB_TOKEN` must have permission to add labels to the PR.


