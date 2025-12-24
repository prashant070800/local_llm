import os
import django
from django.conf import settings

if not settings.configured:
    os.environ.setdefault("DJANGO_SETTINGS_MODULE", "ollama_chat.settings")
    django.setup()

from django.test import TestCase, Client
from django.contrib.auth.models import User
from unittest.mock import patch
import json
import time

class DebugStreamingTests(TestCase):
    def setUp(self):
        self.user = User.objects.create_user(username='debuguser', password='password')
        self.client = Client()
        self.client.login(username='debuguser', password='password')

    @patch('chat.services.requests.post')
    def test_streaming_timing(self, mock_post):
        # Mock Ollama response with a slow generator
        def mock_iter_content(chunk_size=None):
            words = ["Hello", " ", "World", " ", "from", " ", "Ollama", "!"]
            for word in words:
                time.sleep(0.1) # Simulate delay
                # Yield full line for simplicity, or partials to test splitting
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

        # Wait, I need to patch the service to use this mock, 
        # but the service uses `requests.post` directly.
        # So patching `chat.services.requests.post` should work.
        
        print("\n--- Starting Streaming Debug Test ---")
        start_time = time.time()
        
        response = self.client.post(
            '/api/chat/',
            data=json.dumps({'prompt': 'Hi'}),
            content_type='application/json'
        )
        
        self.assertEqual(response.status_code, 200)
        self.assertTrue(response.streaming)
        
        first_chunk_time = None
        last_chunk_time = None
        chunk_count = 0
        
        for chunk in response.streaming_content:
            now = time.time()
            if first_chunk_time is None:
                first_chunk_time = now
            last_chunk_time = now
            chunk_count += 1
            print(f"Received chunk {chunk_count} at {now - start_time:.4f}s: {chunk.decode('utf-8').strip()}")
            
        total_duration = last_chunk_time - start_time
        print(f"Total duration: {total_duration:.4f}s")
        
        # If buffering happened, total_duration might be close to sum of sleeps but chunks would arrive all at once?
        # Wait, if `response.streaming_content` iterates, it pulls from the generator.
        # If the generator sleeps, the iterator waits.
        # So we should see chunks arriving at 0.1s intervals.
        
        # If Django buffers, `streaming_content` might yield everything at once after 0.8s.
        
        # But wait, `Client` in Django test might behave differently than a real browser request?
        # Django `Client` consumes the iterator.
        # If `StreamingHttpResponse` is working, `Client` should get chunks as they are yielded.
        
        pass

from unittest.mock import MagicMock
