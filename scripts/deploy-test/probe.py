"""Send requests nonstop during a local deploy test and report the failures.

    python3 scripts/deploy-test/probe.py <seconds> <url> [<url> ...]

Four threads per URL. A request fails on a connection error, a timeout or a
5xx. See docs/architecture/deploys.md.
"""

import http.client
import sys
import threading
import time
import urllib.parse

THREADS_PER_URL = 4

duration = float(sys.argv[1])
urls = sys.argv[2:]
results = []
lock = threading.Lock()
stop_at = time.time() + duration


def worker(url):
    parts = urllib.parse.urlsplit(url)
    while time.time() < stop_at:
        start = time.time()
        try:
            conn = http.client.HTTPConnection(parts.hostname, parts.port, timeout=30)
            conn.request("GET", parts.path or "/")
            response = conn.getresponse()
            response.read()
            conn.close()
            outcome = response.status
        except Exception as exc:  # noqa: BLE001 - every failure is a result
            outcome = f"{type(exc).__name__}: {exc}"[:100]
        with lock:
            results.append((start, url, outcome, time.time() - start))
        time.sleep(0.05)


threads = [threading.Thread(target=worker, args=(url,)) for url in urls for _ in range(THREADS_PER_URL)]
for thread in threads:
    thread.start()
for thread in threads:
    thread.join()

t0 = min(row[0] for row in results)
for url in urls:
    rows = [row for row in results if row[1] == url]
    failed = [row for row in rows if not (isinstance(row[2], int) and row[2] < 500)]
    slowest = max(row[3] for row in rows)
    print(f"{url}: {len(rows)} requests, {len(failed)} failed, slowest {slowest:.1f}s")
    if failed:
        print(f"  failures from +{failed[0][0] - t0:.1f}s to +{failed[-1][0] - t0:.1f}s")
        kinds = {}
        for row in failed:
            kinds[str(row[2])] = kinds.get(str(row[2]), 0) + 1
        for kind, count in sorted(kinds.items(), key=lambda item: -item[1]):
            print(f"    {count:5d}  {kind}")
