"""
Seed script: Populates realistic links and simulates diverse click traffic
(referrers, client devices, timestamps) across Redis Streams and PostgreSQL.

Usage:
    python seed_data.py
"""

import random
import time
import httpx

API_BASE_URL = "http://localhost:8000"

SEED_LINKS = [
    {
        "custom_alias": "torvalds",
        "original_url": "https://github.com/torvalds/linux",
    },
    {
        "custom_alias": "fastapi",
        "original_url": "https://fastapi.tiangolo.com/tutorial/",
    },
    {
        "custom_alias": "streams",
        "original_url": "https://redis.io/docs/latest/develop/data-types/streams/",
    },
    {
        "custom_alias": "grafana",
        "original_url": "https://grafana.com/docs/grafana/latest/dashboards/",
    },
    {
        "custom_alias": "python",
        "original_url": "https://www.python.org/downloads/",
    },
]

USER_AGENTS = [
    "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/128.0.0.0 Safari/537.36",
    "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/128.0.0.0 Safari/537.36",
    "Mozilla/5.0 (iPhone; CPU iPhone OS 17_6 like Mac OS X) AppleWebKit/605.1.15 (KHTML, like Gecko) Version/17.5 Mobile/15E148 Safari/604.1",
    "Mozilla/5.0 (X11; Linux x86_64; rv:129.0) Gecko/20100101 Firefox/129.0",
    "Mozilla/5.0 (iPad; CPU OS 17_6 like Mac OS X) AppleWebKit/605.1.15 (KHTML, like Gecko) Version/17.5 Mobile/15E148 Safari/604.1",
]

REFERRERS = [
    "https://github.com",
    "https://news.ycombinator.com",
    "https://twitter.com/x",
    "https://reddit.com/r/programming",
    "https://linkedin.com/feed",
    "https://google.com/search",
    "",  # Direct traffic
]


def seed_platform():
    print("=" * 60)
    print("[*] Seeding Link Analytics Platform with realistic demo traffic...")
    print("=" * 60)

    client = httpx.Client(base_url=API_BASE_URL, timeout=10.0)

    # 1. Create Links
    created_codes = []
    for item in SEED_LINKS:
        try:
            res = client.post("/links", json=item)
            if res.status_code in (201, 200):
                print(f"[+] Created short link: /{item['custom_alias']} -> {item['original_url']}")
                created_codes.append(item["custom_alias"])
            elif res.status_code == 409:
                print(f"[i] Link /{item['custom_alias']} already exists.")
                created_codes.append(item["custom_alias"])
            else:
                print(f"[!] Unexpected response ({res.status_code}): {res.text}")
        except Exception as e:
            print(f"[-] Could not connect to {API_BASE_URL}: {e}")
            return

    # 2. Simulate Click Traffic
    print("\n[*] Simulating diverse click stream events...")
    total_clicks = 0
    for code in created_codes:
        clicks_for_link = random.randint(5, 12)
        for _ in range(clicks_for_link):
            ua = random.choice(USER_AGENTS)
            ref = random.choice(REFERRERS)
            headers = {"User-Agent": ua}
            if ref:
                headers["Referer"] = ref

            try:
                # Follow redirect false so we just trigger the 307
                client.get(f"/{code}", headers=headers, follow_redirects=False)
                total_clicks += 1
                time.sleep(0.05)  # small spacing
            except Exception as e:
                print(f"Click error on /{code}: {e}")

        print(f"  * Generated {clicks_for_link} stream events for /{code}")

    print("\n" + "=" * 60)
    print(f"[OK] Seeding Complete! Total clicks generated: {total_clicks}")
    print(f"[*] Open Frontend:  http://localhost:3001")
    print(f"[*] Open Grafana:   http://localhost:3000")
    print(f"[*] API Reference:  http://localhost:8000/docs")
    print("=" * 60)


if __name__ == "__main__":
    seed_platform()
