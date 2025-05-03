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
            last_data_count = 0
            
            while True:
                try:
                    # Get current data
                    table = get_data_as_table()
                    total = get_total_earnings()
                    today = get_earnings_today()
                    interactions_today = get_interactions_today()
                    total_interactions = get_total_interactions()
                    
                    # Check if data count has changed (new data added)
                    data_updated = total_interactions != last_data_count
                    last_data_count = total_interactions
                    
                    data = {
                        'table': table,
                        'total_earnings': total,
                        'earnings_today': today,
                        'interactions_today': interactions_today,
                        'total_interactions': total_interactions,
                        'data_updated': data_updated,
                        'timestamp': datetime.now().isoformat()
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
            'coordinates': '(37.8760, -122.2588)',  # Updated Berkeley coordinates
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
        'coordinates': '(37.8760, -122.2588)',  # Updated Berkeley coordinates
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
    # Calculate based on combined interactions * value
    total_interactions = get_total_interactions()
    return total_interactions * 0.20

def get_earnings_today():
    # Calculate based on combined interactions today * value
    interactions_today = get_interactions_today()
    return interactions_today * 0.20

def get_interactions_today():
    today_date = datetime.now().date()
    data_today_count = 0

    # Count today's entries in data.json
    if os.path.exists(DATA_FILE):
        try:
            with open(DATA_FILE, 'r') as f:
                data = json.load(f)
                if isinstance(data, list):
                    for entry in data:
                        try:
                            entry_ts = datetime.fromisoformat(entry.get('timestamp', '')).date()
                            if entry_ts == today_date:
                                data_today_count += 1
                        except (ValueError, TypeError):
                            continue # Ignore invalid timestamps
        except (json.JSONDecodeError, IOError):
            print(f"Error reading/parsing {DATA_FILE} for today's count")
            
    return data_today_count

def get_total_interactions():
    data_count = 0

    # Count total entries in data.json
    if os.path.exists(DATA_FILE):
        try:
            with open(DATA_FILE, 'r') as f:
                data = json.load(f)
                if isinstance(data, list):
                    data_count = len(data)
        except (json.JSONDecodeError, IOError):
             print(f"Error reading/parsing {DATA_FILE} for total count")
             
    return data_count
