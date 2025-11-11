#!/usr/bin/env python
"""
ParkWise Application Starter
Run this script to start the ParkWise web application
"""

import os
import sys
import webbrowser
from threading import Timer

# Add the current directory to Python path
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

def open_browser():
    """Open the web browser after a short delay"""
    webbrowser.open('http://localhost:5000')

if __name__ == '__main__':
    print("=" * 60)
    print("ParkWise - Smart Parking Risk Analysis")
    print("=" * 60)
    print("\nStarting the application...")
    print("The browser will open automatically in 3 seconds.")
    print("If it doesn't, navigate to: http://localhost:5000")
    print("\nPress Ctrl+C to stop the server.\n")
    
    # Open browser after 3 seconds
    Timer(3, open_browser).start()
    
    # Import and run the Flask app
    from app import app
    app.run(debug=True, port=5000, use_reloader=False) 