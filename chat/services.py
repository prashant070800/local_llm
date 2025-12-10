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
            - Generator yielding response chunks
            - Raises queue.Full if queue is full
        """
        response_queue = queue.Queue()
        
        try:
            # Try to put in queue, non-blocking if full
            self.queue.put_nowait({
                'type': 'chat',
                'messages': messages,
                'model': model,
                'response_queue': response_queue
            })
        except queue.Full:
            raise

        # Yield from response_queue
        while True:
            chunk = response_queue.get()
            if chunk is None:
                break
            if isinstance(chunk, Exception):
                raise chunk
            yield chunk

    def _worker(self):
        while True:
            data = self.queue.get()
            response_queue = data.get('response_queue')
            
            try:
                # Process the request
                if data['type'] == 'chat':
                    payload = {
                        "model": data['model'],
                        "messages": data['messages'],
                        "stream": True
                    }
                    with requests.post(f"{self.base_url}/api/chat", json=payload, stream=True) as response:
                        if response.status_code == 200:
                            buffer = b""
                            for chunk in response.iter_content(chunk_size=None):
                                if chunk:
                                    buffer += chunk
                                    while b"\n" in buffer:
                                        line, buffer = buffer.split(b"\n", 1)
                                        if line:
                                            try:
                                                json_response = json.loads(line)
                                                content = json_response.get('message', {}).get('content', '')
                                                if content:
                                                    response_queue.put(content)
                                                if json_response.get('done', False):
                                                    break
                                            except json.JSONDecodeError:
                                                continue
                        else:
                            response_queue.put(Exception(f"Ollama API Error: {response.status_code} - {response.text}"))
            except Exception as e:
                if response_queue:
                    response_queue.put(e)
            finally:
                if response_queue:
                    response_queue.put(None) # Signal end of stream
                self.queue.task_done()
