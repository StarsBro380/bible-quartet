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
ADMIN_IDS = [39444699]

FEEDBACK_FILE = 'feedback.json'

def load_feedback():
    if os.path.exists(FEEDBACK_FILE):
        try:
            with open(FEEDBACK_FILE, 'r', encoding='utf-8') as f:
                return json.load(f)
        except:
            return []
    return []

def save_feedback(feedback_list):
    with open(FEEDBACK_FILE, 'w', encoding='utf-8') as f:
        json.dump(feedback_list, f, ensure_ascii=False, indent=2)

all_feedback = load_feedback()

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
            'quartets': [],
            'missed_turns': 0
        }],
        'deck': deck[cards_count:],
        'categories': categories,
        'currentPlayer': 0,
        'status': 'lobby',
        'maxPlayers': 4,
        'cardsPerPlayer': cards_count,
        'history': [],
        'ownerId': 0,
        'observers': [],
        'last_move_time': datetime.now().timestamp()
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
    room['last_move_time'] = datetime.now().timestamp()
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
        'quartets': [],
        'missed_turns': 0
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
    
    is_observer = player_id in room.get('observers', [])
    
    player = None
    for p in room['players']:
        if p['id'] == player_id:
            player = p
            break
    
    if not player and not is_observer:
        return jsonify({'ok': False, 'error': f'Игрок {player_id} не найден'}), 404
    
    players_info = []
    for p in room['players']:
        info = {
            'id': int(p['id']),
            'name': p['name'],
            'quartets': p['quartets'],
            'handCount': int(len(p['hand']))
        }
        if p['id'] == player_id or is_observer:
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
        'is_observer': is_observer
    })

@app.route('/rename', methods=['POST'])
def rename_player():
    data = request.get_json()
    code = data.get('code', '').upper()
    player_id = int(data.get('playerId', -1))
    new_name = data.get('name', 'Игрок').strip()
    
    if code not in rooms:
        return jsonify({'ok': False, 'error': 'Комната не найдена'}), 404
    
    room = rooms[code]
    for p in room['players']:
        if p['id'] == player_id:
            old_name = p['name']
            p['name'] = new_name
            room['history'].append({
                'time': datetime.now().strftime('%H:%M'),
                'text': f'✏️ {old_name} сменил имя на "{new_name}"',
                'type': 'system'
            })
            print(f"[RENAME] Игрок {player_id} в комнате {code}: {old_name} -> {new_name}")
            return jsonify({'ok': True})
    
    return jsonify({'ok': False, 'error': 'Игрок не найден'}), 404

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
    
    if from_player in room.get('observers', []):
        return jsonify({'ok': False, 'error': 'Наблюдатели не могут ходить'}), 400
    
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
    
    for p in room['players']:
        if p['id'] == from_player:
            p['missed_turns'] = 0
    
    if card_index is not None:
        card = target['hand'].pop(card_index)
        requester['hand'].append(card)
        
        check_quartets(room, from_player)
        check_quartets(room, to_player)
        
        room['currentPlayer'] = int(from_player)
        room['last_move_time'] = datetime.now().timestamp()
        
        room['history'].append({
            'time': datetime.now().strftime('%H:%M'),
            'text': f'{from_name} спросил(а) у {to_name}: «{card_name}» ({category}) — ✅ Есть!',
            'type': 'ok'
        })
        
        print(f"[REQUEST] {from_name} -> {to_name}: {card_name} ({category}) — УГАДАЛ")
        
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
        room['last_move_time'] = datetime.now().timestamp()
        
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
        
        print(f"[REQUEST] {from_name} -> {to_name}: {card_name} ({category}) — НЕ УГАДАЛ")
        
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
            print(f"[QUARTET] {p['name']} собрал(а) квартет «{cat}»!")

@app.route('/leave', methods=['POST'])
def leave_room():
    data = request.get_json()
    code = data.get('code', '').upper()
    player_id = int(data.get('playerId', -1))
    
    if code not in rooms:
        return jsonify({'ok': False, 'error': 'Комната не найдена'}), 404
    
    room = rooms[code]
    
    if player_id in room.get('observers', []):
        room['observers'].remove(player_id)
        return jsonify({'ok': True})
    
    player = None
    for p in room['players']:
        if p['id'] == player_id:
            player = p
            break
    
    if not player:
        return jsonify({'ok': False, 'error': 'Игрок не найден'}), 404
    
    player_name = player['name']
    
    room['players'] = [p for p in room['players'] if p['id'] != player_id]
    
    if len(room['players']) == 0:
        del rooms[code]
        return jsonify({'ok': True})
    
    if room['ownerId'] == player_id:
        if len(room['players']) > 0:
            new_owner = random.choice(room['players'])
            room['ownerId'] = new_owner['id']
            room['history'].append({
                'time': datetime.now().strftime('%H:%M'),
                'text': f'👑 Владение перешло к {new_owner["name"]}',
                'type': 'system'
            })
    
    if room['currentPlayer'] == player_id:
        if len(room['players']) > 0:
            next_player = room['currentPlayer'] % len(room['players'])
            room['currentPlayer'] = int(next_player)
            room['last_move_time'] = datetime.now().timestamp()
    
    room['history'].append({
        'time': datetime.now().strftime('%H:%M'),
        'text': f'🚪 {player_name} покинул игру',
        'type': 'system'
    })
    
    print(f"[LEAVE] {player_name} покинул комнату {code}")
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
    
    print(f"[END] Игра в комнате {code} завершена создателем")
    return jsonify({'ok': True})

@app.route('/feedback', methods=['POST'])
def feedback():
    data = request.get_json()
    code = data.get('code', '')
    player_id = data.get('playerId', -1)
    message = data.get('message', '').strip()
    player_name = data.get('name', 'Игрок')
    
    if not message:
        return jsonify({'ok': False, 'error': 'Сообщение не может быть пустым'}), 400
    
    global all_feedback
    feedback_entry = {
        'id': len(all_feedback) + 1,
        'time': datetime.now().strftime('%H:%M %d.%m'),
        'name': player_name,
        'playerId': player_id,
        'room': code,
        'message': message,
        'read': False
    }
    all_feedback.append(feedback_entry)
    save_feedback(all_feedback)
    
    print(f"[FEEDBACK] От {player_name} (ID: {player_id}, комната: {code}): {message}")
    return jsonify({'ok': True, 'message': 'Сообщение отправлено в поддержку'})

@app.route('/feedback/list/<int:player_id>', methods=['GET'])
def get_feedback_list(player_id):
    if player_id not in ADMIN_IDS:
        return jsonify({'ok': False, 'error': 'Доступ запрещён'}), 403
    
    feedback_list = sorted(all_feedback, key=lambda x: x['id'], reverse=True)
    return jsonify({'ok': True, 'feedback': feedback_list})

@app.route('/feedback/mark_read/<int:feedback_id>', methods=['POST'])
def mark_feedback_read(feedback_id):
    global all_feedback
    for entry in all_feedback:
        if entry['id'] == feedback_id:
            entry['read'] = True
            save_feedback(all_feedback)
            return jsonify({'ok': True})
    return jsonify({'ok': False, 'error': 'Сообщение не найдено'}), 404

@app.route('/admin/games/<int:player_id>', methods=['GET'])
def admin_games(player_id):
    if player_id not in ADMIN_IDS:
        return jsonify({'ok': False, 'error': 'Доступ запрещён'}), 403
    
    games_list = []
    for code, room in rooms.items():
        players_info = [{'id': p['id'], 'name': p['name']} for p in room['players']]
        games_list.append({
            'code': code,
            'status': room['status'],
            'players': players_info,
            'ownerId': room['ownerId'],
            'created': room['history'][0]['time'] if room['history'] else 'неизвестно'
        })
    
    return jsonify({'ok': True, 'games': games_list})

@app.route('/observe/<code>/<int:player_id>', methods=['POST'])
def observe_game(code, player_id):
    if player_id not in ADMIN_IDS:
        return jsonify({'ok': False, 'error': 'Доступ запрещён'}), 403
    
    if code not in rooms:
        return jsonify({'ok': False, 'error': 'Комната не найдена'}), 404
    
    room = rooms[code]
    
    if player_id not in room.get('observers', []):
        room.setdefault('observers', []).append(player_id)
    
    return jsonify({'ok': True, 'roomCode': code, 'playerId': player_id})

@app.route('/check_timeouts/<code>', methods=['POST'])
def check_timeouts(code):
    if code not in rooms:
        return jsonify({'ok': False, 'error': 'Комната не найдена'}), 404
    
    room = rooms[code]
    if room['status'] != 'playing':
        return jsonify({'ok': False, 'error': 'Игра не активна'}), 400
    
    current_time = datetime.now().timestamp()
    time_diff = current_time - room['last_move_time']
    
    if time_diff > 60:
        current_player_id = room['currentPlayer']
        current_player = None
        for p in room['players']:
            if p['id'] == current_player_id:
                current_player = p
                break
        
        if current_player:
            current_player['missed_turns'] = current_player.get('missed_turns', 0) + 1
            print(f"[TIMEOUT] {current_player['name']} пропустил ход ({current_player['missed_turns']} раз)")
            
            if current_player['missed_turns'] >= 2:
                player_name = current_player['name']
                room['players'] = [p for p in room['players'] if p['id'] != current_player_id]
                room['history'].append({
                    'time': datetime.now().strftime('%H:%M'),
                    'text': f'⏰ {player_name} исключён за бездействие',
                    'type': 'system'
                })
                print(f"[KICK] {player_name} исключён из комнаты {code} за бездействие")
                
                if len(room['players']) == 0:
                    del rooms[code]
                    return jsonify({'ok': True, 'kicked': True})
                
                if room['ownerId'] == current_player_id:
                    if len(room['players']) > 0:
                        new_owner = random.choice(room['players'])
                        room['ownerId'] = new_owner['id']
                        room['history'].append({
                            'time': datetime.now().strftime('%H:%M'),
                            'text': f'👑 Владение перешло к {new_owner["name"]}',
                            'type': 'system'
                        })
            else:
                next_player = (current_player_id + 1) % len(room['players'])
                room['currentPlayer'] = int(next_player)
                room['last_move_time'] = datetime.now().timestamp()
                room['history'].append({
                    'time': datetime.now().strftime('%H:%M'),
                    'text': f'⏰ Ход передан {room["players"][next_player]["name"]} (бездействие)',
                    'type': 'system'
                })
    
    return jsonify({'ok': True})

if __name__ == '__main__':
    app.run(host='0.0.0.0', port=int(os.environ.get('PORT', 5000)))
