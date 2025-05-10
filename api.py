from flask import jsonify, request, abort, Response
import json
import os
import requests
from datetime import datetime
import pandas as pd
from flask import stream_with_context

DATA_FILE = 'data.json'
connected_clients = set()

EARNINGS_BY_TYPE = {
    'SWIPE_UP': 0.05,
    'SWIPE_DOWN': 0.05,
    'SWIPE_RIGHT': 0.20,
    'qr': 1.00
}
DEFAULT_EARNINGS = 0.20  # fallback if type not found

def get_latest_coordinates():
    """Gets the coordinates of the most recent entry in data.json."""
    if os.path.exists(DATA_FILE):
        try:
            with open(DATA_FILE, 'r') as f:
                data = json.load(f)
                if isinstance(data, list) and data:
                    # Sort by timestamp (assuming ISO format allows string comparison)
                    # Or parse to datetime if needed for robustness
                    latest_entry = max(data, key=lambda x: x.get('timestamp', ''))
                    return latest_entry.get('coordinates')
        except (json.JSONDecodeError, IOError, ValueError) as e:
            print(f"Error getting latest coordinates: {e}")
    return None

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
                    
                    latest_coords = None
                    if data_updated:
                        latest_coords_str = get_latest_coordinates()
                        if latest_coords_str:
                            try:
                                # Basic parsing assuming format '(lat, lng)'
                                lat_str, lng_str = latest_coords_str.strip('()').split(',')
                                latest_coords = {'lat': float(lat_str), 'lng': float(lng_str)}
                            except ValueError:
                                print(f"Could not parse latest coords: {latest_coords_str}")

                    data = {
                        'table': table,
                        'total_earnings': total,
                        'earnings_today': today,
                        'interactions_today': interactions_today,
                        'total_interactions': total_interactions,
                        'data_updated': data_updated,
                        'latest_coords': latest_coords,
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

        # Determine earnings based on interaction_type
        earnings = EARNINGS_BY_TYPE.get(interaction_type, DEFAULT_EARNINGS)

        new_entry = {
            'coordinates': '(37.8760, -122.2588)',  # Updated Berkeley coordinates
            'interaction_type': interaction_type,
            'ad_id': ad_id,
            'timestamp': timestamp,
            'earnings': earnings
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

def make_post_request(
    url='http://localhost:5000/api/data',
    interaction_type='swipe',
    ad_id='default_ad'
):
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
                    # Ensure earnings column is numeric, default to 0.20 if missing/invalid
                    df['earnings'] = pd.to_numeric(df['earnings'], errors='coerce').fillna(0.20)
                    summary = (
                        df.groupby('ad_id')
                        .agg(Interactions=('ad_id', 'size'), Earnings=('earnings', 'sum'))
                        .reset_index()
                    )
                    return summary.to_dict(orient='records')
                else:
                    return []
            except (json.JSONDecodeError, IOError): # Added IOError
                print(f"Error reading/parsing {DATA_FILE} for table")
                return [] # Return empty on error
    else:
        return []

def get_total_earnings():
    total_earnings = 0.0
    if os.path.exists(DATA_FILE):
        with open(DATA_FILE, 'r') as f:
            try:
                data = json.load(f)
                if isinstance(data, list):
                    # Sum 'earnings', defaulting to 0.20 if missing or invalid
                    total_earnings = sum(float(entry.get('earnings', 0.20)) for entry in data if isinstance(entry.get('earnings', 0.20), (int, float, str)) and str(entry.get('earnings', 0.20)).replace('.', '', 1).isdigit())
            except (json.JSONDecodeError, IOError):
                print(f"Error reading/parsing {DATA_FILE} for total earnings")
                pass # Return 0.0 on error
    return total_earnings

def get_earnings_today():
    today_date = datetime.now().date()
    earnings_today = 0.0

    if os.path.exists(DATA_FILE):
        try:
            with open(DATA_FILE, 'r') as f:
                data = json.load(f)
                if isinstance(data, list):
                    for entry in data:
                        try:
                            entry_ts = datetime.fromisoformat(entry.get('timestamp', '')).date()
                            if entry_ts == today_date:
                                # Add earnings, defaulting to 0.20 if missing or invalid
                                earnings_val = entry.get('earnings', 0.20)
                                if isinstance(earnings_val, (int, float, str)) and str(earnings_val).replace('.', '', 1).isdigit():
                                    earnings_today += float(earnings_val)
                                else:
                                     earnings_today += 0.20 # Default if invalid format
                        except (ValueError, TypeError):
                            continue # Ignore invalid timestamps or earnings format errors within the loop
        except (json.JSONDecodeError, IOError):
            print(f"Error reading/parsing {DATA_FILE} for today's earnings")
            # Return 0.0 on error reading the file

    return earnings_today

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
