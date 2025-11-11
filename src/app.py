from flask import Flask, render_template, jsonify, request
from flask_cors import CORS
import pyodbc
import pandas as pd
import json
from datetime import datetime
from pathlib import Path
import math
import hashlib
import random
from collections import OrderedDict

app = Flask(__name__)
CORS(app)

BASE_DIR = Path(__file__).resolve().parent
DATA_DIR = BASE_DIR / 'data'
HEATMAP_OVERALL_PATH = DATA_DIR / 'heatmap_overall.pkl'
HEATMAP_DB_LIMIT = 1000
_heatmap_overall_cache = None
HEATMAP_SUMMARY_PATH = DATA_DIR / 'heatmap_overall_summary.pkl'
HEATMAP_OVERALL_PAYLOAD_PATH = DATA_DIR / 'heatmap_overall_payload.json'
HEATMAP_QUERY_CACHE_LIMIT = 32
HEATMAP_QUERY_RESULT_LIMIT = 2000
_heatmap_overall_payload_cache = None
_heatmap_query_cache = OrderedDict()
_geocode_cache = {}




def build_heatmap_payload(df):
    if df is None:
        return []

    if not isinstance(df, pd.DataFrame):
        df = pd.DataFrame(df)

    if df.empty:
        return []

    working_df = df[['violation_location', 'violation_count', 'avg_fine', 'violation_types']].copy()
    working_df['violation_location'] = working_df['violation_location'].fillna('').astype(str)

    working_df['violation_count'] = pd.to_numeric(working_df['violation_count'], errors='coerce').fillna(0).astype(int)
    working_df['avg_fine'] = pd.to_numeric(working_df['avg_fine'], errors='coerce').fillna(0.0)
    working_df['violation_types'] = pd.to_numeric(working_df['violation_types'], errors='coerce').fillna(0).astype(int)

    max_count = working_df['violation_count'].max()
    if pd.isna(max_count) or max_count <= 0:
        max_count = 1
    else:
        max_count = float(max_count)

    coords = working_df['violation_location'].map(geocode_location)
    working_df['lat'] = [safe_float(coord[0], default=None) if coord else None for coord in coords]
    working_df['lng'] = [safe_float(coord[1], default=None) if coord else None for coord in coords]

    valid_df = working_df[working_df['lat'].notna() & working_df['lng'].notna()].copy()
    if valid_df.empty:
        return []

    payload = []
    for row in valid_df.itertuples(index=False):
        intensity = float(min(row.violation_count / max_count, 1.0))
        payload.append({
            'location': row.violation_location,
            'count': int(row.violation_count),
            'avgFine': float(row.avg_fine),
            'violationTypes': int(row.violation_types),
            'intensity': intensity,
            'lat': float(row.lat),
            'lng': float(row.lng)
        })

    return payload

def get_overall_heatmap_df():
    global _heatmap_overall_cache
    if _heatmap_overall_cache is not None:
        return _heatmap_overall_cache

    source_path = None
    if HEATMAP_SUMMARY_PATH.exists():
        source_path = HEATMAP_SUMMARY_PATH
    elif HEATMAP_OVERALL_PATH.exists():
        source_path = HEATMAP_OVERALL_PATH

    if source_path is None:
        return None

    df = pd.read_pickle(source_path)
    try:
        df['violation_count'] = pd.to_numeric(df['violation_count'], errors='coerce').fillna(0).astype('int32', copy=False)
        df['violation_types'] = pd.to_numeric(df['violation_types'], errors='coerce').fillna(0).astype('int16', copy=False)
        df['avg_fine'] = pd.to_numeric(df['avg_fine'], errors='coerce').fillna(0.0).astype('float32', copy=False)
    except Exception:
        pass

    if source_path == HEATMAP_OVERALL_PATH:
        summary_df = df.nlargest(HEATMAP_DB_LIMIT, 'violation_count').reset_index(drop=True)
        try:
            summary_df.to_pickle(HEATMAP_SUMMARY_PATH)
        except Exception:
            pass
        df = summary_df
    elif len(df) > HEATMAP_DB_LIMIT:
        df = df.nlargest(HEATMAP_DB_LIMIT, 'violation_count').reset_index(drop=True)

    _heatmap_overall_cache = df
    return _heatmap_overall_cache

def get_overall_heatmap_payload():
    global _heatmap_overall_payload_cache
    if _heatmap_overall_payload_cache is not None:
        return _heatmap_overall_payload_cache

    if HEATMAP_OVERALL_PAYLOAD_PATH.exists():
        try:
            with HEATMAP_OVERALL_PAYLOAD_PATH.open('r', encoding='utf-8') as fp:
                cached_payload = json.load(fp)
            _heatmap_overall_payload_cache = cached_payload
            return cached_payload
        except Exception:
            pass

    df = get_overall_heatmap_df()
    if df is None or df.empty:
        _heatmap_overall_payload_cache = []
        return []

    if len(df) > HEATMAP_DB_LIMIT:
        df = df.nlargest(HEATMAP_DB_LIMIT, 'violation_count').reset_index(drop=True)

    payload = build_heatmap_payload(df)

    try:
        HEATMAP_OVERALL_PAYLOAD_PATH.parent.mkdir(parents=True, exist_ok=True)
        with HEATMAP_OVERALL_PAYLOAD_PATH.open('w', encoding='utf-8') as fp:
            json.dump(payload, fp)
    except Exception:
        pass

    _heatmap_overall_payload_cache = payload
    return payload

def safe_float(value, default=0.0):
    try:
        if value is None:
            return default
        result = float(value)
        if math.isnan(result) or math.isinf(result):
            return default
        return result
    except (TypeError, ValueError):
        return default

def safe_int(value, default=0):
    try:
        result = safe_float(value, default=None)
        if result is None:
            return default
        return int(result)
    except (TypeError, ValueError, OverflowError):
        return default

# Database connection string
DB_CONNECTION = 'DRIVER={SQL Server};SERVER=.\SQLEXPRESS;DATABASE=ParkingTickets;Trusted_Connection=yes;'

def _fetch_heatmap_dataframe(day_filter, hour_filter):
    cache_key = (day_filter or 'ALL', hour_filter if hour_filter is not None else 'ALL')
    if cache_key in _heatmap_query_cache:
        _heatmap_query_cache.move_to_end(cache_key)
        return _heatmap_query_cache[cache_key]

    conn = get_db_connection()
    try:
        query = f"""
        SELECT TOP {HEATMAP_QUERY_RESULT_LIMIT}
            t.violation_location,
            COUNT(*) as violation_count,
            AVG(CAST(v.Cost as FLOAT)) as avg_fine,
            COUNT(DISTINCT t.violation_code) as violation_types
        FROM Ticket t
        JOIN Violation v ON t.violation_code = v.Code
        WHERE t.violation_location IS NOT NULL
            AND (? IS NULL OR DATENAME(WEEKDAY, t.issue_date) = ?)
            AND (? IS NULL OR DATEPART(HOUR, t.issue_date) = ?)
        GROUP BY t.violation_location
        ORDER BY COUNT(*) DESC
        """
        params = [day_filter, day_filter, hour_filter, hour_filter]
        df = pd.read_sql(query, conn, params=params)
    finally:
        conn.close()

    try:
        df['violation_count'] = pd.to_numeric(df['violation_count'], errors='coerce').fillna(0).astype('int32', copy=False)
        df['violation_types'] = pd.to_numeric(df['violation_types'], errors='coerce').fillna(0).astype('int16', copy=False)
        df['avg_fine'] = pd.to_numeric(df['avg_fine'], errors='coerce').fillna(0.0).astype('float32', copy=False)
    except Exception:
        pass

    _heatmap_query_cache[cache_key] = df
    _heatmap_query_cache.move_to_end(cache_key)
    if len(_heatmap_query_cache) > HEATMAP_QUERY_CACHE_LIMIT:
        _heatmap_query_cache.popitem(last=False)
    return df


def get_db_connection():
    """Create and return a database connection"""
    return pyodbc.connect(DB_CONNECTION)

@app.route('/')
def index():
    """Render the main page"""
    return render_template('index.html')

@app.route('/api/heatmap-data')

def get_heatmap_data():
    """Get parking violation data for heat map visualization"""
    # Get query parameters
    day_of_week = request.args.get('day', datetime.now().strftime('%A'))
    hour = request.args.get('hour', datetime.now().hour)

    day_filter = None if str(day_of_week).lower() == 'all' else day_of_week
    hour_filter = None
    if str(hour).lower() != 'all':
        try:
            hour_filter = safe_int(hour, default=None)
        except Exception:
            hour_filter = None

    try:
        # Reuse precomputed payload when no filters constrain the dataset
        if day_filter is None and hour_filter is None:
            heatmap_data = get_overall_heatmap_payload()
            return jsonify({
                'status': 'success',
                'data': heatmap_data,
                'metadata': {
                    'day': day_of_week,
                    'hour': hour,
                    'totalLocations': len(heatmap_data)
                }
            })

        df = _fetch_heatmap_dataframe(day_filter, hour_filter)
        print(f"[DEBUG] /api/heatmap-data => day={day_of_week}, hour={hour}, records={len(df)}")

        if df.empty:
            return jsonify({
                'status': 'success',
                'data': [],
                'metadata': {
                    'day': day_of_week,
                    'hour': hour,
                    'totalLocations': 0
                }
            })

        heatmap_data = build_heatmap_payload(df)

        return jsonify({
            'status': 'success',
            'data': heatmap_data,
            'metadata': {
                'day': day_of_week,
                'hour': hour,
                'totalLocations': len(heatmap_data)
            }
        })

    except Exception as e:
        return jsonify({
            'status': 'error',
            'message': str(e)
        }), 500
@app.route('/api/statistics')
def get_statistics():
    """Get overall parking violation statistics"""
    try:
        conn = get_db_connection()

        # Get various statistics
        stats = {}

        # Total violations
        total_query = "SELECT COUNT(*) as total FROM Ticket"
        total_df = pd.read_sql(total_query, conn)
        stats['totalViolations'] = safe_int(total_df.iloc[0]['total'])
        print(f"[DEBUG] /api/statistics => totalViolations={stats['totalViolations']}")

        # Most common violations
        violations_query = """
        SELECT TOP 5
            v.Description as violation_type,
            COUNT(*) as count,
            v.Cost as fine
        FROM Ticket t
        JOIN Violation v ON t.violation_code = v.Code
        GROUP BY v.Description, v.Cost
        ORDER BY COUNT(*) DESC
        """
        top_violations_df = pd.read_sql(violations_query, conn)
        stats['topViolations'] = []
        for record in top_violations_df.to_dict('records'):
            stats['topViolations'].append({
                'violation_type': record['violation_type'],
                'count': safe_int(record['count']),
                'fine': safe_float(record['fine'])
            })

        # Peak hours
        peak_hours_query = """
        SELECT TOP 5
            DATEPART(HOUR, issue_date) as hour,
            COUNT(*) as count
        FROM Ticket
        WHERE issue_date IS NOT NULL
        GROUP BY DATEPART(HOUR, issue_date)
        ORDER BY COUNT(*) DESC
        """
        peak_hours_df = pd.read_sql(peak_hours_query, conn)
        stats['peakHours'] = []
        for record in peak_hours_df.to_dict('records'):
            stats['peakHours'].append({
                'hour': safe_int(record['hour']),
                'count': safe_int(record['count'])
            })

        # Hottest locations
        hot_locations_query = """
            SELECT TOP 10
                violation_location,
                COUNT(*) as count
            FROM Ticket
            WHERE violation_location IS NOT NULL
            GROUP BY violation_location
            ORDER BY COUNT(*) DESC
        """
        hot_locations_df = pd.read_sql(hot_locations_query, conn)
        stats['hotLocations'] = []
        for record in hot_locations_df.to_dict('records'):
            stats['hotLocations'].append({
                'violation_location': record['violation_location'],
                'count': safe_int(record['count'])
            })

        conn.close()

        return jsonify({
            'status': 'success',
            'data': stats
        })

    except Exception as e:
        return jsonify({
            'status': 'error',
            'message': str(e)
        }), 500

@app.route('/api/location-details/<location>')
def get_location_details(location):
    """Get detailed information about a specific location"""
    try:
        conn = get_db_connection()

        # Get violation patterns for this location
        query = """
        SELECT
            DATENAME(WEEKDAY, t.issue_date) as day_of_week,
            DATEPART(HOUR, t.issue_date) as hour,
            COUNT(*) as count,
            AVG(CAST(v.Cost as FLOAT)) as avg_fine
        FROM Ticket t
        JOIN Violation v ON t.violation_code = v.Code
        WHERE t.violation_location = ?
            AND t.issue_date IS NOT NULL
        GROUP BY DATENAME(WEEKDAY, t.issue_date), DATEPART(HOUR, t.issue_date)
        ORDER BY COUNT(*) DESC
        """

        df = pd.read_sql(query, conn, params=[location])

        # Get violation types for this location
        types_query = """
        SELECT
            v.Description as violation_type,
            COUNT(*) as count,
            v.Cost as fine
        FROM Ticket t
        JOIN Violation v ON t.violation_code = v.Code
        WHERE t.violation_location = ?
        GROUP BY v.Description, v.Cost
        ORDER BY COUNT(*) DESC
        """

        types_df = pd.read_sql(types_query, conn, params=[location])

        conn.close()

        return jsonify({
            'status': 'success',
            'data': {
                'location': location,
                'patterns': df.to_dict('records'),
                'violationTypes': types_df.to_dict('records')
            }
        })

    except Exception as e:
        return jsonify({
            'status': 'error',
            'message': str(e)
        }), 500

def calculate_distance(lat1, lng1, lat2, lng2):
    """
    Calculate distance in miles between two coordinates using Haversine formula
    """
    # Convert decimal degrees to radians
    lat1_rad = math.radians(lat1)
    lng1_rad = math.radians(lng1)
    lat2_rad = math.radians(lat2)
    lng2_rad = math.radians(lng2)

    # Haversine formula
    dlat = lat2_rad - lat1_rad
    dlng = lng2_rad - lng1_rad
    a = math.sin(dlat/2)**2 + math.cos(lat1_rad) * math.cos(lat2_rad) * math.sin(dlng/2)**2
    c = 2 * math.asin(math.sqrt(a))

    # Radius of Earth in miles
    radius_miles = 3959

    return c * radius_miles

@app.route('/api/geocode')
def geocode_address():
    """Resolve a user-supplied address or intersection into coordinates."""
    address = request.args.get('address', '').strip()
    if not address:
        return jsonify({
            'status': 'error',
            'message': 'address parameter is required'
        }), 400

    lat, lng = geocode_location(address)
    if lat is None or lng is None:
        return jsonify({
            'status': 'error',
            'message': 'Unable to resolve address'
        }), 404

    return jsonify({
        'status': 'success',
        'data': {
            'lat': float(lat),
            'lng': float(lng),
            'normalizedAddress': address
        }
    })


@app.route('/api/nearest-violations')
def get_nearest_violations():
    """Find nearby parking options ranked by relative risk."""
    try:
        # Get query parameters
        lat = request.args.get('lat', type=float)
        lng = request.args.get('lng', type=float)
        radius = request.args.get('radius', default=0.5, type=float)
        limit = request.args.get('limit', default=20, type=int)
        day = request.args.get('day', default='all')
        hour = request.args.get('hour', default='all')

        # Validate required parameters
        if lat is None or lng is None:
            return jsonify({
                'status': 'error',
                'message': 'lat and lng parameters are required'
            }), 400

        day_filter = None if not day or str(day).lower() == 'all' else day
        hour_filter = None
        if hour is not None and str(hour).lower() != 'all':
            try:
                hour_filter = safe_int(hour, default=None)
            except Exception:
                hour_filter = None

        conn = get_db_connection()

        query = """
        SELECT
            t.violation_location,
            COUNT(*) as violation_count,
            AVG(CAST(v.Cost as FLOAT)) as avg_fine,
            COUNT(DISTINCT t.violation_code) as violation_types
        FROM Ticket t
        JOIN Violation v ON t.violation_code = v.Code
        WHERE t.violation_location IS NOT NULL
            AND (? IS NULL OR DATENAME(WEEKDAY, t.issue_date) = ?)
            AND (? IS NULL OR DATEPART(HOUR, t.issue_date) = ?)
        GROUP BY t.violation_location
        """
        params = [day_filter, day_filter, hour_filter, hour_filter]

        try:
            df = pd.read_sql(query, conn, params=params)
        finally:
            conn.close()

        if df.empty:
            return jsonify({
                'status': 'success',
                'data': [],
                'metadata': {
                    'userLat': lat,
                    'userLng': lng,
                    'radius': radius,
                    'day': day,
                    'hour': hour,
                    'totalFound': 0
                }
            })

        results = []
        for _, row in df.iterrows():
            location_lat, location_lng = geocode_location(row['violation_location'])
            if location_lat is None or location_lng is None:
                continue

            distance = calculate_distance(lat, lng, location_lat, location_lng)
            if distance > radius:
                continue

            violation_count = safe_int(row['violation_count'], default=0)
            avg_fine = safe_float(row['avg_fine'], default=0.0)
            violation_types = safe_int(row['violation_types'], default=0)

            results.append({
                'location': row['violation_location'],
                'lat': float(location_lat),
                'lng': float(location_lng),
                'distance': round(distance, 2),
                'violationCount': violation_count,
                'avgFine': round(float(avg_fine), 2),
                'violationTypes': violation_types
            })

        if not results:
            return jsonify({
                'status': 'success',
                'data': [],
                'metadata': {
                    'userLat': lat,
                    'userLng': lng,
                    'radius': radius,
                    'day': day,
                    'hour': hour,
                    'totalFound': 0
                }
            })

        counts = [entry['violationCount'] for entry in results]
        min_count = min(counts)
        max_count = max(counts) or 1

        for entry in results:
            if max_count == min_count:
                percentile = 0.0
            else:
                percentile = (entry['violationCount'] - min_count) / max(1, (max_count - min_count))

            if percentile <= 0.33:
                level = 'Low'
            elif percentile <= 0.66:
                level = 'Medium'
            else:
                level = 'High'

            entry['riskScore'] = round(percentile, 4)
            entry['riskLevel'] = level

        results.sort(key=lambda x: (x['riskScore'], x['distance']))
        results = results[:max(limit, 1)]

        return jsonify({
            'status': 'success',
            'data': results,
            'metadata': {
                'userLat': lat,
                'userLng': lng,
                'radius': radius,
                'day': day,
                'hour': hour,
                'totalFound': len(results)
            }
        })

    except Exception as e:
        return jsonify({
            'status': 'error',
            'message': str(e)
        }), 500

def _deterministic_offsets(location_key, scale):
    digest = hashlib.sha1(location_key.encode('utf-8')).hexdigest()
    seed = int(digest[:16], 16)
    rng = random.Random(seed)
    return rng.uniform(-scale, scale), rng.uniform(-scale, scale)


def geocode_location(location_str):
    """
    Convert location string to lat/lng coordinates
    This is a simplified version - in production, use Google Geocoding API
    """
    chicago_lat = 41.8781
    chicago_lng = -87.6298

    if location_str is None:
        location_str = ''

    location_text = str(location_str).strip()
    if not location_text:
        return chicago_lat, chicago_lng

    location_key = location_text.upper()

    cached = _geocode_cache.get(location_key)
    if cached is not None:
        return cached

    street_coords = {
        'MICHIGAN': (41.8755, -87.6244),
        'STATE': (41.8819, -87.6278),
        'LASALLE': (41.8755, -87.6321),
        'CLARK': (41.8822, -87.6309),
        'WABASH': (41.8755, -87.6256),
        'RUSH': (41.8904, -87.6248),
        'DEARBORN': (41.8789, -87.6298),
        'FRANKLIN': (41.8833, -87.6356),
        'WELLS': (41.8822, -87.6340),
        'ADAMS': (41.8794, -87.6278)
    }

    for street, coords in street_coords.items():
        if street in location_key:
            lat_offset, lng_offset = _deterministic_offsets(location_key, 0.005)
            result = (float(coords[0] + lat_offset), float(coords[1] + lng_offset))
            _geocode_cache[location_key] = result
            return result

    lat_offset, lng_offset = _deterministic_offsets(location_key, 0.1)
    result = (float(chicago_lat + lat_offset), float(chicago_lng + lng_offset))
    _geocode_cache[location_key] = result
    return result

if __name__ == '__main__':
    app.run(debug=True, port=5000) 
