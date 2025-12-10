document.addEventListener('DOMContentLoaded', () => {
    const chatForm = document.getElementById('chat-form');
    const userInput = document.getElementById('user-input');
    const chatArea = document.getElementById('chat-area');
    const sendBtn = document.getElementById('send-btn');
    const newChatBtn = document.getElementById('new-chat-btn');
    const historyList = document.getElementById('history-list');
    const currentChatTitle = document.getElementById('current-chat-title');
    const modelSelect = document.getElementById('model-select');

    // Mobile UI elements
    const mobileMenuBtn = document.getElementById('mobile-menu-btn');
    const sidebar = document.getElementById('sidebar');
    const sidebarOverlay = document.getElementById('sidebar-overlay');

    let currentConversationId = null;

    // Fetch available models
    fetchModels();

    async function fetchModels() {
        try {
            const response = await fetch('/api/models/');
            const data = await response.json();
            if (data.models && data.models.length > 0) {
                modelSelect.innerHTML = '';
                data.models.forEach(model => {
                    const option = document.createElement('option');
                    option.value = model;
                    option.text = model;
                    if (model.includes('llama3.1:8b')) option.selected = true;
                    modelSelect.appendChild(option);
                });
            }
        } catch (err) {
            console.error("Failed to fetch models", err);
        }
    }

    // Toggle Sidebar
    if (mobileMenuBtn) {
        mobileMenuBtn.addEventListener('click', () => {
            sidebar.classList.toggle('open');
            sidebarOverlay.classList.toggle('open');
        });
    }

    // Close Sidebar on Overlay Click
    if (sidebarOverlay) {
        sidebarOverlay.addEventListener('click', () => {
            sidebar.classList.remove('open');
            sidebarOverlay.classList.remove('open');
        });
    }

    // Close Sidebar when selecting a chat (on mobile)
    function closeSidebarOnMobile() {
        if (window.innerWidth <= 768) {
            sidebar.classList.remove('open');
            sidebarOverlay.classList.remove('open');
        }
    }

    // Handle New Chat
    newChatBtn.addEventListener('click', () => {
        currentConversationId = null;
        currentChatTitle.innerText = "New Chat";
        chatArea.innerHTML = `
            <div class="message bot-message">
                <div class="message-content">
                    Hello! I'm running on Llama 3.1. Ask me anything.
                </div>
            </div>
        `;
        // Remove active class from history items
        document.querySelectorAll('.history-item').forEach(item => item.classList.remove('active'));
        closeSidebarOnMobile();
    });

    // Handle History Item Click
    historyList.addEventListener('click', async (e) => {
        const item = e.target.closest('.history-item');
        if (!item) return;

        const conversationId = item.dataset.id;
        if (conversationId == currentConversationId) return;

        // Set active
        document.querySelectorAll('.history-item').forEach(i => i.classList.remove('active'));
        item.classList.add('active');

        currentConversationId = conversationId;
        currentChatTitle.innerText = item.querySelector('.chat-title').innerText;

        // Load messages
        await loadMessages(conversationId);
        closeSidebarOnMobile();
    });

    async function loadMessages(conversationId) {
        chatArea.innerHTML = ''; // Clear chat
        try {
            const response = await fetch(`/api/messages/${conversationId}/`);
            const data = await response.json();

            if (data.messages) {
                data.messages.forEach(msg => {
                    appendMessage(msg.content, msg.role);
                });
            }
        } catch (err) {
            console.error("Failed to load messages", err);
        }
    }

    chatForm.addEventListener('submit', async (e) => {
        e.preventDefault();
        const prompt = userInput.value.trim();
        if (!prompt) return;

        // Add user message
        appendMessage(prompt, 'user');
        userInput.value = '';
        userInput.disabled = true;
        sendBtn.disabled = true;

        // Create bot message container immediately
        const botMsgId = appendMessage('', 'bot');
        const botMsgContent = document.querySelector(`#${botMsgId} .message-content`);
        botMsgContent.innerHTML = '<span class="typing-indicator"><span></span><span></span><span></span></span>';

        try {
            const response = await fetch('/api/chat/', {
                method: 'POST',
                headers: {
                    'Content-Type': 'application/json',
                },
                body: JSON.stringify({
                    prompt: prompt,
                    conversation_id: currentConversationId,
                    model: modelSelect.value // Send selected model
                })
            });

            if (!response.ok) {
                botMsgContent.innerHTML = ''; // Clear typing indicator
                if (response.status === 409) {
                    botMsgContent.innerText = "⚠️ Server is busy (Queue Full). Please try again in a moment.";
                    botMsgContent.classList.add('error-message');
                } else {
                    const data = await response.json();
                    botMsgContent.innerText = `⚠️ Error: ${data.error || 'Something went wrong'}`;
                    botMsgContent.classList.add('error-message');
                }
                return;
            }

            // Clear typing indicator before streaming
            botMsgContent.innerHTML = '';

            const reader = response.body.getReader();
            const decoder = new TextDecoder();
            let buffer = '';

            while (true) {
                const { done, value } = await reader.read();
                if (done) break;

                buffer += decoder.decode(value, { stream: true });
                const lines = buffer.split('\n');
                buffer = lines.pop(); // Keep the last partial line in buffer

                for (const line of lines) {
                    if (!line.trim()) continue;
                    try {
                        const data = JSON.parse(line);

                        if (data.conversation_id) {
                            // If it was a new chat, update ID and sidebar
                            if (!currentConversationId) {
                                currentConversationId = data.conversation_id;
                                currentChatTitle.innerText = data.title;
                                addHistoryItem(data.conversation_id, data.title);
                            }
                        } else if (data.content) {
                            // Accumulate content
                            if (!botMsgContent.dataset.markdown) {
                                botMsgContent.dataset.markdown = '';
                            }
                            botMsgContent.dataset.markdown += data.content;

                            // Render Markdown if available, else text
                            if (typeof marked !== 'undefined') {
                                try {
                                    botMsgContent.innerHTML = marked.parse(botMsgContent.dataset.markdown);
                                    // Highlight code blocks
                                    if (typeof hljs !== 'undefined') {
                                        botMsgContent.querySelectorAll('pre code').forEach((block) => {
                                            hljs.highlightElement(block);
                                        });
                                    }
                                } catch (parseErr) {
                                    console.error("Markdown parse error:", parseErr);
                                    botMsgContent.innerText = botMsgContent.dataset.markdown;
                                }
                            } else {
                                botMsgContent.innerText = botMsgContent.dataset.markdown;
                            }

                            chatArea.scrollTop = chatArea.scrollHeight;
                        } else if (data.error) {
                            botMsgContent.innerText += `\n[Error: ${data.error}]`;
                            botMsgContent.classList.add('error-message');
                        }
                    } catch (e) {
                        console.error("Error parsing JSON chunk", e);
                    }
                }
            }

        } catch (err) {
            const botMsgContent = document.querySelector(`#${botMsgId} .message-content`);
            if (botMsgContent) {
                botMsgContent.innerHTML = "⚠️ Network Error. Please check your connection.";
                botMsgContent.classList.add('error-message');
            }
            console.error(err);
        } finally {
            userInput.disabled = false;
            sendBtn.disabled = false;
            userInput.focus();
        }
    });

    function appendMessage(text, sender, isError = false) {
        const msgDiv = document.createElement('div');
        msgDiv.classList.add('message', `${sender}-message`);

        const contentDiv = document.createElement('div');
        contentDiv.classList.add('message-content');
        if (isError) {
            contentDiv.classList.add('error-message');
            contentDiv.innerText = text;
        } else if (sender === 'bot') {
            // For bot, we might render HTML (Markdown)
            // But initially, just set text if it's not streaming yet?
            // Actually, for streaming, we update innerText/innerHTML later.
            // If it's a full response (e.g. from history), render it.
            contentDiv.innerHTML = marked.parse(text);
            // Highlight code blocks
            contentDiv.querySelectorAll('pre code').forEach((block) => {
                hljs.highlightElement(block);
            });
        } else {
            contentDiv.innerText = text;
        }

        msgDiv.appendChild(contentDiv);
        chatArea.appendChild(msgDiv);
        chatArea.scrollTop = chatArea.scrollHeight;
        return msgDiv.id = 'msg-' + Date.now();
    }

    function appendLoading() {
        const msgDiv = document.createElement('div');
        msgDiv.classList.add('message', 'bot-message');
        msgDiv.id = 'loading-' + Date.now();

        const contentDiv = document.createElement('div');
        contentDiv.classList.add('message-content', 'typing-indicator');
        contentDiv.innerHTML = '<span></span><span></span><span></span>';

        msgDiv.appendChild(contentDiv);
        chatArea.appendChild(msgDiv);
        chatArea.scrollTop = chatArea.scrollHeight;
        return msgDiv.id;
    }

    function removeMessage(id) {
        const el = document.getElementById(id);
        if (el) el.remove();
    }

    function addHistoryItem(id, title) {
        const div = document.createElement('div');
        div.className = 'history-item active';
        div.dataset.id = id;
        div.innerHTML = `<span class="chat-title">${title}</span>`;

        // Prepend to list
        historyList.insertBefore(div, historyList.firstChild);
    }
});
