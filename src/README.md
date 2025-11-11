# ParkWise Web Application

This is the web application for ParkWise - a smart parking risk analysis tool for Chicago.

## Prerequisites

1. **Python 3.8 or higher**
2. **SQL Server Express** with the ParkingTickets database restored
3. **Required Python packages** (see requirements.txt)

## Installation

1. Install the required Python packages:
   ```bash
   cd src
   pip install -r requirements.txt
   ```

2. Make sure your SQL Server Express is running and the ParkingTickets database is restored.

## Native Acceleration (Optional)

The `/api/nearest-violations` endpoint can offload its distance and ranking work to a C extension for lower latency.

```bash
cd src/native
python setup.py build_ext --inplace
```

This produces `c_nearest.*.pyd` alongside `c_nearest.c`. The Flask app will automatically detect and use it; if it is missing, the pure-Python fallback remains active.

## Running the Application

There are two ways to run the application:

### Option 1: Using the run script
```bash
python run.py
```

### Option 2: Direct Flask run
```bash
python app.py
```

The application will start on `http://localhost:5000`

## Features

- **Interactive Heat Map**: Shows parking violation hotspots based on day and time
- **Real-time Updates**: Select any day of the week and hour to see violation patterns
- **Statistics Dashboard**: View top violations, peak hours, and high-risk locations
- **Location Details**: Click on any location to see detailed violation patterns
- **Responsive Design**: Works on desktop and mobile devices

## How to Use

1. **Select Day and Time**: Use the dropdown menus to select a day of the week and hour
2. **Update Heat Map**: Click the "Update Heat Map" button to refresh the visualization
3. **Use Current Time**: Click "Use Current Time" to automatically set to current day/hour
4. **Explore Statistics**: View the statistics panel on the right for insights
5. **Click Locations**: Click on high-risk locations in the list or on the map for details

## Troubleshooting

### Database Connection Error
- Ensure SQL Server Express is running
- Check that the database name is "ParkingTickets"
- Verify Windows Authentication is enabled

### No Data Showing
- Check that the database has been properly restored
- Verify the tables (Ticket, Violation, etc.) exist in the database

### Port Already in Use
- Change the port in `app.py` or `run.py` from 5000 to another port

## Architecture

- **Backend**: Flask (Python) with SQL Server database
- **Frontend**: HTML5, CSS3, JavaScript
- **Map**: Leaflet.js with heatmap plugin
- **Charts**: Chart.js for statistics visualization
- **Styling**: Custom CSS with modern dark theme 
