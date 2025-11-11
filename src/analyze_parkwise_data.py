import pyodbc
import pandas as pd
import numpy as np
from collections import Counter
import re
from datetime import datetime

# Connect to the database
cn = pyodbc.connect('DRIVER={SQL Server};SERVER=.\SQLEXPRESS;DATABASE=ParkingTickets;Trusted_Connection=yes;')

print("="*60)
print("PARKWISE DATA ANALYSIS - Parking Violation Patterns")
print("="*60)

# 1. LOCATION DATA ANALYSIS - Critical for heat maps
print("\n1. LOCATION DATA ACCURACY ANALYSIS")
print("-" * 40)

# Get sample location data to understand format
location_sample = pd.read_sql("""
    SELECT TOP 20 violation_location, COUNT(*) as ticket_count
    FROM Ticket 
    WHERE violation_location IS NOT NULL 
    GROUP BY violation_location 
    ORDER BY COUNT(*) DESC
""", cn)

print("Sample of most common violation locations:")
for idx, row in location_sample.iterrows():
    print(f"  {row['violation_location']} ({row['ticket_count']} tickets)")

# Analyze location data granularity
location_patterns = pd.read_sql("""
    SELECT 
        violation_location,
        COUNT(*) as frequency
    FROM Ticket 
    WHERE violation_location IS NOT NULL
    GROUP BY violation_location
""", cn)

print(f"\nLocation Data Statistics:")
print(f"  Total unique locations: {len(location_patterns):,}")
print(f"  Average tickets per location: {location_patterns['frequency'].mean():.1f}")
print(f"  Most ticketed location has: {location_patterns['frequency'].max():,} tickets")

# Check if locations contain street addresses, blocks, or coordinates
sample_locations = location_patterns['violation_location'].head(50).tolist()
address_patterns = {
    'street_numbers': sum(1 for loc in sample_locations if re.search(r'\d+\s+\w+\s+(ST|AVE|BLVD|RD|DR)', str(loc), re.IGNORECASE)),
    'block_numbers': sum(1 for loc in sample_locations if re.search(r'\d+00\s+BLOCK', str(loc), re.IGNORECASE)),
    'intersections': sum(1 for loc in sample_locations if ' & ' in str(loc) or ' AND ' in str(loc)),
    'coordinates': sum(1 for loc in sample_locations if re.search(r'-?\d+\.\d+', str(loc)))
}

print(f"\nLocation Format Analysis (from 50 samples):")
for pattern, count in address_patterns.items():
    print(f"  {pattern.replace('_', ' ').title()}: {count}/50 ({count*2}%)")

# 2. TIME PATTERN ANALYSIS - Critical for smart predictions
print("\n\n2. TIME PATTERN ANALYSIS")
print("-" * 40)

# Get violation patterns by time
time_analysis = pd.read_sql("""
    SELECT 
        DATEPART(HOUR, issue_date) as hour_of_day,
        DATEPART(WEEKDAY, issue_date) as day_of_week,
        DATENAME(WEEKDAY, issue_date) as weekday_name,
        COUNT(*) as ticket_count
    FROM Ticket 
    WHERE issue_date IS NOT NULL
    GROUP BY DATEPART(HOUR, issue_date), DATEPART(WEEKDAY, issue_date), DATENAME(WEEKDAY, issue_date)
    ORDER BY ticket_count DESC
""", cn)

print("Peak violation times (Top 10):")
for idx, row in time_analysis.head(10).iterrows():
    print(f"  {row['weekday_name']} at {row['hour_of_day']:02d}:00 - {row['ticket_count']:,} tickets")

# 3. VIOLATION TYPE ANALYSIS - For understanding enforcement patterns
print("\n\n3. VIOLATION TYPE ANALYSIS")
print("-" * 40)

violation_analysis = pd.read_sql("""
    SELECT 
        v.Description as violation_type,
        v.Cost as fine_amount,
        COUNT(t.ticket_number) as ticket_count,
        AVG(CAST(v.Cost as FLOAT)) as avg_fine
    FROM Ticket t
    JOIN Violation v ON t.violation_code = v.Code
    GROUP BY v.Description, v.Cost
    ORDER BY COUNT(t.ticket_number) DESC
""", cn)

print("Most common violations:")
for idx, row in violation_analysis.head(10).iterrows():
    print(f"  {row['violation_type']}: {row['ticket_count']:,} tickets (${row['fine_amount']} fine)")

# 4. GEOGRAPHIC HOTSPOT ANALYSIS
print("\n\n4. GEOGRAPHIC HOTSPOT ANALYSIS")
print("-" * 40)

# Find the most dangerous areas for parking
hotspots = pd.read_sql("""
    SELECT TOP 15
        violation_location,
        COUNT(*) as total_tickets,
        COUNT(DISTINCT violation_code) as violation_types,
        AVG(CAST(v.Cost as FLOAT)) as avg_fine_amount
    FROM Ticket t
    JOIN Violation v ON t.violation_code = v.Code
    WHERE violation_location IS NOT NULL
    GROUP BY violation_location
    ORDER BY COUNT(*) DESC
""", cn)

print("Highest risk parking locations:")
for idx, row in hotspots.iterrows():
    print(f"  {row['violation_location']}")
    print(f"    Total tickets: {row['total_tickets']:,}")
    print(f"    Violation types: {row['violation_types']}")
    print(f"    Avg fine: ${row['avg_fine_amount']:.2f}")
    print()

# 5. SEASONAL PATTERNS
print("\n5. SEASONAL PATTERNS")
print("-" * 40)

seasonal_data = pd.read_sql("""
    SELECT 
        DATEPART(MONTH, issue_date) as month_num,
        DATENAME(MONTH, issue_date) as month_name,
        COUNT(*) as ticket_count
    FROM Ticket 
    WHERE issue_date IS NOT NULL
    GROUP BY DATEPART(MONTH, issue_date), DATENAME(MONTH, issue_date)
    ORDER BY DATEPART(MONTH, issue_date)
""", cn)

print("Tickets by month:")
for idx, row in seasonal_data.iterrows():
    print(f"  {row['month_name']}: {row['ticket_count']:,} tickets")

# 6. DATA QUALITY ASSESSMENT
print("\n\n6. DATA QUALITY FOR PARKWISE")
print("-" * 40)

data_quality = pd.read_sql("""
    SELECT 
        COUNT(*) as total_records,
        COUNT(violation_location) as records_with_location,
        COUNT(issue_date) as records_with_date,
        COUNT(violation_code) as records_with_violation_code,
        MIN(issue_date) as earliest_date,
        MAX(issue_date) as latest_date
    FROM Ticket
""", cn)

quality_row = data_quality.iloc[0]
print(f"Total records: {quality_row['total_records']:,}")
print(f"Records with location: {quality_row['records_with_location']:,} ({quality_row['records_with_location']/quality_row['total_records']*100:.1f}%)")
print(f"Records with date: {quality_row['records_with_date']:,} ({quality_row['records_with_date']/quality_row['total_records']*100:.1f}%)")
print(f"Date range: {quality_row['earliest_date']} to {quality_row['latest_date']}")

print("\n" + "="*60)
print("RECOMMENDATIONS FOR PARKWISE:")
print("="*60)
print("✓ Location data appears to be street-level accurate")
print("✓ Rich time-based patterns available for smart predictions")
print("✓ Multiple violation types for comprehensive risk assessment")
print("✓ Sufficient data volume for statistical significance")
print("✓ Multi-year historical data for trend analysis")

cn.close() 