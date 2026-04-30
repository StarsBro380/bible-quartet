import os
import json
import random
import string
from datetime import datetime
from flask import Flask, request, jsonify
from flask_cors import CORS

app = Flask(__name__)
CORS(app)

rooms = {}

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
    
    if code not in rooms:
        return jsonify({'ok': False, 'error': 'Комната не найдена'}), 404
    
    room = rooms[code]
    
    if room['status'] != 'lobby':
        return jsonify({'ok': False, 'error': 'Игра уже началась'}), 400
    
    if len(room['players']) >= room['maxPlayers']:
        return jsonify({'ok': False, 'error': 'Комната заполнена'}), 400
    
    player_id = len(room['players'])
    cards = room['deck'][:room['cardsPerPlayer']]
    room['deck'] = room['deck'][room['cardsPerPlayer']:]
    
    room['players'].append({
        'id': player_id,
        'name': player_name,
        'hand': cards,
        'quartets': []
    })
    
    room['history'].append({
        'time': datetime.now().strftime('%H:%M'),
        'text': f'👤 {player_name} присоединился к игре',
        'type': 'system'
    })
    
    print(f"[JOIN] Комната {code}, новый игрок {player_id}: {player_name}")
    return jsonify({'ok': True, 'playerId': int(player_id)})

@app.route('/state/<code>/<int:player_id>', methods=['GET'])
def get_state(code, player_id):
    if code not in rooms:
        return jsonify({'ok': False, 'error': 'Комната не найдена'}), 404
    
    room = rooms[code]
    
    # Ищем игрока по ID
    player = None
    for p in room['players']:
        if p['id'] == player_id:
            player = p
            break
    
    if not player:
        return jsonify({'ok': False, 'error': f'Игрок {player_id} не найден. Всего игроков: {len(room["players"])}'}), 404
    
    players_info = []
    for p in room['players']:
        info = {
            'id': int(p['id']),
            'name': p['name'],
            'quartets': p['quartets'],
            'handCount': int(len(p['hand']))
        }
        # Показываем руку только самому игроку
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
    
    # Проверяем, что ходящий игрок существует
    if from_player >= len(room['players']) or from_player < 0:
        return jsonify({'ok': False, 'error': 'Игрок не найден'}), 400
    
    # Проверяем currentPlayer
    if int(room['currentPlayer']) != from_player:
        return jsonify({'ok': False, 'error': f'Не ваш ход. Сейчас ходит игрок {room["currentPlayer"]}'}), 400
    
    requester = room['players'][from_player]
    has_category = any(c['category'] == category for c in requester['hand'])
    if not has_category:
        return jsonify({'ok': False, 'error': 'У вас нет карт этой категории'}), 400
    
    # Проверяем, что целевой игрок существует
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
        
        print(f"[REQUEST] {from_name} -> {to_name}: {card_name} ({category}) — НЕ УГАДАЛ. Ход переходит к {next_player}")
        
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

if __name__ == '__main__':
    app.run(host='0.0.0.0', port=int(os.environ.get('PORT', 5000)))
