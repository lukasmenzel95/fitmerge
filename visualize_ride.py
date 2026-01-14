import gpxpy
import folium
import webbrowser
import os
import math
import json
from datetime import timedelta
from branca.element import MacroElement
from jinja2 import Template
#!/usr/bin/env python3
# --- CONFIG ---
INPUT_GPX = 'merged_ride.gpx'
OUTPUT_MAP = 'ride_map.html'
GAP_THRESHOLD_HOURS = 5
CHART_POINTS_COUNT = 400  # Downsample chart to this many points for performance

# Palette
RED_HUES = [
    '#FF4500', '#8B0000', '#FF6347', '#DC143C', 
    '#B22222', '#FA8072', '#800000', '#FF0000', 
    '#CD5C5C', '#C71585', '#A52A2A', '#E9967A'
]

# --- CLASSES ---

class StatsOverlay(MacroElement):
    """Floating stats card (Bottom-Left)"""
    _template = Template("""
        {% macro html(this, kwargs) %}
        <div style="
            position: fixed; bottom: 30px; left: 30px; width: 220px; z-index: 9999; 
            background-color: rgba(255, 255, 255, 0.9); border-radius: 8px; padding: 15px; 
            box-shadow: 0 4px 12px rgba(0,0,0,0.3); font-family: sans-serif; font-size: 13px; color: #333;
            border-left: 5px solid #DC143C;
            ">
            <h4 style="margin: 0 0 10px 0; color: #DC143C; text-transform: uppercase; font-size: 12px; letter-spacing: 1px;">Trip Stats</h4>
            <div style="display:flex;justify-content:space-between;margin-bottom:4px;"><span>Dist:</span><b>{{ this.distance_km }} km</b></div>
            <div style="display:flex;justify-content:space-between;margin-bottom:4px;"><span>Time:</span><b>{{ this.moving_time_str }}</b></div>
            <div style="display:flex;justify-content:space-between;margin-bottom:4px;"><span>Avg:</span><b>{{ this.avg_speed }} km/h</b></div>
            <div style="display:flex;justify-content:space-between;margin-bottom:4px;"><span>Climb:</span><b>{{ this.elevation }} m</b></div>
            <div style="margin-top:8px;padding-top:8px;border-top:1px solid #ddd;font-size:11px;color:#777;">
                {{ this.days }} Segments
            </div>
        </div>
        {% endmacro %}
    """)
    def __init__(self, distance_km, moving_time_str, avg_speed, elevation, days):
        super().__init__()
        self.distance_km = distance_km
        self.moving_time_str = moving_time_str  # Fixed: Key name match
        self.avg_speed = avg_speed
        self.elevation = elevation
        self.days = days

class ChartOverlay(MacroElement):
    """Interactive Elevation Profile using Chart.js (Bottom-Right/Center)"""
    _template = Template("""
        {% macro html(this, kwargs) %}
        <script src="https://cdn.jsdelivr.net/npm/chart.js"></script>
        
        <div style="
            position: fixed; bottom: 30px; right: 30px; width: 40vw; height: 160px; z-index: 9999;
            background-color: rgba(30, 30, 30, 0.85); border-radius: 8px; padding: 10px;
            box-shadow: 0 4px 12px rgba(0,0,0,0.5); backdrop-filter: blur(4px);
            ">
            <canvas id="elevationChart"></canvas>
        </div>

        <script>
            var ctx = document.getElementById('elevationChart').getContext('2d');
            var dataPoints = {{ this.data }};
            
            // Create Gradient
            var gradient = ctx.createLinearGradient(0, 0, 0, 160);
            gradient.addColorStop(0, 'rgba(220, 20, 60, 0.6)'); // Red
            gradient.addColorStop(1, 'rgba(220, 20, 60, 0.0)'); // Transparent

            new Chart(ctx, {
                type: 'line',
                data: {
                    labels: dataPoints.map(p => p.x), // Distances
                    datasets: [{
                        label: 'Elevation (m)',
                        data: dataPoints.map(p => p.y), // Elevations
                        borderColor: '#DC143C',
                        backgroundColor: gradient,
                        borderWidth: 2,
                        pointRadius: 0, // Hide points for smooth look
                        pointHoverRadius: 4,
                        fill: true,
                        tension: 0.1 // Slight smoothing
                    }]
                },
                options: {
                    responsive: true,
                    maintainAspectRatio: false,
                    interaction: { mode: 'index', intersect: false },
                    plugins: {
                        legend: { display: false },
                        tooltip: { 
                            displayColors: false,
                            callbacks: { title: (c) => 'Distance: ' + c[0].label + 'km' }
                        }
                    },
                    scales: {
                        x: { 
                            display: true, 
                            ticks: { maxTicksLimit: 8, color: '#aaa', font: {size: 10} }, 
                            grid: { display: false } 
                        },
                        y: { 
                            display: true, 
                            ticks: { color: '#aaa', font: {size: 10} }, 
                            grid: { color: '#444' } 
                        }
                    }
                }
            });
        </script>
        {% endmacro %}
    """)
    def __init__(self, data_json):
        super().__init__()
        self.data = data_json

# --- HELPER FUNCTIONS ---

def format_duration(seconds):
    h = int(seconds // 3600)
    m = int((seconds % 3600) // 60)
    return f"{h}h {m}m"

def haversine(lat1, lon1, lat2, lon2):
    """Simple distance calc between two points (in km)"""
    R = 6371  # Earth radius km
    dlat = math.radians(lat2 - lat1)
    dlon = math.radians(lon2 - lon1)
    a = (math.sin(dlat/2)**2 + math.cos(math.radians(lat1)) * math.cos(math.radians(lat2)) * math.sin(dlon/2)**2)
    c = 2 * math.atan2(math.sqrt(a), math.sqrt(1-a))
    return R * c

def process_gpx(gpx):
    points = []
    elevation_profile = []
    
    total_dist = 0.0
    prev_point = None
    
    # Iterate all points to build map data AND chart data
    for track in gpx.tracks:
        for segment in track.segments:
            for p in segment.points:
                
                # 1. Map Point
                points.append({
                    'loc': (p.latitude, p.longitude),
                    'time': p.time,
                    'ele': p.elevation
                })
                
                # 2. Chart Data (Cumulative Distance)
                if prev_point:
                    dist = haversine(prev_point.latitude, prev_point.longitude, p.latitude, p.longitude)
                    total_dist += dist
                
                # Only add to chart if elevation exists
                if p.elevation is not None:
                    elevation_profile.append({'x': total_dist, 'y': p.elevation})
                    
                prev_point = p

    # --- Downsample Chart Data ---
    if len(elevation_profile) > CHART_POINTS_COUNT:
        step = len(elevation_profile) / CHART_POINTS_COUNT
        downsampled = []
        for i in range(CHART_POINTS_COUNT):
            idx = int(i * step)
            # Round X to 1 decimal (100.5 km) and Y to integer (500 m)
            item = elevation_profile[idx]
            downsampled.append({'x': round(item['x'], 1), 'y': int(item['y'])})
        elevation_profile = downsampled

    # --- Stats ---
    moving = gpx.get_moving_data(stopped_speed_threshold=0.5)
    uphill, _ = gpx.get_uphill_downhill()
    
    stats = {
        'distance_km': "{:,.1f}".format(moving.moving_distance / 1000),
        'moving_time_str': format_duration(moving.moving_time), # Fixed Key Name
        'avg_speed': round((moving.moving_distance / moving.moving_time) * 3.6, 1) if moving.moving_time else 0,
        'elevation': "{:,}".format(int(uphill))
    }
    
    return points, stats, json.dumps(elevation_profile)

# --- MAIN ---

def main():
    if not os.path.exists(INPUT_GPX):
        print(f"Error: {INPUT_GPX} not found.")
        return

    print(f"Reading {INPUT_GPX}...")
    with open(INPUT_GPX, 'r', encoding='utf-8') as f:
        gpx = gpxpy.parse(f)

    points, stats, chart_json = process_gpx(gpx)
    
    if not points:
        print("No data found.")
        return

    # Center Map
    avg_lat = sum(p['loc'][0] for p in points) / len(points)
    avg_lon = sum(p['loc'][1] for p in points) / len(points)
    
    print("Generating Map...")
    
    # Dark Mode Base
    m = folium.Map(
        location=[avg_lat, avg_lon], zoom_start=6,
        tiles='https://{s}.basemaps.cartocdn.com/rastertiles/voyager/{z}/{x}/{y}{r}.png',
        attr='&copy; CARTO'
    )

    # Layers
    folium.TileLayer('https://{s}.basemaps.cartocdn.com/dark_all/{z}/{x}/{y}{r}.png', attr='CARTO', name='Dark Mode').add_to(m)
    folium.TileLayer('https://server.arcgisonline.com/ArcGIS/rest/services/World_Imagery/MapServer/tile/{z}/{y}/{x}', attr='Esri', name='Satellite').add_to(m)
    folium.TileLayer('https://{s}.tile-cyclosm.openstreetmap.fr/cyclosm/{z}/{x}/{y}.png', attr='CyclOSM', name='CyclOSM').add_to(m)

    # Draw Segments
    current_segment = []
    segment_idx = 0
    
    for i, point in enumerate(points):
        current_segment.append(point['loc'])
        is_last = (i == len(points) - 1)
        should_break = False
        
        if not is_last:
            diff = points[i+1]['time'] - point['time']
            if diff > timedelta(hours=GAP_THRESHOLD_HOURS):
                should_break = True
        
        if (should_break or is_last) and len(current_segment) > 1:
            color = RED_HUES[segment_idx % len(RED_HUES)]
            start_date = points[i - len(current_segment) + 1]['time'].strftime('%Y-%m-%d')
            
            folium.PolyLine(current_segment, color=color, weight=4, opacity=0.9, tooltip=f"Day {segment_idx+1}: {start_date}").add_to(m)
            
            if should_break: # Jump line
                folium.PolyLine([point['loc'], points[i+1]['loc']], color="#999", weight=2, dash_array='4,8', opacity=0.5).add_to(m)
            
            current_segment = []
            segment_idx += 1

    # Markers
    folium.Marker(points[0]['loc'], icon=folium.Icon(color='green', icon='play'), popup="Start").add_to(m)
    folium.Marker(points[-1]['loc'], icon=folium.Icon(color='black', icon='stop'), popup="End").add_to(m)

    stats['days'] = segment_idx

    # Inject Overlays
    m.get_root().add_child(StatsOverlay(**stats))
    m.get_root().add_child(ChartOverlay(chart_json))

    folium.LayerControl().add_to(m)
    m.save(OUTPUT_MAP)
    print(f"Done! Stats: {stats['distance_km']}km | Elev: {stats['elevation']}m")
    webbrowser.open('file://' + os.path.realpath(OUTPUT_MAP))

if __name__ == "__main__":
    main()