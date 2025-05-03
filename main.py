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
import tempfile
import shutil

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

@app.route('/land')
def land_page():
    # Renders the land.html template
    return render_template('land.html')

@app.route('/send_data')
def send_data():
    return render_template('send_data.html')

@app.route('/testhome')
def testhome_page():
    # Renders the testhome.html template
    return render_template('testhome.html')

@app.route('/map')
def map_view():
    combined_coords = []
    valid_coords_exist = False

    # 1. Read from coords.csv (Assuming this should still be included based on previous state)
    coords_file = 'coords.csv'
    if os.path.exists(coords_file):
        try:
            df_coords = pd.read_csv(coords_file)
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
        HeatMap(combined_coords, radius=13, blur=12, min_opacity=0.3).add_to(m) # Adjusted radius from user prompt

        icon_create_function = '''
        function(cluster) {
            var markers = cluster.getAllChildMarkers();
                var totalValue = markers.length * 0.20;
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
        marker_cluster = MarkerCluster(icon_create_function=icon_create_function).add_to(m)

        for lat, lon in combined_coords:
            folium.Marker(
                location=[lat, lon],
                popup=f"Lat: {lat:.4f}, Lon: {lon:.4f}"
            ).add_to(marker_cluster)

    # Atomic write to a static file
    map_filename = "templates/map_render.html"
    # Use try-finally to ensure temporary file is cleaned up on error during move
    tmp_file = None
    try:
        with tempfile.NamedTemporaryFile("w", dir="templates", delete=False, suffix=".html") as tmp_f:
            tmp_file = tmp_f.name # Store the temp file name
            m.save(tmp_file)
        # If save succeeds, move the file
        shutil.move(tmp_file, map_filename)
        tmp_file = None # Indicate move was successful
    finally:
        # Clean up the temp file only if the move failed and tmp_file exists
        if tmp_file and os.path.exists(tmp_file):
            try:
                os.remove(tmp_file)
            except OSError as e:
                print(f"Error removing temporary file {tmp_file}: {e}")

    return render_template("map_render.html")

@app.route('/map_today')
def map_today_view():
    # Cache-busting timestamp is ignored (available as request.args.get('t'))
    today_combined_coords = []
    valid_today_coords_exist = False
    today_date = datetime.now().date()
    
    # Load data from data.json and filter for today
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
                        continue  # Ignore invalid timestamps
        except (json.JSONDecodeError, IOError) as e:
            print(f"Error reading or parsing {DATA_FILE} for /map_today: {e}")

    # --- Force UC Berkeley campus bounding box ---
    fit_bounds_coords = [
        [37.8627, -122.2726],  # South-West corner
        [37.8790, -122.2453]   # North-East corner
    ]
    m = Map(
        tiles="CartoDB positron",
        # Enable interactive features
        zoom_control=True,
        scrollWheelZoom=True,
        dragging=True,
        touchZoom=True,
        doubleClickZoom=True,
        boxZoom=True
    )

    m.fit_bounds(fit_bounds_coords)
    
    # Add a timestamp to the HTML to prevent browser caching
    timestamp = datetime.now().strftime('%Y%m%d%H%M%S')
    map_filename = f"templates/map_today_render_{timestamp}.html"

    if today_combined_coords:
        HeatMap(today_combined_coords, radius=12, blur=12, min_opacity=0.3).add_to(m)

        icon_create_function = '''
        function(cluster) {
            var markers = cluster.getAllChildMarkers();
            var totalValue = markers.length * 0.20;
            var displayValue = '$' + totalValue.toFixed(2);
            var style = `
                background: linear-gradient(135deg, #ffffff 60%, #e3f0ff 100%);
                height: 28px; padding: 0 10px; border-radius: 14%;
                display: flex; justify-content: center; align-items: center;
                font-size: 1.3em; font-weight: 900; color: #1a237e;
                box-shadow: 0 2px 10px rgba(30,60,120,0.18);
                text-shadow: 0 2px 8px #fff, 0 0 2px #1976d2, 0 0 8px #fff;
                user-select: none; opacity: 0.75;
            `;
            return new L.DivIcon({
                html: '<div style="' + style + '">' + displayValue + '</div>',
                className: 'my-custom-cluster-icon-with-bg',
                iconSize: [48, 48]
             });
        }
        '''
        marker_cluster = MarkerCluster(icon_create_function=icon_create_function).add_to(m)

        for lat, lon in today_combined_coords:
            folium.Marker(
                location=[lat, lon],
                popup=f"Lat: {lat:.4f}, Lon: {lon:.4f}"
            ).add_to(marker_cluster)

    # Map remains static - no click/reset logic needed

    # Atomic write for today map
    map_filename_today = "templates/map_today_render.html"
    tmp_file_today = None
    try:
        with tempfile.NamedTemporaryFile("w", dir="templates", delete=False, suffix=".html") as tmp_f:
            tmp_file_today = tmp_f.name
            m.save(tmp_file_today)
        shutil.move(tmp_file_today, map_filename_today)
        tmp_file_today = None # Indicate move was successful
    finally:
        # Clean up the temp file only if the move failed
        if tmp_file_today and os.path.exists(tmp_file_today):
            try:
                os.remove(tmp_file_today)
            except OSError as e:
                print(f"Error removing temporary file {tmp_file_today}: {e}")

    return render_template("map_today_render.html")

# Initialize API routes
init_api_routes(app)

# Restore Helper function to parse coordinate string safely
def parse_coordinate_string(coord_str):
    try:
        # Handle format: "(37.875994, -122.3412217)"
        if isinstance(coord_str, str) and coord_str.startswith('(') and coord_str.endswith(')'):
            coords = ast.literal_eval(coord_str)
            if isinstance(coords, tuple) and len(coords) == 2 and all(isinstance(c, (int, float)) for c in coords):
                return list(coords)
                
        # Handle format: "37.875994,-122.3412217"
        elif isinstance(coord_str, str) and ',' in coord_str and not coord_str.startswith('('):
            parts = coord_str.split(',')
            if len(parts) == 2:
                try:
                    lat = float(parts[0].strip())
                    lon = float(parts[1].strip())
                    return [lat, lon]
                except ValueError:
                    pass
                    
        print(f"Warning: Could not parse coordinate string: {coord_str}")
        return None
    except (ValueError, SyntaxError, TypeError) as e:
        print(f"Error parsing coordinate string '{coord_str}': {e}")
        return None

if __name__ == '__main__':
    app.run(debug=True, host='0.0.0.0', port=3000)
