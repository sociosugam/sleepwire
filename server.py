"""Sleep Wire local server: public RSS only; no API key or paid service required."""
from concurrent.futures import ThreadPoolExecutor, as_completed
from csv import DictWriter
from datetime import datetime, timezone
from email.utils import parsedate_to_datetime
from http.server import SimpleHTTPRequestHandler, ThreadingHTTPServer
from io import StringIO
from pathlib import Path
from threading import Lock
from time import time
from urllib.parse import quote_plus
from urllib.request import Request, urlopen
from xml.etree import ElementTree as ET
import html
import json
import re

FEEDS = {
    "Science": "sleep science research",
    "Innovation": "sleep technology innovation wearable",
    "Business": "sleep startup funding business",
    "Culture": "sleep culture wellness work",
}
EXPORT_DIR = Path(__file__).parent / "exports"
CSV_FIELDS = ("date_and_time", "title", "summary", "link")

# Indicative comparative scores for the desk view; this is not an official
# health or clinical ranking and is labelled accordingly in the interface.
WELLNESS_PLACES = (
    ("Oceania", "Australia", "Melbourne", 84), ("Oceania", "New Zealand", "Wellington", 82),
    ("Europe", "Finland", "Helsinki", 83), ("Europe", "Sweden", "Stockholm", 81),
    ("Europe", "Denmark", "Copenhagen", 80), ("Europe", "Netherlands", "Amsterdam", 78),
    ("North America", "Canada", "Vancouver", 79), ("North America", "United States", "Minneapolis", 73),
    ("Asia", "Japan", "Tokyo", 76), ("Asia", "Singapore", "Singapore", 75), ("Asia", "India", "Bengaluru", 67),
    ("South America", "Chile", "Santiago", 71), ("South America", "Brazil", "Sao Paulo", 65),
    ("Africa", "South Africa", "Cape Town", 69), ("Africa", "Kenya", "Nairobi", 63),
)

def wellness_payload():
    groups = {"continents": {}, "countries": {}, "cities": []}
    for continent, country, city, score in WELLNESS_PLACES:
        groups["continents"].setdefault(continent, []).append(score)
        groups["countries"].setdefault(country, []).append(score)
        groups["cities"].append({"name": city, "score": score})
    rankings = {
        "continents": [{"name": name, "score": round(sum(scores) / len(scores))} for name, scores in groups["continents"].items()],
        "countries": [{"name": name, "score": round(sum(scores) / len(scores))} for name, scores in groups["countries"].items()],
        "cities": groups["cities"],
    }
    for ranking in rankings.values(): ranking.sort(key=lambda item: item["score"], reverse=True)
    return {"rankings": rankings, "updated_at": datetime.now(timezone.utc).isoformat()}

def clean(text):
    text = re.sub(r"<[^>]+>", " ", text or "")
    return re.sub(r"\s+", " ", html.unescape(text)).strip()

def summary(description, title, source, category):
    text = clean(description)
    text = re.sub(r"\s+-\s+[^-]{2,80}$", "", text)
    if not text or text.lower() == title.lower():
        return f"A current {category.lower()} update for the sleep ecosystem, reported by {source}. Open the original for the full context."
    return text[:278].rsplit(" ", 1)[0] + "..." if len(text) > 280 else text

def image_url(description):
    """Preserve a publisher-provided lead image from RSS when one is present."""
    match = re.search(r'<img[^>]+src=["\']([^"\']+)', description or "", re.I)
    return html.unescape(match.group(1)) if match else ""

def fetch_feed(category, query):
    url = "https://news.google.com/rss/search?q=" + quote_plus(query + " when:14d") + "&hl=en-US&gl=US&ceid=US:en"
    request = Request(url, headers={"User-Agent": "Mozilla/5.0 SleepWire/1.0"})
    with urlopen(request, timeout=12) as response:
        root = ET.fromstring(response.read())
    items = []
    for item in root.findall("./channel/item")[:10]:
        source = item.find("source")
        source_name = clean(source.text) if source is not None else "Google News"
        raw_title = clean(item.findtext("title"))
        title = re.sub(r"\s+-\s+" + re.escape(source_name) + r"$", "", raw_title, flags=re.I)
        published = item.findtext("pubDate", "")
        try:
            published = parsedate_to_datetime(published).isoformat()
        except (TypeError, ValueError):
            pass
        description = item.findtext("description")
        items.append({"title": title, "link": item.findtext("link", ""), "summary": summary(description, title, source_name, category), "source": source_name, "published": published, "category": category, "image": image_url(description)})
    return items

def spreadsheet_rows(stories):
    return [{"date_and_time": story.get("published", ""), "title": story.get("title", ""), "summary": story.get("summary", ""), "link": story.get("link", "")} for story in stories]

def make_csv(stories):
    output = StringIO(newline="")
    writer = DictWriter(output, fieldnames=CSV_FIELDS)
    writer.writeheader()
    writer.writerows(spreadsheet_rows(stories))
    return output.getvalue()

def save_spreadsheet(stories):
    EXPORT_DIR.mkdir(exist_ok=True)
    content = make_csv(stories)
    stamp = datetime.now(timezone.utc).strftime("%Y%m%d-%H%M%S")
    for name in ("sleep-news-latest.csv", f"sleep-news-{stamp}.csv"):
        (EXPORT_DIR / name).write_text(content, encoding="utf-8-sig", newline="")

class Handler(SimpleHTTPRequestHandler):
    cache = {"saved_at": 0, "payload": None}
    cache_lock = Lock()

    def __init__(self, *args, **kwargs):
        super().__init__(*args, directory=str(Path(__file__).parent), **kwargs)

    def do_GET(self):
        path = self.path.split("?")[0]
        if path == "/api/wellness":
            self.send_json(wellness_payload())
            return
        if path == "/api/news.csv":
            payload = self.get_payload()
            encoded = make_csv(payload["stories"]).encode("utf-8-sig")
            self.send_response(200)
            self.send_header("Content-Type", "text/csv; charset=utf-8")
            self.send_header("Content-Disposition", "attachment; filename=sleep-news-latest.csv")
            self.send_header("Content-Length", str(len(encoded)))
            self.end_headers()
            self.wfile.write(encoded)
            return
        if path != "/api/news":
            return super().do_GET()
        self.send_json(self.get_payload())

    def get_payload(self):
        with self.cache_lock:
            cached = self.cache["payload"] if time() - self.cache["saved_at"] < 300 else None
        if cached:
            return cached
        stories = []
        with ThreadPoolExecutor(max_workers=len(FEEDS)) as executor:
            jobs = [executor.submit(fetch_feed, category, query) for category, query in FEEDS.items()]
            for job in as_completed(jobs):
                try:
                    stories.extend(job.result())
                except Exception:
                    continue
        unique = {item["link"]: item for item in stories if item["link"]}
        stories = sorted(unique.values(), key=lambda item: item["published"], reverse=True)
        payload = {"stories": stories, "sources": len({item["source"] for item in stories}), "updated_at": time()}
        with self.cache_lock:
            self.cache = {"saved_at": time(), "payload": payload}
        if stories:
            save_spreadsheet(stories)
        return payload

    def send_json(self, payload):
        encoded = json.dumps(payload, ensure_ascii=False).encode("utf-8")
        self.send_response(200)
        self.send_header("Content-Type", "application/json; charset=utf-8")
        self.send_header("Cache-Control", "no-store")
        self.send_header("Content-Length", str(len(encoded)))
        self.end_headers()
        self.wfile.write(encoded)

if __name__ == "__main__":
    print("Sleep Wire is running at http://localhost:8000")
    ThreadingHTTPServer(("127.0.0.1", 8000), Handler).serve_forever()
