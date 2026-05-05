import os
import json
import random
import string
from datetime import datetime
from flask import Flask, request, jsonify
from flask_cors import CORS

app = Flask(__name__)
CORS(app)

# Отключаем кэширование
@app.after_request
def after_request(response):
    response.headers.add('Cache-Control', 'no-cache, no-store, must-revalidate')
    return response

rooms = {}
# Хранилище сообщений для чата с поддержкой
chat_messages = []
chat_id_counter = 0
CHAT_FILE = 'chat_messages.json'  # Файл для хранения сообщений

ADMIN_IDS = [39444699]  # ID администратора

# ===== ЗАГРУЗКА СООБЩЕНИЙ ИЗ ФАЙЛА =====
def load_chat_messages():
    global chat_messages, chat_id_counter
    try:
        if os.path.exists(CHAT_FILE):
            with open(CHAT_FILE, 'r', encoding='utf-8') as f:
                data = json.load(f)
                chat_messages = data.get('messages', [])
                chat_id_counter = data.get('counter', 0)
                print(f"[CHAT] Загружено {len(chat_messages)} сообщений из файла")
        else:
            chat_messages = []
            chat_id_counter = 0
            print("[CHAT] Файл сообщений не найден, создаём новый")
    except Exception as e:
        print(f"[CHAT] Ошибка загрузки сообщений: {e}")
        chat_messages = []
        chat_id_counter = 0

# ===== СОХРАНЕНИЕ СООБЩЕНИЙ В ФАЙЛ =====
def save_chat_messages():
    try:
        with open(CHAT_FILE, 'w', encoding='utf-8') as f:
            json.dump({'messages': chat_messages, 'counter': chat_id_counter}, f, ensure_ascii=False, indent=2)
        print(f"[CHAT] Сохранено {len(chat_messages)} сообщений в файл")
    except Exception as e:
        print(f"[CHAT] Ошибка сохранения сообщений: {e}")

# Загружаем сообщения при старте
load_chat_messages()

def generate_code():
    return ''.join(random.choices(string.ascii_uppercase + string.digits, k=6))

def create_deck():
    with open('data.json', 'r', encoding='utf-8') as f:
        data = json.load(f)
    deck = []
    for q in data:
        for c in q['cards']:
            deck.append({'category': q['name'], 'cardName': c['name']})
    random.shuffle(deck)
    return deck, data

@app.route('/')
def home():
    return 'OK'

@app.route('/create', methods=['POST'])
def create_room():
    data = request.get_json()
    player_name = data.get('name', 'Игрок')
    cards_count = int(data.get('cards', 10))
    player_id = int(data.get('playerId', 0))
    
    code = generate_code()
    while code in rooms:
        code = generate_code()
    
    deck, categories = create_deck()
    
    room = {
        'code': code,
        'players': [{
            'id': 0,
            'name': player_name,
            'hand': deck[:cards_count],
            'quartets': []
        }],
        'deck': deck[cards_count:],
        'categories': categories,
        'currentPlayer': 0,
        'status': 'lobby',
        'maxPlayers': 4,
        'cardsPerPlayer': cards_count,
        'history': [],
        'ownerId': 0
    }
    
    rooms[code] = room
    print(f"[CREATE] Комната {code}, игрок 0: {player_name}")
    return jsonify({'ok': True, 'code': code, 'playerId': 0})

@app.route('/start', methods=['POST'])
def start_game():
    data = request.get_json()
    code = data.get('code', '').upper()
    player_id = int(data.get('playerId', -1))
    
    if code not in rooms:
        return jsonify({'ok': False, 'error': 'Комната не найдена'}), 404
    
    room = rooms[code]
    
    if room['ownerId'] != player_id:
        return jsonify({'ok': False, 'error': 'Только создатель может начать игру'}), 400
    
    if len(room['players']) < 2:
        return jsonify({'ok': False, 'error': 'Нужно минимум 2 игрока'}), 400
    
    room['status'] = 'playing'
    room['currentPlayer'] = 0
    room['history'].append({
        'time': datetime.now().strftime('%H:%M'),
        'text': '🎮 Игра началась!',
        'type': 'system'
    })
    
    print(f"[START] Игра в комнате {code} началась! Игроков: {len(room['players'])}")
    return jsonify({'ok': True})

@app.route('/join', methods=['POST'])
def join_room():
    data = request.get_json()
    code = data.get('code', '').upper()
    player_name = data.get('name', 'Игрок')
    player_id = int(data.get('playerId', 0))
    
    if code not in rooms:
        return jsonify({'ok': False, 'error': 'Комната не найдена'}), 404
    
    room = rooms[code]
    
    if room['status'] != 'lobby':
        return jsonify({'ok': False, 'error': 'Игра уже началась'}), 400
    
    if len(room['players']) >= room['maxPlayers']:
        return jsonify({'ok': False, 'error': 'Комната заполнена'}), 400
    
    new_id = len(room['players'])
    cards = room['deck'][:room['cardsPerPlayer']]
    room['deck'] = room['deck'][room['cardsPerPlayer']:]
    
    room['players'].append({
        'id': new_id,
        'name': player_name,
        'hand': cards,
        'quartets': []
    })
    
    room['history'].append({
        'time': datetime.now().strftime('%H:%M'),
        'text': f'👤 {player_name} присоединился к игре',
        'type': 'system'
    })
    
    print(f"[JOIN] Комната {code}, новый игрок {new_id}: {player_name}")
    return jsonify({'ok': True, 'playerId': int(new_id)})

@app.route('/state/<code>/<int:player_id>', methods=['GET'])
def get_state(code, player_id):
    if code not in rooms:
        return jsonify({'ok': False, 'error': 'Комната не найдена'}), 404
    
    room = rooms[code]
    
    player = None
    for p in room['players']:
        if p['id'] == player_id:
            player = p
            break
    
    if not player:
        return jsonify({'ok': False, 'error': f'Игрок {player_id} не найден'}), 404
    
    players_info = []
    for p in room['players']:
        info = {
            'id': int(p['id']),
            'name': p['name'],
            'quartets': p['quartets'],
            'handCount': int(len(p['hand']))
        }
        if p['id'] == player_id:
            info['hand'] = p['hand']
        players_info.append(info)
    
    return jsonify({
        'ok': True,
        'code': code,
        'playerId': int(player_id),
        'players': players_info,
        'bankCount': int(len(room['deck'])),
        'currentPlayer': int(room['currentPlayer']),
        'status': room['status'],
        'categories': room['categories'],
        'history': room['history'][-30:],
        'ownerId': int(room['ownerId'])
    })

@app.route('/request', methods=['POST'])
def request_card():
    data = request.get_json()
    code = data.get('code', '').upper()
    from_player = int(data.get('fromPlayer', -1))
    to_player = int(data.get('toPlayer', -1))
    category = data.get('category', '')
    card_name = data.get('cardName', '')
    
    if code not in rooms:
        return jsonify({'ok': False, 'error': 'Комната не найдена'}), 404
    
    room = rooms[code]
    
    if from_player >= len(room['players']) or from_player < 0:
        return jsonify({'ok': False, 'error': 'Игрок не найден'}), 400
    
    if int(room['currentPlayer']) != from_player:
        return jsonify({'ok': False, 'error': f'Не ваш ход. Сейчас ходит игрок {room["currentPlayer"]}'}), 400
    
    requester = room['players'][from_player]
    has_category = any(c['category'] == category for c in requester['hand'])
    if not has_category:
        return jsonify({'ok': False, 'error': 'У вас нет карт этой категории'}), 400
    
    if to_player >= len(room['players']) or to_player < 0:
        return jsonify({'ok': False, 'error': 'Целевой игрок не найден'}), 400
    
    target = room['players'][to_player]
    card_index = None
    for i, c in enumerate(target['hand']):
        if c['category'] == category and c['cardName'] == card_name:
            card_index = i
            break
    
    from_name = requester['name']
    to_name = target['name']
    
    if card_index is not None:
        card = target['hand'].pop(card_index)
        requester['hand'].append(card)
        
        check_quartets(room, from_player)
        check_quartets(room, to_player)
        
        room['currentPlayer'] = int(from_player)
        
        room['history'].append({
            'time': datetime.now().strftime('%H:%M'),
            'text': f'{from_name} спросил(а) у {to_name}: «{card_name}» ({category}) — ✅ Есть!',
            'type': 'ok'
        })
        
        return jsonify({
            'ok': True, 'found': True, 'card': card,
            'nextPlayer': int(from_player)
        })
    else:
        drawn = None
        if room['deck']:
            drawn = room['deck'].pop()
            requester['hand'].append(drawn)
            check_quartets(room, from_player)
        
        next_player = (from_player + 1) % len(room['players'])
        room['currentPlayer'] = int(next_player)
        
        if drawn:
            room['history'].append({
                'time': datetime.now().strftime('%H:%M'),
                'text': f'{from_name} спросил(а) у {to_name}: «{card_name}» ({category}) — ❌ Нет. Взял из запаса.',
                'type': 'no'
            })
        else:
            room['history'].append({
                'time': datetime.now().strftime('%H:%M'),
                'text': f'{from_name} спросил(а) у {to_name}: «{card_name}» ({category}) — ❌ Нет. Запас пуст.',
                'type': 'no'
            })
        
        return jsonify({
            'ok': True, 'found': False, 'drawn': drawn,
            'nextPlayer': int(next_player)
        })

def check_quartets(room, player_id):
    p = room['players'][player_id]
    groups = {}
    for c in p['hand']:
        if c['category'] not in groups:
            groups[c['category']] = []
        groups[c['category']].append(c)
    
    for cat, cards in groups.items():
        if len(cards) == 4:
            p['quartets'].append(cat)
            p['hand'] = [c for c in p['hand'] if c['category'] != cat]
            room['history'].append({
                'time': datetime.now().strftime('%H:%M'),
                'text': f'🏆 {p["name"]} собрал(а) квартет «{cat}»!',
                'type': 'ok'
            })

# ===== ЧАТ С ПОДДЕРЖКОЙ =====
@app.route('/chat/send', methods=['POST'])
def send_chat_message():
    global chat_id_counter
    data = request.get_json()
    code = data.get('code', '')
    player_id = int(data.get('playerId', -1))
    name = data.get('name', 'Игрок')
    message = data.get('message', '')
    
    if not message:
        return jsonify({'ok': False, 'error': 'Сообщение не может быть пустым'}), 400
    
    # Уникальный ключ чата: ID игрока
    chat_key = str(player_id)
    
    chat_id_counter += 1
    chat_messages.append({
        'id': chat_id_counter,
        'from_player': player_id,
        'from_name': name,
        'to_player': None,
        'room': chat_key,
        'message': message,
        'time': datetime.now().strftime('%H:%M'),
        'read': False
    })
    
    # Сохраняем в файл
    save_chat_messages()
    
    print(f"[CHAT] Сообщение от {name} (ID {player_id}): {message}")
    return jsonify({'ok': True, 'message_id': chat_id_counter})

@app.route('/chat/list/<int:admin_id>', methods=['GET'])
def get_chat_messages(admin_id):
    if admin_id not in ADMIN_IDS:
        return jsonify({'ok': False, 'error': 'Доступ только для администраторов'}), 403
    
    # Группируем сообщения по чатам (ключ = ID игрока)
    chats = {}
    for msg in chat_messages:
        key = msg['room']
        if key not in chats:
            chats[key] = []
        chats[key].append(msg)
    
    result = []
    for chat_key, msgs in chats.items():
        last_msg = msgs[-1]
        # Имя игрока из первого сообщения
        player_name = msgs[0]['from_name']
        result.append({
            'roomCode': chat_key,
            'name': player_name,
            'lastMsg': last_msg['message'],
            'time': last_msg['time'],
            'unread': sum(1 for m in msgs if not m['read'] and m['from_player'] != admin_id)
        })
    
    return jsonify({'ok': True, 'chats': result})

@app.route('/chat/messages/<int:player_id>/<chat_key>', methods=['GET'])
def get_room_chat_messages(player_id, chat_key):
    # Разрешаем доступ, если player_id совпадает с chat_key (свои сообщения)
    # ИЛИ если это админ
    if player_id != int(chat_key) and player_id not in ADMIN_IDS:
        return jsonify({'ok': False, 'error': 'Доступ запрещён'}), 403
    
    room_messages = [m for m in chat_messages if m['room'] == chat_key]
    
    # Помечаем как прочитанные
    for m in chat_messages:
        if m['room'] == chat_key:
            m['read'] = True
    save_chat_messages()
    
    return jsonify({'ok': True, 'messages': room_messages})

@app.route('/chat/reply', methods=['POST'])
def reply_to_chat():
    global chat_id_counter
    data = request.get_json()
    admin_id = int(data.get('adminId', -1))
    chat_key = data.get('roomCode', '')
    message = data.get('message', '')
    
    if admin_id not in ADMIN_IDS:
        return jsonify({'ok': False, 'error': 'Доступ только для администраторов'}), 403
    
    if not message:
        return jsonify({'ok': False, 'error': 'Сообщение не может быть пустым'}), 400
    
    chat_id_counter += 1
    chat_messages.append({
        'id': chat_id_counter,
        'from_player': admin_id,
        'from_name': 'Администратор',
        'to_player': None,
        'room': chat_key,
        'message': message,
        'time': datetime.now().strftime('%H:%M'),
        'read': False
    })
    save_chat_messages()
    
    print(f"[CHAT] Ответ админа в чат {chat_key}: {message}")
    return jsonify({'ok': True, 'message_id': chat_id_counter})

# ===== ДЛЯ АДМИНА: НАБЛЮДЕНИЕ =====
@app.route('/observe/<code>/<int:admin_id>', methods=['POST'])
def observe_game(code, admin_id):
    if admin_id not in ADMIN_IDS:
        return jsonify({'ok': False, 'error': 'Доступ только для администраторов'}), 403
    
    if code not in rooms:
        return jsonify({'ok': False, 'error': 'Игра не найдена'}), 404
    
    room = rooms[code]
    observer_id = max([p['id'] for p in room['players']] + [-1]) + 1
    room['players'].append({
        'id': observer_id,
        'name': 'Наблюдатель',
        'hand': [],
        'quartets': [],
        'is_observer': True
    })
    
    return jsonify({'ok': True, 'roomCode': code, 'playerId': observer_id})

# ===== ДЛЯ АДМИНА: ЗАВЕРШЁННЫЕ ИГРЫ =====
@app.route('/admin/games/<int:admin_id>', methods=['GET'])
def admin_games(admin_id):
    if admin_id not in ADMIN_IDS:
        return jsonify({'ok': False, 'error': 'Доступ только для администраторов'}), 403
    
    result = []
    for code, room in rooms.items():
        # Фильтруем только реальных игроков (не наблюдателей)
        players_info = []
        for p in room['players']:
            if p.get('is_observer', False):
                continue
            # Если игра не началась, показываем 0 квартетов и 0 карт
            if room['status'] == 'lobby':
                players_info.append({
                    'id': p['id'],
                    'name': p['name'],
                    'quartets': 0,
                    'handCount': 0
                })
            else:
                players_info.append({
                    'id': p['id'],
                    'name': p['name'],
                    'quartets': len(p['quartets']),
                    'handCount': len(p['hand'])
                })
        
        # Добавляем только если есть игроки
        if players_info:
            result.append({
                'code': code,
                'status': room['status'],
                'players': players_info,
                'ownerId': room['ownerId']
            })
    
    return jsonify({'ok': True, 'games': result})

# ===== ВЫХОД ИЗ ИГРЫ =====
@app.route('/leave', methods=['POST'])
def leave_game():
    data = request.get_json()
    code = data.get('code', '').upper()
    player_id = int(data.get('playerId', -1))
    
    if code not in rooms:
        return jsonify({'ok': False, 'error': 'Комната не найдена'}), 404
    
    room = rooms[code]
    
    # Удаляем игрока
    old_count = len(room['players'])
    room['players'] = [p for p in room['players'] if p['id'] != player_id]
    new_count = len(room['players'])
    
    print(f"[LEAVE] Игрок {player_id} вышел из комнаты {code}. Было {old_count}, стало {new_count}")
    
    # Если игроков нет — удаляем комнату
    if new_count == 0:
        del rooms[code]
        print(f"[LEAVE] Комната {code} удалена (все игроки вышли)")
    else:
        # Если ушёл создатель — передаём создателя следующему
        if room['ownerId'] == player_id:
            room['ownerId'] = room['players'][0]['id']
            print(f"[LEAVE] Создатель вышел. Новый создатель: {room['ownerId']}")
    
    return jsonify({'ok': True})

# ===== ЗАВЕРШЕНИЕ ИГРЫ =====
@app.route('/end_game', methods=['POST'])
def end_game():
    data = request.get_json()
    code = data.get('code', '').upper()
    player_id = int(data.get('playerId', -1))
    
    if code not in rooms:
        return jsonify({'ok': False, 'error': 'Комната не найдена'}), 404
    
    room = rooms[code]
    
    if room['ownerId'] != player_id:
        return jsonify({'ok': False, 'error': 'Только создатель может завершить игру'}), 400
    
    room['status'] = 'finished'
    room['history'].append({
        'time': datetime.now().strftime('%H:%M'),
        'text': '🚫 Игра завершена создателем',
        'type': 'system'
    })
    
    print(f"[END] Игра в комнате {code} завершена создателем {player_id}")
    return jsonify({'ok': True})

# ===== ПЕРЕИМЕНОВАНИЕ =====
@app.route('/rename', methods=['POST'])
def rename_player():
    data = request.get_json()
    code = data.get('code', '').upper()
    player_id = int(data.get('playerId', -1))
    new_name = data.get('name', 'Игрок')
    
    if code not in rooms:
        return jsonify({'ok': False, 'error': 'Комната не найдена'}), 404
    
    room = rooms[code]
    for p in room['players']:
        if p['id'] == player_id:
            p['name'] = new_name
            return jsonify({'ok': True})
    
    return jsonify({'ok': False, 'error': 'Игрок не найден'}), 404

# ===== ОБРАТНАЯ СВЯЗЬ =====
@app.route('/feedback', methods=['POST'])
def feedback():
    data = request.get_json()
    code = data.get('code', '')
    player_id = int(data.get('playerId', -1))
    name = data.get('name', 'Игрок')
    message = data.get('message', '')
    
    if not message:
        return jsonify({'ok': False, 'error': 'Сообщение не может быть пустым'}), 400
    
    print(f"[FEEDBACK] {name} (ID {player_id}, комната {code}): {message}")
    return jsonify({'ok': True})

# ===== СПИСОК ОБРАТНОЙ СВЯЗИ =====
@app.route('/feedback/list/<int:admin_id>', methods=['GET'])
def feedback_list(admin_id):
    if admin_id not in ADMIN_IDS:
        return jsonify({'ok': False, 'error': 'Доступ только для администраторов'}), 403
    
    return jsonify({'ok': True, 'feedback': []})

if __name__ == '__main__':
    # Очищаем комнаты при старте
    rooms.clear()
    print("[START] Сервер запущен, данные очищены")
    app.run(host='0.0.0.0', port=int(os.environ.get('PORT', 5000)))
