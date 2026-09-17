# Sleep Wire — local intelligence desk

No API keys, subscriptions, or paid services are needed. The local Python server reads public Google News RSS searches for sleep science, innovation, business and culture.

## Run it

1. Open a terminal in this folder.
2. Run `python server.py`.
3. Open http://localhost:8000 in your browser.

Use **Refresh intelligence** whenever you want a fresh scan. Each successful fresh scan writes an Excel-compatible CSV spreadsheet to `exports/`: `sleep-news-latest.csv` is the latest scan and `sleep-news-YYYYMMDD-HHMMSS.csv` is its archived copy. It includes date and time, title, summary, and link. You can also use **Download spreadsheet** in the dashboard. To avoid repeatedly hitting the public feeds, results are cached for five minutes; a browser reload or button press within that time returns the newest saved scan. The dashboard only displays feed metadata and each **Read original** link opens the publisher's article.

## Sleep Wellness Index

The dashboard also includes a continent, country, and city comparison panel. It is served at `/api/wellness` and refreshes with the desk. Its 0–100 scores are indicative product estimates, not clinical findings or an official health ranking; use it as a comparative dashboard view only.
