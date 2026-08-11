import urllib.request
import urllib.error
import json
import time

URL = "http://122.160.253.37:8000/v1/chat/completions"
API_KEY = "Himanshu@126"
MODEL = "qwen3.6-35b-a3b"

headers = {
    "Content-Type": "application/json",
    "Authorization": f"Bearer {API_KEY}"
}

data = {
    "model": MODEL,
    "messages": [
        {"role": "user", "content": "Please write a comprehensive, 1000-word essay about the history and future of artificial intelligence in software development."}
    ],
    "stream": False,
    "max_tokens": 50
}

req = urllib.request.Request(URL, data=json.dumps(data).encode("utf-8"), headers=headers, method="POST")

print(f"Starting benchmark for {MODEL} on {URL}...")
start_time = time.time()

try:
    with urllib.request.urlopen(req) as response:
        result = json.loads(response.read().decode("utf-8"))
        end_time = time.time()
        
        duration = end_time - start_time
        usage = result.get("usage", {})
        completion_tokens = usage.get("completion_tokens", 0)
        total_tokens = usage.get("total_tokens", 0)
        
        if completion_tokens > 0:
            tps = completion_tokens / duration
            print(f"\\n--- Benchmark Results ---")
            print(f"Total Time: {duration:.2f} seconds")
            print(f"Tokens Generated: {completion_tokens}")
            print(f"Tokens Per Second (TPS): {tps:.2f} tokens/sec")
            print(f"-------------------------")
        else:
            print("Error: No tokens were generated. Response:")
            print(result)

except urllib.error.URLError as e:
    print(f"Failed to connect to the LLM API: {e}")
except Exception as e:
    print(f"An error occurred: {e}")
