function showMenu() {
    clearInterval(pollTimer);
    document.getElementById('bottom-panel').classList.add('hidden');
    
    // ✅ Загружаем ID из Telegram
    if (tg && tg.initDataUnsafe && tg.initDataUnsafe.user) {
        playerId = parseInt(tg.initDataUnsafe.user.id);
    }
    
    const isAdmin = ADMIN_IDS.includes(parseInt(playerId));
    document.getElementById('app').innerHTML = `
        <div class="menu-container">
            <div class="menu-decoration"></div>
            <div class="menu-decoration-2"></div>
            <div class="logo-container" style="position:relative;z-index:1;">
                <span class="logo-icon">📖</span>
                <div class="logo-text-group">
                    <span class="logo-text-main">Библейский квартет</span>
                    <span class="logo-text-sub">Bible Quartet</span>
                </div>
            </div>
            <div style="text-align:center;color:var(--text2);font-size:12px;line-height:1.5;max-width:300px;margin:0 auto;position:relative;z-index:1;">
                <p>Здесь вы можете играть в Библейский квартет онлайн с другими людьми.</p>
                <p style="margin-top:4px;opacity:0.7;">Если вы заметили ошибки или хотите что-то добавить, напишите в поддержку.</p>
            </div>
            <div class="name-section" style="width:100%;position:relative;z-index:1;">
                <label style="text-align:center;display:block;font-size:13px;color:var(--text2);font-weight:500;">Ваше имя</label>
                <input class="input input-name" id="player-name" value="${playerName}" maxlength="20" style="text-align:center;"
                       onblur="saveNameFromMenu()" onkeydown="if(event.key==='Enter') saveNameFromMenu()">
            </div>
            <button class="btn btn-primary" style="position:relative;z-index:1;" onclick="saveNameAndCreate()">
                <span class="btn-icon">🎮</span> Создать игру
            </button>
            <button class="btn btn-secondary" style="position:relative;z-index:1;" onclick="saveNameAndJoin()">
                <span class="btn-icon join-icon">🔗</span> Присоединиться
            </button>
            <div style="display:flex;gap:8px;justify-content:center;flex-wrap:wrap;position:relative;z-index:1;margin-top:8px;">
                <button class="btn btn-secondary" style="max-width:300px;padding:8px 16px;font-size:12px;flex:1;" onclick="openFeedback()">
                    💬 Написать в поддержку
                </button>
                <button class="btn btn-secondary" style="max-width:300px;padding:8px 16px;font-size:12px;flex:1;" onclick="openRules()">
                    📜 Правила
                </button>
                ${isAdmin ? `
                <button class="btn btn-secondary" style="max-width:300px;padding:8px 16px;font-size:12px;flex:1;background:rgba(123,75,42,0.15);border-color:var(--accent);" onclick="openAdminPanel()">
                    📊 Игры
                </button>
                ` : ''}
            </div>
        </div>
    `;
    window.saveNameFromMenu = function() {
        const newName = document.getElementById('player-name').value.trim() || 'Игрок';
        playerName = newName;
    };
}
