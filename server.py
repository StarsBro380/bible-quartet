import os
import json
import random
import string
from flask import Flask, request, jsonify
from flask_cors import CORS

app = Flask(__name__)
CORS(app)

# Хранилище комнат в памяти
rooms = {}

def generate_code():
    """Генерирует 6-значный код комнаты"""
    return ''.join(random.choices(string.ascii_uppercase + string.digits, k=6))

def create_deck():
    """Создаёт перемешанную колоду из data.json"""
    with open('data.json', 'r', encoding='utf-8') as f:
        data = json.load(f)
    deck = []
    for q in data:
        for c in q['cards']:
            deck.append({'category': q['name'], 'categoryId': q['id'], 'cardName': c['name']})
    random.shuffle(deck)
    return deck, data

@app.route('/create', methods=['POST'])
def create_room():
    """Создаёт новую комнату"""
    data = request.get_json()
    player_name = data.get('name', 'Игрок')
    cards_count = data.get('cards', 10)
    
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
        'status': 'waiting',
        'maxPlayers': 4,
        'cardsPerPlayer': cards_count
    }
    
    rooms[code] = room
    return jsonify({'ok': True, 'code': code, 'playerId': 0})

@app.route('/join', methods=['POST'])
def join_room():
    """Подключается к существующей комнате"""
    data = request.get_json()
    code = data.get('code', '').upper()
    player_name = data.get('name', 'Игрок')
    
    if code not in rooms:
        return jsonify({'ok': False, 'error': 'Комната не найдена'}), 404
    
    room = rooms[code]
    
    if room['status'] != 'waiting':
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
    
    if len(room['players']) >= 2:
        room['status'] = 'playing'
    
    return jsonify({'ok': True, 'playerId': player_id})

@app.route('/state/<code>/<int:player_id>', methods=['GET'])
def get_state(code, player_id):
    """Возвращает состояние игры для конкретного игрока"""
    if code not in rooms:
        return jsonify({'ok': False, 'error': 'Комната не найдена'}), 404
    
    room = rooms[code]
    player = room['players'][player_id]
    
    # Скрываем руки других игроков
    players_info = []
    for p in room['players']:
        info = {
            'id': p['id'],
            'name': p['name'],
            'quartets': p['quartets'],
            'handCount': len(p['hand'])
        }
        if p['id'] == player_id:
            info['hand'] = p['hand']
        players_info.append(info)
    
    return jsonify({
        'ok': True,
        'code': code,
        'playerId': player_id,
        'players': players_info,
        'bankCount': len(room['deck']),
        'currentPlayer': room['currentPlayer'],
        'status': room['status'],
        'categories': room['categories']
    })

@app.route('/request', methods=['POST'])
def request_card():
    """Запрос карты у другого игрока"""
    data = request.get_json()
    code = data.get('code', '').upper()
    from_player = data.get('fromPlayer')
    to_player = data.get('toPlayer')
    category = data.get('category')
    card_name = data.get('cardName')
    
    if code not in rooms:
        return jsonify({'ok': False, 'error': 'Комната не найдена'}), 404
    
    room = rooms[code]
    
    if room['currentPlayer'] != from_player:
        return jsonify({'ok': False, 'error': 'Не ваш ход'}), 400
    
    # Проверяем, есть ли у запрашивающего карта из этой категории
    requester = room['players'][from_player]
    has_category = any(c['category'] == category for c in requester['hand'])
    if not has_category:
        return jsonify({'ok': False, 'error': 'У вас нет карт этой категории'}), 400
    
    # Ищем карту у другого игрока
    target = room['players'][to_player]
    card_index = None
    for i, c in enumerate(target['hand']):
        if c['category'] == category and c['cardName'] == card_name:
            card_index = i
            break
    
    if card_index is not None:
        # Забираем карту
        card = target['hand'].pop(card_index)
        requester['hand'].append(card)
        
        # Проверяем квартеты
        check_quartets(room, from_player)
        check_quartets(room, to_player)
        
        return jsonify({
            'ok': True,
            'found': True,
            'card': card,
            'nextPlayer': from_player  # Ходит снова
        })
    else:
        # Не угадал — берёт из банка
        if room['deck']:
            drawn = room['deck'].pop()
            requester['hand'].append(drawn)
            check_quartets(room, from_player)
        
        # Передаём ход следующему
        next_player = (from_player + 1) % len(room['players'])
        room['currentPlayer'] = next_player
        
        return jsonify({
            'ok': True,
            'found': False,
            'drawn': drawn if room['deck'] else None,
            'nextPlayer': next_player
        })

def check_quartets(room, player_id):
    """Проверяет и собирает квартеты"""
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

if __name__ == '__main__':
    app.run(host='0.0.0.0', port=int(os.environ.get('PORT', 5000)))
