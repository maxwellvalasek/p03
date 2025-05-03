from flask import Flask, render_template, request, jsonify
import json
import os
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

@app.route('/send_data')
def send_data():
    return render_template('send_data.html')

@app.route('/map')
def map_view():
    # Cache-busting timestamp is ignored (available as request.args.get('t'))
    combined_coords = []
    valid_coords_exist = False

    # Load data from data.json
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

    # Add a timestamp to the HTML to prevent browser caching
    timestamp = datetime.now().strftime('%Y%m%d%H%M%S')
    map_filename = f"templates/map_render_{timestamp}.html"

    if combined_coords:
        HeatMap(combined_coords, radius=13, blur=12, min_opacity=0.3).add_to(m)

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

    m.save(map_filename)
    
    # Clean up old map files (keep at most 5 recent files)
    try:
        map_files = [f for f in os.listdir('templates') if f.startswith('map_render_')]
        if len(map_files) > 5:
            map_files.sort()
            for old_file in map_files[:-5]:
                os.remove(os.path.join('templates', old_file))
    except Exception as e:
        print(f"Error cleaning up old map files: {e}")
        
    return render_template(os.path.basename(map_filename))

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
            
    m.save(map_filename)
    
    # Clean up old map files (keep at most 5 recent files)
    try:
        map_files = [f for f in os.listdir('templates') if f.startswith('map_today_render_')]
        if len(map_files) > 5:
            map_files.sort()
            for old_file in map_files[:-5]:
                os.remove(os.path.join('templates', old_file))
    except Exception as e:
        print(f"Error cleaning up old map files: {e}")
        
    return render_template(os.path.basename(map_filename))

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
