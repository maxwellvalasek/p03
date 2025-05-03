from flask import Flask, render_template, request, jsonify
import json
import os
import pandas as pd
from folium import Map, Element
import folium
from folium.plugins import HeatMap, MarkerCluster
from datetime import datetime
from collections import Counter
from api import init_api_routes, DATA_FILE, get_data_as_table, get_total_earnings, get_earnings_today
import ast

app = Flask(__name__)

@app.route('/')
def show_data():
    if os.path.exists(DATA_FILE):
        with open(DATA_FILE, 'r') as f:
            try:
                data = json.load(f)
            except json.JSONDecodeError:
                data = []
    else:
        data = []

    ad_counts = Counter(entry.get('ad_id', '') for entry in data)
    return render_template('index.html',
                           data=data,
                           ad_counts=ad_counts,
                           earnings_table=get_data_as_table(),
                           total_earnings=get_total_earnings(),
                           earnings_today=get_earnings_today())

@app.route('/map')
def map_view():
    combined_coords = []
    valid_coords_exist = False

    # 1. Read from coords.csv
    coords_file = 'coords.csv'
    if os.path.exists(coords_file):
        try:
            df_coords = pd.read_csv(coords_file)
            # Add valid lat/lon pairs
            coords_csv_list = df_coords[['lat', 'lon']].dropna().values.tolist()
            combined_coords.extend(coords_csv_list)
            if coords_csv_list:
                 valid_coords_exist = True
        except Exception as e:
            print(f"Error processing {coords_file} for /map: {e}")
            
    # 2. Read from data.json
    if os.path.exists(DATA_FILE):
        try:
            with open(DATA_FILE, 'r') as f:
                all_data_json = json.load(f)
            if isinstance(all_data_json, list):
                for entry in all_data_json:
                    coords = parse_coordinate_string(entry.get('coordinates'))
                    if coords:
                        combined_coords.append(coords)
                        valid_coords_exist = True
        except (json.JSONDecodeError, IOError) as e:
            print(f"Error reading or parsing {DATA_FILE} for /map: {e}")

    # --- Static Map Setup (using combined data) ---
    if valid_coords_exist:
         min_lat = min(c[0] for c in combined_coords)
         max_lat = max(c[0] for c in combined_coords)
         min_lon = min(c[1] for c in combined_coords)
         max_lon = max(c[1] for c in combined_coords)
         padding = 0.001 
         if min_lat == max_lat: min_lat -= padding; max_lat += padding
         if min_lon == max_lon: min_lon -= padding; max_lon += padding
         fit_bounds_coords = [[min_lat, min_lon], [max_lat, max_lon]]
    else:
        fit_bounds_coords = [[37.8, -122.4], [37.9, -122.3]] # Default view

    m = Map(
            tiles="CartoDB positron",
            zoom_control=False,
            scrollWheelZoom=False,
            dragging=False,
            touchZoom=False,
            doubleClickZoom=False,
            boxZoom=False
    )
    
    m.fit_bounds(fit_bounds_coords)

    if combined_coords:
        HeatMap(combined_coords, radius=15, blur=12, min_opacity=0.3).add_to(m)

        # Update icon function to use $0.20 per marker
        icon_create_function = '''
        function(cluster) {
            var markers = cluster.getAllChildMarkers();
            var totalValue = markers.length * 0.20; // Use $0.20 per interaction
            var displayValue = '$' + totalValue.toFixed(2);
            var style = `
                background: linear-gradient(135deg, #ffffff 60%, #e3f0ff 100%);
                height: 28px; padding: 0 10px; border-radius: 14%; display: flex;
                justify-content: center; align-items: center; font-size: 1.3em;
                font-weight: 900; color: #1a237e; box-shadow: 0 2px 10px rgba(30,60,120,0.18);
                text-shadow: 0 2px 8px #fff, 0 0 2px #1976d2, 0 0 8px #fff; user-select: none; opacity: 0.75;
            `;
            return new L.DivIcon({
                html: '<div style="' + style + '">' + displayValue + '</div>',
                className: 'my-custom-cluster-icon-with-bg',
                iconSize: [48, 48]
             });
        }
        '''
        marker_cluster = MarkerCluster(
            icon_create_function=icon_create_function
        ).add_to(m)

        # Add markers for all combined coords
        for lat, lon in combined_coords:
            folium.Marker(
                location=[lat, lon],
                popup=f"Lat: {lat:.4f}, Lon: {lon:.4f}" # Simplified popup
            ).add_to(marker_cluster)

    m.save("templates/map_render.html")
    return render_template("map_render.html")

@app.route('/add_coord', methods=['POST'])
def add_coord():
    data = request.get_json()
    lat, lon = data.get("lat"), data.get("lon")
    if lat is None or lon is None:
        return jsonify({"error": "Missing lat/lon"}), 400

    # Get today's date in ISO format
    today_str = datetime.now().date().isoformat()

    # Append to CSV
    csv_path = 'coords.csv'
    if os.path.exists(csv_path):
        df = pd.read_csv(csv_path)
    else:
        df = pd.DataFrame(columns=['lat', 'lon', 'date'])

    # Ensure the 'date' column exists
    if 'date' not in df.columns:
        df['date'] = ''

    # Add the new row
    new_row = pd.DataFrame([[lat, lon, today_str]], columns=['lat', 'lon', 'date'])
    df = pd.concat([df, new_row], ignore_index=True)
    df.to_csv(csv_path, index=False)
    return jsonify({"status": "ok"})

@app.route('/map_today')
def map_today_view():
    today_combined_coords = []
    valid_today_coords_exist = False
    today_date = datetime.now().date()
    
    # 1. Read from coords.csv and filter for today
    coords_file = 'coords.csv'
    if os.path.exists(coords_file):
        try:
            df_coords = pd.read_csv(coords_file)
            if 'date' in df_coords.columns:
                df_coords['date'] = pd.to_datetime(df_coords['date'], errors='coerce')
                df_coords_today = df_coords.dropna(subset=['date'])[df_coords['date'].dt.date == today_date]
                coords_csv_today = df_coords_today[['lat', 'lon']].dropna().values.tolist()
                today_combined_coords.extend(coords_csv_today)
                if coords_csv_today:
                    valid_today_coords_exist = True
        except Exception as e:
            print(f"Error processing {coords_file} for /map_today: {e}")
            
    # 2. Read from data.json and filter for today
    if os.path.exists(DATA_FILE):
        try:
            with open(DATA_FILE, 'r') as f:
                all_data_json = json.load(f)
            if isinstance(all_data_json, list):
                for entry in all_data_json:
                    try:
                        entry_ts = datetime.fromisoformat(entry.get('timestamp', '')).date()
                        if entry_ts == today_date:
                             coords = parse_coordinate_string(entry.get('coordinates'))
                             if coords:
                                 today_combined_coords.append(coords)
                                 valid_today_coords_exist = True
                    except (ValueError, TypeError):
                        continue # Ignore invalid timestamps
        except (json.JSONDecodeError, IOError) as e:
            print(f"Error reading or parsing {DATA_FILE} for /map_today: {e}")

    # --- Static Map Setup for Today (using combined data) ---
    if valid_today_coords_exist:
         min_lat = min(c[0] for c in today_combined_coords)
         max_lat = max(c[0] for c in today_combined_coords)
         min_lon = min(c[1] for c in today_combined_coords)
         max_lon = max(c[1] for c in today_combined_coords)
         padding = 0.001 
         if min_lat == max_lat: min_lat -= padding; max_lat += padding
         if min_lon == max_lon: min_lon -= padding; max_lon += padding
         fit_bounds_coords = [[min_lat, min_lon], [max_lat, max_lon]]
    else:
        fit_bounds_coords = [[37.8, -122.4], [37.9, -122.3]] # Default view
        
    m = Map(
            tiles="CartoDB positron",
            # Keep static options 
            zoom_control=False,
            scrollWheelZoom=False,
            dragging=False,
            touchZoom=False,
            doubleClickZoom=False,
            boxZoom=False
    )

    m.fit_bounds(fit_bounds_coords)

    if today_combined_coords:
        HeatMap(today_combined_coords, radius=15, blur=12, min_opacity=0.3).add_to(m)

        # Use the same updated icon function ($0.20 per marker)
        icon_create_function = '''
        function(cluster) {
            var markers = cluster.getAllChildMarkers();
            var totalValue = markers.length * 0.20; // Use $0.20 per interaction
            var displayValue = '$' + totalValue.toFixed(2);
            var style = `
                background: linear-gradient(135deg, #ffffff 60%, #e3f0ff 100%);
                height: 28px; padding: 0 10px; border-radius: 14%; display: flex;
                justify-content: center; align-items: center; font-size: 1.3em;
                font-weight: 900; color: #1a237e; box-shadow: 0 2px 10px rgba(30,60,120,0.18);
                text-shadow: 0 2px 8px #fff, 0 0 2px #1976d2, 0 0 8px #fff; user-select: none; opacity: 0.75;
            `;
            return new L.DivIcon({
                html: '<div style="' + style + '">' + displayValue + '</div>',
                className: 'my-custom-cluster-icon-with-bg',
                iconSize: [48, 48]
             });
        }
        '''
        marker_cluster = MarkerCluster(
             icon_create_function=icon_create_function
        ).add_to(m)

        # Add markers for today's combined coords
        for lat, lon in today_combined_coords:
            folium.Marker(
                location=[lat, lon],
                popup=f"Lat: {lat:.4f}, Lon: {lon:.4f}" # Simplified popup
            ).add_to(marker_cluster)
            
    # Map remains static - no click/reset logic needed

    m.save("templates/map_today_render.html")
    return render_template("map_today_render.html")

# Initialize API routes
init_api_routes(app)

# Restore Helper function to parse coordinate string safely
def parse_coordinate_string(coord_str):
    try:
        if isinstance(coord_str, str) and coord_str.startswith('(') and coord_str.endswith(')'):
            coords = ast.literal_eval(coord_str)
            if isinstance(coords, tuple) and len(coords) == 2 and all(isinstance(c, (int, float)) for c in coords):
                return list(coords)
        print(f"Warning: Could not parse coordinate string: {coord_str}")
        return None
    except (ValueError, SyntaxError, TypeError) as e:
        print(f"Error parsing coordinate string '{coord_str}': {e}")
        return None

if __name__ == '__main__':
    app.run(debug=True, host='0.0.0.0', port=3000)
