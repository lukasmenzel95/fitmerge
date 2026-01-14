import os
import pandas as pd
import gpxpy
import gpxpy.gpx
import fitdecode
from datetime import datetime
from concurrent.futures import ProcessPoolExecutor
from tqdm import tqdm

#!/usr/bin/env python3

# --- CONFIGURATION ---
INPUT_FOLDER = 'input_files'
OUTPUT_FILE = 'merged_ride.gpx'
SIMPLIFICATION_MARGIN = 10.0  # Meters

def get_safe(frame, field_name):
    """
    Safely extracts a value from a FIT frame.
    Returns None if the field is missing, preventing crashes.
    """
    if frame.has_field(field_name):
        return frame.get_value(field_name)
    return None

def extract_fit_data(file_path):
    """
    Reads a FIT file and extracts GPS points.
    Runs in parallel.
    """
    points = []
    try:
        with fitdecode.FitReader(file_path) as fit:
            for frame in fit:
                if frame.frame_type == fitdecode.FIT_FRAME_DATA and frame.name == 'record':
                    
                    # 1. Essential Check: GPS
                    if not (frame.has_field('position_lat') and frame.has_field('position_long')):
                        continue

                    try:
                        # 2. Extract Lat/Lon safely
                        lat_semicircles = get_safe(frame, 'position_lat')
                        lon_semicircles = get_safe(frame, 'position_long')
                        
                        if lat_semicircles is None or lon_semicircles is None:
                            continue

                        # Conversion factor for Wahoo/Garmin (180 / 2^31)
                        COORD_FACTOR = 8.381903171539307e-08 
                        
                        # 3. Extract Optional Fields (using the safe helper)
                        # We prefer 'enhanced_altitude' if available, otherwise 'altitude'
                        ele = get_safe(frame, 'enhanced_altitude')
                        if ele is None:
                            ele = get_safe(frame, 'altitude')

                        points.append({
                            'timestamp': get_safe(frame, 'timestamp'),
                            'lat': lat_semicircles * COORD_FACTOR,
                            'lon': lon_semicircles * COORD_FACTOR,
                            'ele': ele,
                            'hr': get_safe(frame, 'heart_rate'),
                            'cad': get_safe(frame, 'cadence'),
                            'temp': get_safe(frame, 'temperature')
                        })
                    except Exception:
                        continue
                        
    except Exception as e:
        # If a file is truly corrupt, we skip it
        return []

    return points

def create_gpx_with_extensions(df):
    gpx = gpxpy.gpx.GPX()
    gpx_track = gpxpy.gpx.GPXTrack()
    gpx.tracks.append(gpx_track)
    gpx_segment = gpxpy.gpx.GPXTrackSegment()
    gpx_track.segments.append(gpx_segment)
    
    for row in tqdm(df.itertuples(), total=len(df), desc="Generating GPX Points", unit="pts"):
        point = gpxpy.gpx.GPXTrackPoint(
            latitude=row.lat,
            longitude=row.lon,
            elevation=row.ele if pd.notnull(row.ele) else None,
            time=row.timestamp
        )
        
        # Add Extensions (HR, Cadence, Temp)
        from xml.etree import ElementTree
        
        has_ext = False
        gpx_extension_node = ElementTree.Element('gpxtpx:TrackPointExtension')
        gpx_extension_node.set('xmlns:gpxtpx', 'http://www.garmin.com/xmlschemas/TrackPointExtension/v1')

        if pd.notnull(row.hr):
            has_ext = True
            hr_node = ElementTree.SubElement(gpx_extension_node, 'gpxtpx:hr')
            hr_node.text = str(int(row.hr))
        
        if pd.notnull(row.cad):
            has_ext = True
            cad_node = ElementTree.SubElement(gpx_extension_node, 'gpxtpx:cad')
            cad_node.text = str(int(row.cad))
            
        if pd.notnull(row.temp):
            has_ext = True
            temp_node = ElementTree.SubElement(gpx_extension_node, 'gpxtpx:atemp')
            temp_node.text = str(row.temp)
            
        if has_ext:
            point.extensions.append(gpx_extension_node)

        gpx_segment.points.append(point)
        
    return gpx, gpx_track

def main():
    if not os.path.exists(INPUT_FOLDER):
        os.makedirs(INPUT_FOLDER)
        print(f"Created '{INPUT_FOLDER}'. Please put your .fit files there.")
        return

    files = [os.path.join(INPUT_FOLDER, f) for f in os.listdir(INPUT_FOLDER) if f.lower().endswith('.fit')]
    if not files:
        print("No .fit files found.")
        return

    print(f"Found {len(files)} files. Starting parallel processing...")

    all_data = []
    with ProcessPoolExecutor() as executor:
        results = list(tqdm(executor.map(extract_fit_data, files), total=len(files), unit="file"))
        for file_result in results:
            all_data.extend(file_result)

    if not all_data:
        print("No valid data extracted. Please check debug_fit output again.")
        return

    print("Sorting and merging timestamps...")
    df = pd.DataFrame(all_data)
    df.sort_values(by='timestamp', inplace=True)
    df.drop_duplicates(subset=['timestamp'], inplace=True)
    
    print(f"Total merged points: {len(df)}")

    gpx, gpx_track = create_gpx_with_extensions(df)

    original_count = gpx_track.get_points_no()
    print(f"Simplifying track (Margin: {SIMPLIFICATION_MARGIN} meters)...")
    
    try:
        gpx.simplify(SIMPLIFICATION_MARGIN)
        final_count = gpx_track.get_points_no()
        reduction = (1 - (final_count / original_count)) * 100
        print(f"Points reduced from {original_count} to {final_count} ({reduction:.1f}% smaller)")
    except Exception as e:
        print(f"Simplification error: {e}")

    print(f"Saving to {OUTPUT_FILE}...")
    with open(OUTPUT_FILE, "w", encoding="utf-8") as f:
        f.write(gpx.to_xml())
    
    print("Success!")

if __name__ == "__main__":
    main()