# Chicago Parking Violation Data Fetcher

This script downloads parking violation records from the City of Chicago's Open Data API.
It focuses on recent data and saves results to `chicago_violations.json`.

## Usage

```bash
node chicago_scraper.js
```

Environment variables:
- `START_DATE` – start of the date range (`YYYY-MM-DD`)
- `END_DATE` – end of the date range (`YYYY-MM-DD`)
- `APP_TOKEN` – optional Socrata application token

The script currently fetches a small subset (default 5,000 records) centered on
Chicago's downtown area. Adjust `limit` and `maxPages` in the script for larger downloads.
