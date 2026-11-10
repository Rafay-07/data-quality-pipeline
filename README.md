# data-quality-pipeline

A small data pipeline in Python and SQLite that turns a messy CSV into a clean table and a quality report. Rows that break the rules are quarantined with the reason instead of silently dropped. Comments in `pipeline.py` explain each stage.

```
read -> clean -> validate -> dedupe -> load good rows / quarantine bad rows -> report
```

## Sample result

```
DATA QUALITY REPORT
Rows read:        9
Loaded:           3
Duplicates:       1
Rejected:         5
Pass rate:        33.3%

Rejected rows:
  line 3: email: bad format 'bob@example'
  line 4: quantity: 0 outside 1-1000
  line 7: customer: missing
  ...
```

## What it checks

- Required fields, regex formats (order id, email), numeric ranges, and dates.
- Cleaning: trims spaces, fixes name case, lowercases email, strips `$` and commas from prices, and converts three date formats to ISO.
- Duplicate order ids: the first row wins and the repeat is counted.

Change the `RULES` dictionary to fit another dataset.

## Run

```bash
pip install pytest
python -m pytest -q          # 6 tests
python pipeline.py sample_orders.csv
```

## Limits

Date formats with day and month swapped (`03/10/2026`) are ambiguous; this pipeline assumes day first for slashes. Reads whole files row by row, so very large files would need batching.
