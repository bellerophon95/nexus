import asyncio
import json
import time

import httpx


async def test_sse_stability():
    print("--- SSE Stability & Heartbeat Verification ---")
    url = "http://localhost:8000/api/query?q=Tell me a very long story about AI agents in 2026&match_threshold=0.2&rerank=true&user_id=test_user"

    print(f"Connecting to: {url}")
    start_time = time.perf_counter()
    last_event_time = start_time
    heartbeats_received = 0
    tokens_received = 0
    complete = False

    try:
        async with httpx.AsyncClient(timeout=60.0) as client:
            async with client.stream("GET", url) as response:
                print(f"Status Code: {response.status_code}")
                if response.status_code != 200:
                    print("Error: Backend returned non-200 status")
                    return

                async for line in response.aiter_lines():
                    now = time.perf_counter()
                    delta = now - last_event_time

                    if line.startswith(": heartbeat"):
                        heartbeats_received += 1
                        print(
                            f"[HEARTBEAT] Received at +{now-start_time:.2f}s (Silence was {delta:.2f}s)"
                        )
                        last_event_time = now
                    elif line.startswith("data: "):
                        data = json.loads(line[6:])
                        if data["type"] == "token":
                            tokens_received += 1
                            if tokens_received % 50 == 0:
                                print(f"[TOKEN] Received {tokens_received} tokens...")
                        elif data["type"] == "agent_step":
                            print(f"[AGENT] {data['agent']}: {data['tool']} -> {data['status']}")
                        elif data["type"] == "done":
                            print(f"[DONE] Stream completed at +{now-start_time:.2f}s")
                            complete = True
                            break
                        last_event_time = now
                    elif line.strip() == "":
                        continue
                    else:
                        # Raw comment or other
                        print(f"[INFO] Raw line: {line[:50]}")
                        last_event_time = now

    except Exception as e:
        print(f"Connection Failed: {e}")

    print("\n--- Results ---")
    print(f"Total Time: {time.perf_counter()-start_time:.2f}s")
    print(f"Heartbeats Received: {heartbeats_received}")
    print(f"Tokens Received: {tokens_received}")
    print(f"Status: {'Success' if complete else 'Failed (Disconnected early)'}")


if __name__ == "__main__":
    asyncio.run(test_sse_stability())
