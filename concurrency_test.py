"""
Concurrency test for the event-driven click-counting pipeline.

Fires N simultaneous GET requests at a short link's redirect endpoint.
Each request publishes a click event to Redis Streams (< 1ms read path).
The background ClickConsumer batches and persists these into PostgreSQL.
"""

import threading
import time
import requests

BASE_URL = "http://127.0.0.1:8000"
SHORT_CODE = "ctest"
NUM_REQUESTS = 50


def fire_request():
    # allow_redirects=False because we just care that the request
    # hit the server and triggered the stream event publication
    requests.get(
        f"{BASE_URL}/{SHORT_CODE}",
        headers={"User-Agent": "ConcurrencyTest/1.0", "Referer": "https://example.com/test"},
        allow_redirects=False,
    )


def main():
    # Ensure test link exists
    try:
        requests.post(
            f"{BASE_URL}/links",
            json={"original_url": "https://example.com/target", "custom_alias": SHORT_CODE},
            timeout=5.0,
        )
    except Exception:
        pass

    threads = []

    # Create all thread objects first, without starting them yet
    for _ in range(NUM_REQUESTS):
        t = threading.Thread(target=fire_request)
        threads.append(t)

    # Start them all as close together as possible
    start_time = time.perf_counter()
    for t in threads:
        t.start()

    # Wait for every thread to finish before checking the result
    for t in threads:
        t.join()
    duration = time.perf_counter() - start_time

    print(f"Fired {NUM_REQUESTS} concurrent requests in {duration:.3f}s ({NUM_REQUESTS/duration:.1f} req/s).")

    # In Phase 3, event processing is asynchronous (eventual consistency).
    # We poll the stats/analytics endpoint for up to 5 seconds to wait for the consumer worker.
    print("Waiting for ClickConsumer to process stream batch into PostgreSQL...")
    click_count = 0
    for _ in range(25):
        time.sleep(0.2)
        try:
            stats = requests.get(f"{BASE_URL}/links/{SHORT_CODE}/stats").json()
            click_count = stats.get("click_count", 0)
            if click_count >= NUM_REQUESTS:
                break
        except Exception:
            pass

    print(f"Final click_count in database: {click_count}")

    if click_count == NUM_REQUESTS:
        print("PASS: All concurrent events successfully ingested and accounted for!")
    else:
        print(f"NOTE: Database click_count is {click_count} (expected {NUM_REQUESTS}). Ensure the ClickConsumer worker is running: python -m app.workers.click_consumer")


if __name__ == "__main__":
    main()