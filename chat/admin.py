from django.contrib import admin
from django.contrib.auth.admin import UserAdmin
from django.contrib.auth.models import User
from .models import Conversation, Message, UserLoginLog

# Unregister the provided model admin
admin.site.unregister(User)

class ConversationInline(admin.TabularInline):
    model = Conversation
    extra = 0
    readonly_fields = ('created_at', 'updated_at')
    show_change_link = True

class UserLoginLogInline(admin.TabularInline):
    model = UserLoginLog
    extra = 0
    readonly_fields = ('ip_address', 'user_agent', 'timestamp')
    can_delete = False
    ordering = ('-timestamp',)

@admin.register(User)
class CustomUserAdmin(UserAdmin):
    inlines = [ConversationInline, UserLoginLogInline]
    list_display = ('username', 'email', 'first_name', 'last_name', 'is_staff', 'conversation_count')
    
    def conversation_count(self, obj):
        return obj.conversations.count()
    conversation_count.short_description = 'Conversations'

from django.utils.html import format_html

@admin.register(Conversation)
class ConversationAdmin(admin.ModelAdmin):
    list_display = ('id', 'user', 'title', 'created_at', 'updated_at')
    list_filter = ('created_at', 'updated_at')
    search_fields = ('title', 'user__username')
    date_hierarchy = 'created_at'
    readonly_fields = ('chat_visual',)
    fields = ('user', 'title', 'chat_visual', 'created_at', 'updated_at')

    def chat_visual(self, obj):
        html = '<div style="max-width: 600px; font-family: sans-serif;">'
        for msg in obj.messages.all().order_by('created_at'):
            is_user = msg.role == 'user'
            align = 'right' if is_user else 'left'
            bg = '#10a37f' if is_user else '#444654'
            color = 'white'
            
            html += f'''
            <div style="display: flex; justify-content: {align}; margin-bottom: 10px;">
                <div style="background-color: {bg}; color: {color}; padding: 10px; border-radius: 10px; max-width: 80%;">
                    <strong>{msg.role.title()}:</strong> <br>
                    {msg.content}
                </div>
            </div>
            '''
        html += '</div>'
        return format_html(html)
    chat_visual.short_description = "Chat History"

@admin.register(Message)
class MessageAdmin(admin.ModelAdmin):
    list_display = ('id', 'conversation', 'role', 'short_content', 'created_at')
    list_filter = ('role', 'created_at')
    search_fields = ('content', 'conversation__title', 'conversation__user__username')
    
    def short_content(self, obj):
        return obj.content[:50] + '...' if len(obj.content) > 50 else obj.content
    short_content.short_description = 'Content'

@admin.register(UserLoginLog)
class UserLoginLogAdmin(admin.ModelAdmin):
    list_display = ('user', 'ip_address', 'timestamp')
    list_filter = ('timestamp',)
    search_fields = ('user__username', 'ip_address')
    readonly_fields = ('user', 'ip_address', 'user_agent', 'timestamp')
