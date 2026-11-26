"""Measure concurrent health requests on the disposable CI stack."""
import json
import statistics
import time
from concurrent.futures import ThreadPoolExecutor
from urllib.request import urlopen

URL = "http://127.0.0.1:18080/api/v1/health"


def probe(_):
    start = time.perf_counter()
    with urlopen(URL, timeout=15) as response:  # nosec B310 - fixed loopback URL
        assert response.status == 200
        assert json.load(response)["status"] == "ok"
    return (time.perf_counter() - start) * 1000


def main():
    start = time.perf_counter()
    with ThreadPoolExecutor(max_workers=4) as pool:
        latencies = list(pool.map(probe, range(40)))
    report = {
        "endpoint": "/api/v1/health",
        "requests": len(latencies),
        "concurrency": 4,
        "median_ms": round(statistics.median(latencies), 2),
        "p95_ms": round(sorted(latencies)[37], 2),
        "requests_per_second": round(len(latencies) / (time.perf_counter() - start), 2),
    }
    print(json.dumps(report, indent=2))
    with open("load-smoke-results.json", "w", encoding="utf-8") as file:
        json.dump(report, file, indent=2)


if __name__ == "__main__":
    main()
