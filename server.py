import os
import json
import random
import string
from datetime import datetime
from flask import Flask, request, jsonify, send_from_directory
from flask_cors import CORS
from flask_socketio import SocketIO, emit, join_room, leave_room

app = Flask(__name__, static_folder='.', static_url_path='')
CORS(app)

# ⚡ ИСПРАВЛЕНИЕ: убрали async_mode='eventlet'
socketio = SocketIO(app, cors_allowed_origins="*")

# Отключаем кэширование
@app.after_request
def after_request(response):
    response.headers.add('Cache-Control', 'no-cache, no-store, must-revalidate')
    return response

rooms = {}

ADMIN_IDS = [39444699]

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
    return send_from_directory('.', 'index.html')

@app.route('/health', methods=['GET'])
def health():
    return jsonify({'status': 'ok'})

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
        'maxPlayers': 21,
        'cardsPerPlayer': cards_count,
        'history': [],
        'ownerId': 0,
        'missedTurns': {}
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
    
    socketio.emit('game_started', {'code': code}, room=code)
    
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
    
    socketio.emit('player_joined', {
        'code': code,
        'player': {'id': new_id, 'name': player_name}
    }, room=code)
    
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
        'ownerId': int(room['ownerId']),
        'missedTurns': room.get('missedTurns', {})
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
    
    room['missedTurns'][str(from_player)] = 0
    
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
        
        socketio.emit('game_update', {'code': code}, room=code)
        
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
        
        socketio.emit('game_update', {'code': code}, room=code)
        
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

@app.route('/exclude', methods=['POST'])
def exclude_player():
    data = request.get_json()
    code = data.get('code', '').upper()
    player_id = int(data.get('playerId', -1))
    
    if code not in rooms:
        return jsonify({'ok': False, 'error': 'Комната не найдена'}), 404
    
    room = rooms[code]
    
    player = None
    for p in room['players']:
        if p['id'] == player_id:
            player = p
            break
    
    if not player:
        return jsonify({'ok': False, 'error': 'Игрок не найден'}), 404
    
    room['deck'].extend(player['hand'])
    player['hand'] = []
    
    room['players'] = [p for p in room['players'] if p['id'] != player_id]
    
    if len(room['players']) == 0:
        del rooms[code]
        print(f"[EXCLUDE] Комната {code} удалена (все игроки вышли)")
        return jsonify({'ok': True})
    
    if room['ownerId'] == player_id:
        room['ownerId'] = random.choice(room['players'])['id']
        print(f"[EXCLUDE] Создатель исключён. Новый создатель: {room['ownerId']}")
    
    if str(player_id) in room['missedTurns']:
        del room['missedTurns'][str(player_id)]
    
    if room['currentPlayer'] == player_id:
        room['currentPlayer'] = (player_id + 1) % len(room['players'])
    
    room['history'].append({
        'time': datetime.now().strftime('%H:%M'),
        'text': f'🚫 Игрок {player["name"]} был исключён из игры.',
        'type': 'system'
    })
    
    socketio.emit('game_update', {'code': code}, room=code)
    
    print(f"[EXCLUDE] Игрок {player['name']} (ID {player_id}) исключён из комнаты {code}")
    return jsonify({'ok': True})

@app.route('/leave', methods=['POST'])
def leave_game():
    data = request.get_json()
    code = data.get('code', '').upper()
    player_id = int(data.get('playerId', -1))
    
    if code not in rooms:
        return jsonify({'ok': False, 'error': 'Комната не найдена'}), 404
    
    room = rooms[code]
    
    player = None
    for p in room['players']:
        if p['id'] == player_id:
            player = p
            break
    
    if not player:
        return jsonify({'ok': False, 'error': 'Игрок не найден'}), 404
    
    room['deck'].extend(player['hand'])
    player['hand'] = []
    
    room['players'] = [p for p in room['players'] if p['id'] != player_id]
    
    if len(room['players']) == 0:
        del rooms[code]
        print(f"[LEAVE] Комната {code} удалена (все игроки вышли)")
        return jsonify({'ok': True})
    
    if room['ownerId'] == player_id:
        room['ownerId'] = random.choice(room['players'])['id']
        print(f"[LEAVE] Создатель вышел. Новый создатель: {room['ownerId']}")
    
    if str(player_id) in room['missedTurns']:
        del room['missedTurns'][str(player_id)]
    
    if room['currentPlayer'] == player_id:
        room['currentPlayer'] = (player_id + 1) % len(room['players'])
    
    room['history'].append({
        'time': datetime.now().strftime('%H:%M'),
        'text': f'👋 Игрок {player["name"]} покинул игру.',
        'type': 'system'
    })
    
    socketio.emit('game_update', {'code': code}, room=code)
    
    print(f"[LEAVE] Игрок {player['name']} (ID {player_id}) вышел из комнаты {code}")
    return jsonify({'ok': True})

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
    
    socketio.emit('game_ended', {'code': code}, room=code)
    
    print(f"[END] Игра в комнате {code} завершена создателем {player_id}")
    return jsonify({'ok': True})

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

# ===== SOCKETIO СОБЫТИЯ =====

@socketio.on('connect')
def handle_connect():
    print(f'Клиент подключился: {request.sid}')

@socketio.on('disconnect')
def handle_disconnect():
    print(f'Клиент отключился: {request.sid}')

@socketio.on('join_room')
def handle_join_room(data):
    code = data.get('code')
    if code and code in rooms:
        join_room(code)
        print(f'Клиент {request.sid} присоединился к комнате {code}')

@socketio.on('leave_room')
def handle_leave_room(data):
    code = data.get('code')
    if code:
        leave_room(code)
        print(f'Клиент {request.sid} покинул комнату {code}')

if __name__ == '__main__':
    socketio.run(app, host='0.0.0.0', port=int(os.environ.get('PORT', 5000)), debug=True)
