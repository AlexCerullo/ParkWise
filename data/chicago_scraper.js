const axios = require('axios');
const fs = require('fs');

/**
 * Simple rate limiter that waits given milliseconds
 */
const sleep = (ms) => new Promise(resolve => setTimeout(resolve, ms));

/**
 * Fetch parking violation data from Chicago's Open Data API.
 * Supports pagination via limit and offset parameters.
 * Filters by date range and bounding box for downtown area.
 */
async function fetchViolations({
  startDate,
  endDate,
  limit = 1000,
  maxPages = 10,
  bbox = null, // [west, south, east, north]
  appToken = null,
  delay = 1000
}) {
  const baseUrl = 'https://data.cityofchicago.org/resource/sbc2-2car.json';
  let allData = [];
  for (let page = 0; page < maxPages; page++) {
    const offset = page * limit;
    const params = {
      '$limit': limit,
      '$offset': offset,
      '$order': 'violation_date DESC',
      '$where': `violation_date >= '${startDate}' and violation_date <= '${endDate}'`
    };
    if (bbox) {
      // Socrata supports within_box with latitude/longitude
      params['$where'] += ` and within_box(location, ${bbox[1]}, ${bbox[0]}, ${bbox[3]}, ${bbox[2]})`;
    }
    const headers = {};
    if (appToken) headers['X-App-Token'] = appToken;

    try {
      const response = await axios.get(baseUrl, { params, headers });
      const data = response.data.map(item => ({
        violation_date: item.violation_date,
        violation_time: item.violation_time,
        violation_location: item.violation_location,
        violation_code: item.violation_code,
        fine_amount: item.fine_amount,
        latitude: item.latitude,
        longitude: item.longitude,
      }));
      if (data.length === 0) break;
      allData = allData.concat(data);
    } catch (err) {
      console.error('Error fetching page', page, err.message);
      break;
    }

    await sleep(delay); // rate limit
  }
  return allData;
}

async function run() {
  const startDate = process.env.START_DATE || '2024-06-01';
  const endDate = process.env.END_DATE || '2025-06-01';
  const bbox = [-87.644, 41.875, -87.620, 41.890]; // downtown Chicago bounding box

  const data = await fetchViolations({ startDate, endDate, bbox, limit: 1000, maxPages: 5 });
  fs.writeFileSync('chicago_violations.json', JSON.stringify(data, null, 2));
  console.log(`Saved ${data.length} records to chicago_violations.json`);
}

if (require.main === module) {
  run();
}
