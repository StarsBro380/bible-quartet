function sendAdminChatMessage(roomCode) {
    const input = document.getElementById('admin-chat-input');
    const text = input.value.trim();
    if (!text) return;
    input.value = '';
    
    const messages = document.getElementById('admin-chat-messages');
    const msgDiv = document.createElement('div');
    msgDiv.className = 'chat-message sent';
    msgDiv.innerHTML = `
        ${text}
        <div class="msg-time">${new Date().toLocaleTimeString()}</div>
    `;
    messages.appendChild(msgDiv);
    messages.scrollTop = messages.scrollHeight;
    
    // Отправляем на сервер
    fetch(API + '/chat/reply', {
        method: 'POST',
        headers: {'Content-Type': 'application/json'},
        body: JSON.stringify({
            adminId: playerId,
            roomCode: roomCode,
            message: text
        })
    })
    .then(res => res.json())
    .then(d => {
        if (!d.ok) {
            toast('Ошибка отправки: ' + d.error, 'error');
        }
    })
    .catch(() => toast('Ошибка соединения', 'error'));
}
