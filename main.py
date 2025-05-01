from flask import Flask, render_template
import json
import os
from collections import Counter

from api import init_api_routes, DATA_FILE, get_data_as_table, get_total_earnings, get_earnings_today

app = Flask(__name__)

@app.route('/')
def show_data():
    # load existing data
    if os.path.exists(DATA_FILE):
        with open(DATA_FILE, 'r') as f:
            try:
                data = json.load(f)
            except json.JSONDecodeError:
                data = []
    else:
        data = []

    # count occurrences of each ad_id
    ad_counts = Counter(entry.get('ad_id', '') for entry in data)

    earnings_table = get_data_as_table()
    total_earnings = get_total_earnings()
    earnings_today = get_earnings_today()

    return render_template('index.html',
                           data=data,
                           ad_counts=ad_counts,
                           earnings_table=earnings_table,
                           total_earnings=total_earnings,
                           earnings_today=earnings_today)

@app.route('/send_data')
def send_data():
    return render_template('send_data.html')

# Initialize API routes
init_api_routes(app)

if __name__ == '__main__':
    app.run(debug=True, host='0.0.0.0', port=3000)
