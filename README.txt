ParkWise is a Chicago-focused parking intelligence platform built to stop "mystery ticket" surprises. Instead of
just showing open spots, it mines the city’s historical violation database to map out when and where enforcement hits
hardest—down to the hour and intersection.

What it does
- Turns millions of Chicago parking tickets into interactive, time-aware heat maps.
- Predicts how long a spot stays “safe” on weekdays vs. weekends based on past citations.
- Highlights patterns across neighbourhoods, violation types, and fine amounts so drivers can plan ahead.
- Surfaces crowd-sourced enforcement reports (planned) to layer in real-time risk.
- Delivers a responsive web UI optimized for phones, tablets, and dashboards.

Under the hood

- Requires a local SQL Server Express instance (.\SQLEXPRESS) with the ParkingTickets database restored.
- Flask backend serves the API and UI, with pandas handling the heavy query lifting.
- A C acceleration module handles the nearest-spot geospatial math and risk ranking—zero allocations in the hot path
once warmed up.

Performance setup
- cd src/native
- python setup.py build_ext --inplace

That one-time build compiles the c_nearest kernel in-place; the Flask app detects it automatically and falls back to
pure Python if it’s missing.

Permission is hereby granted to use, copy, modify, and distribute this software 
for personal and educational purposes only. Commercial use is strictly prohibited 
without written permission from the author.

THE SOFTWARE IS PROVIDED "AS IS", WITHOUT WARRANTY OF ANY KIND.
