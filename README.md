## size-label.sh

Labels PRs by size based on total changed lines. Adds `size/XS`, `size/S`, `size/M`, `size/L`, `size/XL`, or `size/XXL`.

### Defaults
- Thresholds: `{0: XS, 10: S, 30: M, 100: L, 500: XL, 1000: XXL}`
- Events handled: `opened`, `synchronize`, `reopened`

### Usage (GitHub Actions)
Create `.github/workflows/size-label.yml`:

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

      - name: Run size-label.sh
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
          bash size-label.sh
```

### Notes
- Works on `ubuntu-latest` without installing `jq` (available by default).
- `GITHUB_TOKEN` must have permission to add labels to the PR.


