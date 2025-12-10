from django.urls import path
from . import views

urlpatterns = [
    path('', views.index, name='index'),
    path('register/', views.register, name='register'),
    path('login/', views.login_view, name='login'),
    path('logout/', views.logout_view, name='logout'),
    path('api/chat/', views.api_chat, name='api_chat'),
    path('api/messages/<int:conversation_id>/', views.get_messages, name='get_messages'),
    path('api/models/', views.get_models, name='get_models'),
]
