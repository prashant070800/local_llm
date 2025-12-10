import threading
import requests
import time

def send_request(i):
    url = "http://localhost:8000/api/chat/"
    payload = {"prompt": f"Hello from request {i}"}
    try:
        start = time.time()
        print(f"Request {i} started")
        response = requests.post(url, json=payload)
        duration = time.time() - start
        print(f"Request {i} finished in {duration:.2f}s with status {response.status_code}")
        return response.status_code
    except Exception as e:
        print(f"Request {i} failed: {e}")
        return 0

def test_concurrency():
    threads = []
    # Send 10 requests. 
    # 1 should process immediately.
    # 5 should queue.
    # 4 should get 409 (since queue size is 5).
    # Wait, actually:
    # The worker picks one immediately.
    # So queue has space for 5.
    # If we send 10 at once:
    # 1 is processing.
    # 5 are in queue.
    # 4 should be rejected.
    
    for i in range(10):
        t = threading.Thread(target=send_request, args=(i,))
        threads.append(t)
        t.start()
    
    for t in threads:
        t.join()

if __name__ == "__main__":
    # Wait for server to start
    time.sleep(3)
    test_concurrency()
