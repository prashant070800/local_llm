import os
import sys
import django
import json
import time

sys.path.append(os.path.dirname(os.path.abspath(__file__)))
os.environ.setdefault("DJANGO_SETTINGS_MODULE", "ollama_chat.settings")
django.setup()

from django.test import Client
from django.contrib.auth.models import User

def test_streaming_backend():
    # Create user if not exists
    username = 'debug_stream_user'
    password = 'password'
    if not User.objects.filter(username=username).exists():
        User.objects.create_user(username=username, password=password)
    
    client = Client()
    client.login(username=username, password=password)
    
    print("Sending request...")
    start_time = time.time()
    
    # We need to mock OllamaService to ensure it streams, 
    # OR we can rely on the real Ollama if it's running.
    # The user has `grout` running, so maybe Ollama is running locally?
    # The user's prompt implies they are using the app, so Ollama should be running.
    # But I can't be sure.
    # I'll try to hit the real endpoint. If Ollama is down, it will error.
    
    # Actually, I should use the mock to verify Django's streaming behavior independent of Ollama.
    # But the user says "stream response now not working", implying it was working.
    # So I should test the whole stack if possible, or at least the Django part.
    
    # Let's use the mock approach from `tests_debug.py` but as a standalone script.
    
    from unittest.mock import patch, MagicMock
    
    with patch('chat.services.requests.post') as mock_post:
        def mock_iter_content(chunk_size=None):
            words = ["Hello", " ", "World", " ", "from", " ", "Ollama", "!"]
            for word in words:
                time.sleep(0.1)
                yield (json.dumps({
                    "model": "llama3.1:8b",
                    "created_at": "2023-01-01T00:00:00Z",
                    "message": {"role": "assistant", "content": word},
                    "done": False
                }) + "\n").encode('utf-8')
            yield (json.dumps({"done": True}) + "\n").encode('utf-8')

        mock_response = MagicMock()
        mock_response.status_code = 200
        mock_response.iter_content.side_effect = mock_iter_content
        mock_response.__enter__.return_value = mock_response
        mock_response.__exit__.return_value = None
        mock_post.return_value = mock_response
        
        response = client.post(
            '/api/chat/',
            data=json.dumps({'prompt': 'Hi'}),
            content_type='application/json'
        )
        
        if response.status_code != 200:
            print(f"Error: {response.status_code}")
            return

        print("Response received. consuming stream...")
        chunk_count = 0
        first_chunk_time = None
        
        for chunk in response.streaming_content:
            now = time.time()
            if first_chunk_time is None:
                first_chunk_time = now
            
            chunk_count += 1
            print(f"Chunk {chunk_count} at {now - start_time:.4f}s: {chunk.decode('utf-8').strip()}")
            
        print(f"Total chunks: {chunk_count}")

if __name__ == "__main__":
    test_streaming_backend()
