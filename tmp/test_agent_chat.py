import requests
import json
import time

def test_agent_chat():
    url = "http://localhost:8000/api/chat"
    payload = {
        "query": "Who is responsible for the Nexus ingestion pipeline and how was it fixed?",
        "max_iterations": 5
    }
    
    print(f"Starting Agentic Chat with query: '{payload['query']}'\n")
    
    try:
        # Use stream=True for SSE
        with requests.post(url, json=payload, stream=True) as response:
            if response.status_code == 200:
                for line in response.iter_lines():
                    if line:
                        decoded_line = line.decode('utf-8')
                        if decoded_line.startswith("data: "):
                            data = decoded_line[6:]
                            if data == "[DONE]":
                                print("\n--- Stream Finished ---")
                                break
                            
                            step = json.loads(data)
                            node = step.get("node", "unknown")
                            agent = step.get("agent", "")
                            status = step.get("status", "")
                            final_answer = step.get("final_answer", "")
                            
                            print(f"[{node.upper()}] Next Agent: {agent} | Status: {status}")
                            if final_answer:
                                print(f"ANSWER: {final_answer}")
            else:
                print(f"Error: {response.status_code} - {response.text}")
    except Exception as e:
        print(f"Connection failed: {e}")

if __name__ == "__main__":
    # Give server a second to reload
    time.sleep(2)
    test_agent_chat()
