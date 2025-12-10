from django.shortcuts import render, redirect, get_object_or_404
from django.http import JsonResponse, StreamingHttpResponse
from django.views.decorators.csrf import csrf_exempt
from django.views.decorators.http import require_http_methods
from django.contrib.auth.decorators import login_required
from django.contrib.auth import login, logout
from django.contrib.auth.forms import UserCreationForm, AuthenticationForm
import json
import queue
from .services import OllamaService
from .models import Conversation, Message

def register(request):
    if request.method == "POST":
        form = UserCreationForm(request.POST)
        if form.is_valid():
            user = form.save()
            login(request, user)
            return redirect('index')
    else:
        form = UserCreationForm()
    return render(request, 'registration/register.html', {'form': form})

def login_view(request):
    if request.method == "POST":
        form = AuthenticationForm(request, data=request.POST)
        if form.is_valid():
            login(request, form.get_user())
            return redirect('index')
    else:
        form = AuthenticationForm()
    return render(request, 'registration/login.html', {'form': form})

def logout_view(request):
    logout(request)
    return redirect('login')

@login_required
def index(request):
    conversations = request.user.conversations.all()
    return render(request, 'chat/index.html', {'conversations': conversations})

@login_required
def get_messages(request, conversation_id):
    conversation = get_object_or_404(Conversation, id=conversation_id, user=request.user)
    messages = conversation.messages.all()
    return JsonResponse({
        'messages': [{'role': m.role, 'content': m.content} for m in messages]
    })

@login_required
def get_models(request):
    service = OllamaService()
    models = service.get_available_models()
    return JsonResponse({'models': models})

@csrf_exempt
@require_http_methods(["POST"])
@login_required
def api_chat(request):
    try:
        data = json.loads(request.body)
        prompt = data.get('prompt')
        conversation_id = data.get('conversation_id')
        model_name = data.get('model', 'llama3.1:8b')

        if not prompt:
            return JsonResponse({'error': 'Prompt is required'}, status=400)

        # Get or create conversation
        if conversation_id:
            conversation = get_object_or_404(Conversation, id=conversation_id, user=request.user)
        else:
            # Create new conversation
            title = (prompt[:30] + '...') if len(prompt) > 30 else prompt
            conversation = Conversation.objects.create(user=request.user, title=title)
        
        # Save User Message
        Message.objects.create(conversation=conversation, role='user', content=prompt)

        # Prepare context (last 10 messages)
        # Ollama expects 'assistant' for bot role
        recent_messages = conversation.messages.order_by('-created_at')[:10]
        # Reverse to get chronological order
        context_messages = []
        for msg in reversed(recent_messages):
            role = 'assistant' if msg.role == 'bot' else 'user'
            context_messages.append({'role': role, 'content': msg.content})
        
        service = OllamaService()
        try:
            chat_generator = service.process_chat(context_messages, model=model_name)
        except queue.Full:
            return JsonResponse({'error': 'Server is busy, please try again later.'}, status=409)

        def stream_response():
            # Yield metadata first
            yield json.dumps({
                'conversation_id': conversation.id,
                'title': conversation.title
            }) + "\n"
            
            full_response = []
            try:
                for chunk in chat_generator:
                    full_response.append(chunk)
                    yield json.dumps({'content': chunk}) + "\n"
                
                # Save Bot Message after full response is received
                Message.objects.create(conversation=conversation, role='bot', content="".join(full_response))
                
            except Exception as e:
                yield json.dumps({'error': str(e)}) + "\n"

        response = StreamingHttpResponse(stream_response(), content_type='application/x-ndjson')
        response['X-Accel-Buffering'] = 'no'  # Disable buffering in Nginx/proxies
        return response

    except json.JSONDecodeError:
        return JsonResponse({'error': 'Invalid JSON'}, status=400)
    except Exception as e:
        return JsonResponse({'error': str(e)}, status=500)
