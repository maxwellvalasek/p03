from flask import jsonify, request, abort
import json
import os
import requests
from datetime import datetime
import pandas as pd

DATA_FILE = 'data.json'

def init_api_routes(app):
    @app.route('/api/data', methods=['POST'])
    def handle_data():
        if not request.is_json:
            abort(400, description="Invalid JSON")
        
        data = request.get_json()
        coordinates = data.get('coordinates', '')
        interaction_type = data.get('interaction_type', '')
        ad_id = data.get('ad_id', '')
        timestamp = datetime.now().isoformat()
        earnings = 0.20  # New field for earnings
        new_entry = {
            'coordinates': coordinates,
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

        return jsonify({
            'message': 'Data received and saved successfully',
            'received_data': new_entry,
            'method_used': request.method
        }), 200 

def make_post_request(url, coordinates, interaction_type, ad_id):
    payload = {
        'coordinates': coordinates,
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
                    print(summary)
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
