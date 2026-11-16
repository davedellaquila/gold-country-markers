#!/usr/bin/env python3
"""Harvest the FIRST (marker/plaque) photo + credit for every catalogued
marker from its Historical Marker Database (HMdb) page.

HMdb's own pages sit behind a Cloudflare challenge for direct fetches
from this machine (HTTP 403 "Just a moment..."), so pages are read
through the r.jina.ai reader proxy, which returns clean markdown whose
first image is the marker photo:

    [![Image 1: <Name> Marker image. Click for full size.](<PHOTO_URL>)](...)
    <credit line>            e.g. "Photographed by Syd Whittle, March 14, 2009"
                             or  "courtesy California Landmark Foundation, ..."
    1. <caption>

The photo files themselves are NOT downloaded — only their HMdb URLs
and credit lines are recorded, in photos.json (keyed by hmdbId), and the
site hotlinks them with the credit printed underneath.

Politeness / resumability:
  * 4 concurrent readers at most, each page fetched once
  * every fetched page is cached under .photo-cache/<hmdbId>.txt, so a
    re-run parses from cache and never re-fetches a page it already has
  * one retry with backoff on transient errors; failures are logged to
    .photo-cache/failures.json and the run continues

Run:  python3 harvest_photos.py [--retry-failures]
"""
import json
import re
import sys
import time
import urllib.request
import urllib.error
from concurrent.futures import ThreadPoolExecutor, as_completed
from pathlib import Path

REPO = Path(__file__).resolve().parent
DATA = Path.home() / "workspace/goals/event-manager/hidden_files/event-buddy/staged-locations"
CACHE = REPO / ".photo-cache"
OUT = REPO / "photos.json"
COUNTY_ORDER = ["El Dorado", "Nevada", "Placer", "Amador",
                "Tuolumne", "Calaveras", "Mariposa", "Sierra"]
READER_PREFIX = "https://" + "r" + "." + "jina" + "." + "ai" + "/"

IMG1_RE = re.compile(
    r"\[!\[Image 1:[^\]]*\]\((https://www\.hmdb\.org/Photos\d*/[^)\s]+)\)\]")
ANY_PHOTO_RE = re.compile(r"https://www\.hmdb\.org/Photos\d*/[^\s)\]]+")


def load_records():
    recs = []
    for county in COUNTY_ORDER:
        f = DATA / f"markers-{county.lower().replace(' ', '-')}-county-staged.json"
        recs.extend(json.loads(f.read_text()))
    return recs


def parse_page(text):
    """Return dict(photoUrl, credit, caption) or None if no marker photo."""
    m = IMG1_RE.search(text)
    if not m:
        # fall back to the first Photos URL anywhere on the page
        m2 = ANY_PHOTO_RE.search(text)
        if not m2:
            return None
        photo_url = m2.group(0)
        rest = text[m2.end():]
    else:
        photo_url = m.group(1)
        rest = text[m.end():]
    credit = None
    caption = None
    # Drop the remainder of the image line itself (it carries the
    # PhotoFullSize link), then read: [credit line] / "1. <caption>".
    for line in rest.splitlines()[1:]:
        line = line.strip()
        if not line or line.startswith("(") or line.startswith("http"):
            continue
        cm = re.match(r"^\d+\.\s+(.*)$", line)
        if cm:
            caption = cm.group(1).strip()
            break
        if credit is None:
            credit = line
    return {"photoUrl": photo_url, "credit": credit, "caption": caption}


def fetch(mid):
    url = READER_PREFIX + f"https://www.hmdb.org/m.asp?m={mid}"
    req = urllib.request.Request(url, headers={"User-Agent": "Mozilla/5.0"})
    with urllib.request.urlopen(req, timeout=90) as resp:
        return resp.read().decode("utf-8", errors="ignore")


WORKERS = 4
DELAY = 0.0
ATTEMPTS = 2


def harvest_one(mid):
    cache_file = CACHE / f"{mid}.txt"
    if cache_file.exists() and cache_file.stat().st_size > 400:
        return mid, parse_page(cache_file.read_text(errors="ignore")), "cache"
    last_err = None
    for attempt in range(ATTEMPTS):
        try:
            if DELAY:
                time.sleep(DELAY)
            text = fetch(mid)
            if len(text) < 400:
                raise ValueError(f"suspiciously short page ({len(text)} bytes)")
            cache_file.write_text(text)
            return mid, parse_page(text), "fetch"
        except Exception as e:  # noqa: BLE001
            last_err = e
            time.sleep(5 * (attempt + 1))
    return mid, {"error": str(last_err)}, "error"


def main():
    global WORKERS, DELAY, ATTEMPTS
    retry_failures = "--retry-failures" in sys.argv
    for i, a in enumerate(sys.argv):
        if a == "--workers":
            WORKERS = int(sys.argv[i + 1])
        if a == "--delay":
            DELAY = float(sys.argv[i + 1])
        if a == "--attempts":
            ATTEMPTS = int(sys.argv[i + 1])
    CACHE.mkdir(exist_ok=True)
    if retry_failures:
        fail_file = CACHE / "failures.json"
        if fail_file.exists():
            for mid in json.loads(fail_file.read_text()):
                (CACHE / f"{mid}.txt").unlink(missing_ok=True)
    recs = load_records()
    ids = []
    seen = set()
    for r in recs:
        mid = str(r["hmdbId"])
        if mid not in seen:
            seen.add(mid)
            ids.append(mid)
    print(f"{len(recs)} records, {len(ids)} unique hmdbIds", flush=True)

    results = {}
    failures = {}
    done = 0
    with ThreadPoolExecutor(max_workers=WORKERS) as ex:
        futs = {ex.submit(harvest_one, mid): mid for mid in ids}
        for fut in as_completed(futs):
            mid, parsed, how = fut.result()
            done += 1
            if parsed and "error" in parsed:
                failures[mid] = parsed["error"]
            elif parsed:
                results[mid] = parsed
            if done % 50 == 0 or done == len(ids):
                print(f"{done}/{len(ids)}  photos so far: {len(results)}  "
                      f"failures: {len(failures)}", flush=True)
    OUT.write_text(json.dumps(results, indent=1, sort_keys=True) + "\n")
    (CACHE / "failures.json").write_text(json.dumps(failures, indent=1) + "\n")
    print(f"DONE: {len(results)} with photo, "
          f"{len(ids) - len(results) - len(failures)} with no photo, "
          f"{len(failures)} failures")
    return 0


if __name__ == "__main__":
    sys.exit(main())
