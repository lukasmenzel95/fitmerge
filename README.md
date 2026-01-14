# FitMerge: GPX & FIT File Combiner

A tool to merge multiple Wahoo/Garmin `.fit` files into a single, seamless GPX track. It handles multi-day trips, visualizes data with an interactive map, and generates  elevation profiles.

![Map Preview](preview.png)

## Features
* **Smart Merging:** Concatenates hundreds of `.fit` files chronologically.
* **Gap Handling:** Intelligently visualizes time jumps between rides (e.g., overnight stops).
* **Sensor Data:** Preserves Heart Rate, Cadence, and Temperature data in the GPX export.
* **Interactive Visualization:** Generates a standalone HTML map with:
    * Dark Mode / Satellite / CyclOSM layers.
    * Interactive Elevation Profile (Chart.js).
    * Trip Stats Dashboard (Distance, Moving Time, Elevation).

## Installation

### Prerequisites
* Python 3.8+

### 1. Clone & Setup
```bash
git clone "this repo"
cd fitmerge

# Create Virtual Environment (Recommended)
python -m venv venv

# Activate (Windows)
.\venv\Scripts\Activate

# Activate (Mac/Linux)
source venv/bin/activate

# Install Dependencies
pip install -r requirements.txt
```
### 2. Add your data
Place all your .fit files from your bike computer into the /input_files folder. (If the folder doesn't exist, run python merge_rides.py once to create it).

### 3. Run
Step A: Merge & Simplify This parses the binary files, sorts them chronologically, and creates a lightweight GPX.
```bash
python merge_rides.py
```
Step B: Visualize This generates an interactive HTML map with elevation profiles and stats.
```bash
python merge_rides.py
```
### 🛠 Configuration
You can adjust these variables at the top of the scripts:

SIMPLIFICATION_MARGIN: (merge_rides.py) Accuracy in meters. Higher = smaller file size.

GAP_THRESHOLD_HOURS: (visualize_ride.py) Time gap required to trigger a new ride color.