import os
import django
from django.conf import settings

if not settings.configured:
    os.environ.setdefault("DJANGO_SETTINGS_MODULE", "ollama_chat.settings")
    django.setup()

from django.test import TestCase, Client
from django.contrib.auth.models import User
from unittest.mock import patch, MagicMock
import json

class StreamingChatTests(TestCase):
    def setUp(self):
        self.user = User.objects.create_user(username='testuser', password='password')
        self.client = Client()
        self.client.login(username='testuser', password='password')

    @patch('chat.views.OllamaService')
    def test_streaming_response(self, MockService):
        # Mock the service instance and process_chat
        service_instance = MockService.return_value
        
        # Generator for process_chat
        def mock_chat_generator(messages, model):
            yield "Hello"
            yield " "
            yield "World"
        
        service_instance.process_chat.side_effect = mock_chat_generator

        response = self.client.post(
            '/api/chat/',
            data=json.dumps({'prompt': 'Hi'}),
            content_type='application/json'
        )

        self.assertEqual(response.status_code, 200)
        self.assertTrue(response.streaming)
        
        # Consume the stream
        content = b"".join(response.streaming_content)
        decoded_content = content.decode('utf-8')
        
        # Verify NDJSON structure
        lines = decoded_content.strip().split('\n')
        self.assertTrue(len(lines) >= 2) # Metadata + at least one content
        
        metadata = json.loads(lines[0])
        self.assertIn('conversation_id', metadata)
        
        text_content = ""
        for line in lines[1:]:
            data = json.loads(line)
            if 'content' in data:
                text_content += data['content']
        
        self.assertEqual(text_content, "Hello World")
