import requests
import json

# Test the API endpoints
base_url = "http://localhost:5000"

print("Testing ParkWise API Endpoints")
print("=" * 50)

# Test heatmap-data endpoint
try:
    response = requests.get(f"{base_url}/api/heatmap-data?day=Monday&hour=12")
    print(f"\n1. Heatmap Data Endpoint")
    print(f"   Status: {response.status_code}")
    
    if response.status_code == 200:
        data = response.json()
        print(f"   Status: {data.get('status')}")
        print(f"   Total Locations: {len(data.get('data', []))}")
        
        if data.get('data'):
            print(f"\n   First 3 locations:")
            for i, location in enumerate(data['data'][:3]):
                print(f"   {i+1}. {location['location']}")
                print(f"      Lat: {location['lat']}, Lng: {location['lng']}")
                print(f"      Count: {location['count']}, Intensity: {location['intensity']}")
                print(f"      Avg Fine: ${location['avgFine']}")
                
            # Check data validity
            print(f"\n   Data Validation:")
            valid_coords = all(
                -90 <= loc['lat'] <= 90 and -180 <= loc['lng'] <= 180 
                for loc in data['data']
            )
            print(f"   - All coordinates valid: {valid_coords}")
            
            has_counts = all(loc['count'] > 0 for loc in data['data'])
            print(f"   - All locations have counts: {has_counts}")
            
    else:
        print(f"   Error: {response.text}")
        
except Exception as e:
    print(f"   Connection Error: {e}")

# Test statistics endpoint
try:
    response = requests.get(f"{base_url}/api/statistics")
    print(f"\n2. Statistics Endpoint")
    print(f"   Status: {response.status_code}")
    
    if response.status_code == 200:
        data = response.json()
        if data.get('status') == 'success':
            stats = data.get('data', {})
            print(f"   Total Violations: {stats.get('totalViolations', 'N/A')}")
            print(f"   Top Violations: {len(stats.get('topViolations', []))} types")
            print(f"   Peak Hours: {len(stats.get('peakHours', []))} entries")
            print(f"   Hot Locations: {len(stats.get('hotLocations', []))} locations")
    else:
        print(f"   Error: {response.text}")
        
except Exception as e:
    print(f"   Connection Error: {e}")

print("\n" + "=" * 50)
print("If connection errors, make sure Flask app is running on port 5000") 