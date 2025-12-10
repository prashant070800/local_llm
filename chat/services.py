import queue
import threading
import requests
import json
import time

class OllamaService:
    _instance = None
    _lock = threading.Lock()

    def __new__(cls, *args, **kwargs):
        if not cls._instance:
            with cls._lock:
                if not cls._instance:
                    cls._instance = super(OllamaService, cls).__new__(cls)
                    cls._instance._initialized = False
        return cls._instance

    def __init__(self):
        if self._initialized:
            return
        
        # Queue size N=5
        self.queue = queue.Queue(maxsize=5)
        self.worker_thread = threading.Thread(target=self._worker, daemon=True)
        self.worker_thread.start()
        self._initialized = True
        self.base_url = "http://localhost:11434"

    def get_available_models(self):
        try:
            response = requests.get(f"{self.base_url}/api/tags")
            if response.status_code == 200:
                data = response.json()
                return [model['name'] for model in data.get('models', [])]
            return []
        except Exception as e:
            print(f"Error fetching models: {e}")
            return []

    def process_chat(self, messages, model="llama3.1:8b"):
        """
        Adds chat request to queue.
        Args:
            messages: List of dicts [{'role': 'user'|'assistant', 'content': '...'}]
            model: Model name string
        Returns:
            - (response_text, None) if successful
            - (None, "Queue Full") if queue is full
        """
        result_event = threading.Event()
        result_container = {}

        try:
            # Try to put in queue, non-blocking if full
            self.queue.put_nowait(({
                'type': 'chat',
                'messages': messages,
                'model': model
            }, result_event, result_container))
        except queue.Full:
            return None, "Queue Full"

        # Wait for the result
        result_event.wait()
        return result_container.get('response'), result_container.get('error')

    def _worker(self):
        while True:
            data, event, container = self.queue.get()
            try:
                # Process the request
                if data['type'] == 'chat':
                    payload = {
                        "model": data['model'],
                        "messages": data['messages'],
                        "stream": False
                    }
                    response = requests.post(f"{self.base_url}/api/chat", json=payload)
                    if response.status_code == 200:
                        resp_data = response.json()
                        # Ollama chat response structure: {'message': {'role': 'assistant', 'content': '...'}, ...}
                        container['response'] = resp_data.get('message', {}).get('content', '')
                    else:
                        container['error'] = f"Ollama API Error: {response.status_code} - {response.text}"
            except Exception as e:
                container['error'] = str(e)
            finally:
                event.set()
                self.queue.task_done()
