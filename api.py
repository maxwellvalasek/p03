from flask import jsonify, request, abort, Response
import json
import os
import requests
from datetime import datetime
import pandas as pd
from flask import stream_with_context

DATA_FILE = 'data.json'
connected_clients = set()

def init_api_routes(app):
    @app.route('/api/events')
    def events():
        def generate():
            while True:
                try:
                    # Get current data
                    table = get_data_as_table()
                    total = get_total_earnings()
                    today = get_earnings_today()
                    interactions_today = get_interactions_today()
                    total_interactions = get_total_interactions()
                    
                    data = {
                        'table': table,
                        'total_earnings': total,
                        'earnings_today': today,
                        'interactions_today': interactions_today,
                        'total_interactions': total_interactions
                    }
                    
                    yield f"data: {json.dumps(data)}\n\n"
                except Exception as e:
                    print(f"Error in event stream: {e}")
                    break
                
        return Response(stream_with_context(generate()), mimetype='text/event-stream')

    @app.route('/api/data', methods=['POST'])
    def handle_data():
        if not request.is_json:
            abort(400, description="Invalid JSON")
        
        data = request.get_json()
        interaction_type = data.get('interaction_type', '')
        ad_id = data.get('ad_id', '')
        timestamp = datetime.now().isoformat()
        earnings = 0.20  # New field for earnings
        new_entry = {
            'coordinates': '(37.875994, -122.3412217)',  # Hardcoded coordinates
            'interaction_type': interaction_type,
            'ad_id': ad_id,
            'timestamp': timestamp,
            'earnings': earnings  # Add earnings to the new entry
        }

        if os.path.exists(DATA_FILE):
            with open(DATA_FILE, 'r+') as f:
                try:
                    existing_data = json.load(f)
                    if not isinstance(existing_data, list):
                        existing_data = [existing_data]
                except json.JSONDecodeError:
                    existing_data = []
                existing_data.append(new_entry)
                f.seek(0)
                json.dump(existing_data, f, indent=2)
                f.truncate()
        else:
            with open(DATA_FILE, 'w') as f:
                json.dump([new_entry], f, indent=2)

        # Get updated data
        updated_table = get_data_as_table()
        updated_total = get_total_earnings()
        updated_today = get_earnings_today()
        interactions_today = get_interactions_today()
        total_interactions = get_total_interactions()

        return jsonify({
            'message': 'Data received and saved successfully',
            'received_data': new_entry,
            'method_used': request.method,
            'updated_data': {
                'table': updated_table,
                'total_earnings': updated_total,
                'earnings_today': updated_today,
                'interactions_today': interactions_today,
                'total_interactions': total_interactions
            }
        }), 200

def make_post_request(url, interaction_type, ad_id):
    payload = {
        'coordinates': '(37.875994, -122.3412217)',  # Hardcoded coordinates
        'interaction_type': interaction_type,
        'ad_id': ad_id
    }
    headers = {'Content-Type': 'application/json'}
    response = requests.post(url, json=payload, headers=headers)
    return response.json(), response.status_code

def get_data_as_table():
    if os.path.exists(DATA_FILE):
        with open(DATA_FILE, 'r') as f:
            try:
                data = json.load(f)
                if not isinstance(data, list):
                    data = [data]
                df = pd.DataFrame(data)
                if not df.empty:
                    summary = (
                        df.groupby('ad_id')
                        .size()
                        .reset_index(name='Interactions')
                    )
                    summary['Earnings'] = summary['Interactions'] * 0.20
                    # Keep earnings as a float
                    return summary.to_dict(orient='records')
                else:
                    return []
            except json.JSONDecodeError:
                return []
    else:
        return []

def get_total_earnings():
    table = get_data_as_table()
    return sum(row['Earnings'] for row in table)

def get_earnings_today():
    if os.path.exists(DATA_FILE):
        with open(DATA_FILE, 'r') as f:
            try:
                data = json.load(f)
                if not isinstance(data, list):
                    data = [data]
                df = pd.DataFrame(data)
                if not df.empty:
                    today = datetime.now().date()
                    df['timestamp'] = pd.to_datetime(df['timestamp'])
                    today_earnings = df[df['timestamp'].dt.date == today]['earnings'].sum()
                    return today_earnings
                else:
                    return 0.0
            except json.JSONDecodeError:
                return 0.0
    else:
        return 0.0

def get_interactions_today():
    if os.path.exists(DATA_FILE):
        with open(DATA_FILE, 'r') as f:
            try:
                data = json.load(f)
                if not isinstance(data, list):
                    data = [data]
                df = pd.DataFrame(data)
                if not df.empty:
                    today = datetime.now().date()
                    df['timestamp'] = pd.to_datetime(df['timestamp'])
                    today_count = df[df['timestamp'].dt.date == today].shape[0]
                    return today_count
                else:
                    return 0
            except json.JSONDecodeError:
                return 0
    else:
        return 0

def get_total_interactions():
    if os.path.exists(DATA_FILE):
        with open(DATA_FILE, 'r') as f:
            try:
                data = json.load(f)
                if not isinstance(data, list):
                    data = [data]
                return len(data)
            except json.JSONDecodeError:
                return 0
    else:
        return 0
