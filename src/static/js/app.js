// ParkWise App JavaScript
let map;
let heatmapLayer;
let currentData = [];
let peakHoursChart;

let selectedLocation = null;
let geolocationAttempted = false;
let manualSelectionEnabled = false;
let selectedLocationMarker = null;
let locationStatusEl = null;
let addressInputEl = null;
let radiusSliderEl = null;
let radiusValueEl = null;
let nearestLayerGroup = null;

// Initialize the application
document.addEventListener('DOMContentLoaded', function() {
    locationStatusEl = document.getElementById('locationStatus');
    addressInputEl = document.getElementById('addressInput');
    radiusSliderEl = document.getElementById('radiusSlider');
    radiusValueEl = document.getElementById('radiusValue');

    initializeMap();
    populateHourOptions();
    setCurrentDateTime(true);
    loadInitialData();
    setupEventListeners();
    updateRadiusBadge();
});

// Initialize the Leaflet map
function initializeMap() {
    // Chicago coordinates
    const chicagoCoords = [41.8781, -87.6298];
    
    // Create map
    map = L.map('map').setView(chicagoCoords, 12);
    
    // Add dark tile layer
    L.tileLayer('https://{s}.basemaps.cartocdn.com/dark_all/{z}/{x}/{y}{r}.png', {
        attribution: '&copy; <a href="https://www.openstreetmap.org/copyright">OpenStreetMap</a> contributors &copy; <a href="https://carto.com/attributions">CARTO</a>',
        subdomains: 'abcd',
        maxZoom: 19
    }).addTo(map);
    
    console.log('[DEBUG] Map initialized');
    console.log('[DEBUG] Checking for Leaflet.heat plugin...');
    console.log('[DEBUG] typeof L.heatLayer:', typeof L.heatLayer);
    console.log('[DEBUG] typeof L.HeatLayer:', typeof L.HeatLayer);
    
    // Verify Leaflet.heat plugin availability
    if (typeof L.heatLayer !== 'function') {
        console.error('Leaflet.heat plugin failed to load. Heat map will not render.');
        alert('Error: Heat map plugin failed to load. Check internet connection or CDN URL.');
        return;
    }
    
    console.log('[DEBUG] Heat plugin loaded successfully');

    // Initialize empty heatmap layer with higher opacity
    try {
        heatmapLayer = L.heatLayer([], {
            radius: 35,
            blur: 25,
            maxZoom: 17,
            gradient: {
                0.0: 'rgba(0,0,255,0.8)',
                0.25: 'rgba(0,255,255,0.8)',
                0.5: 'rgba(0,255,0,0.8)',
                0.75: 'rgba(255,255,0,0.9)',
                1.0: 'rgba(255,0,0,1)'
            }
        }).addTo(map);
        console.log('[DEBUG] Heatmap layer created:', heatmapLayer);
    } catch (error) {
        console.error('[DEBUG] Error creating heatmap layer:', error);
    }

    // Store markers layer group so we can clear easily
    window._pwMarkerLayer = L.layerGroup().addTo(map);
    map.on('click', handleMapClick);
}

// Populate hour options
function populateHourOptions() {
    const hourSelect = document.getElementById('hourSelect');
    hourSelect.innerHTML = '';

    const allOption = document.createElement('option');
    allOption.value = 'all';
    allOption.textContent = 'All Hours';
    hourSelect.appendChild(allOption);

    for (let i = 0; i < 24; i++) {
        const option = document.createElement('option');
        option.value = i;
        option.textContent = `${i.toString().padStart(2, '0')}:00`;
        hourSelect.appendChild(option);
    }

    hourSelect.value = 'all';
}

// Set current date and time
function setCurrentDateTime(useAll = true) {
    const daySelect = document.getElementById('daySelect');
    const hourSelect = document.getElementById('hourSelect');

    if (useAll) {
        if (daySelect.querySelector('option[value="all"]')) {
            daySelect.value = 'all';
        }
        if (hourSelect.querySelector('option[value="all"]')) {
            hourSelect.value = 'all';
        }
        return;
    }

    const now = new Date();
    const dayOfWeek = now.toLocaleDateString('en-US', { weekday: 'long' });
    const hour = now.getHours();

    daySelect.value = daySelect.querySelector(`option[value="${dayOfWeek}"]`) ? dayOfWeek : 'all';
    hourSelect.value = hourSelect.querySelector(`option[value="${hour}"]`) ? hour : 'all';
}

// Load initial data
function loadInitialData() {
    updateHeatmap();
    loadStatistics();
}

// Setup event listeners
function setupEventListeners() {
    const updateBtn = document.getElementById('updateBtn');
    if (updateBtn) {
        updateBtn.addEventListener('click', updateHeatmap);
    }

    const currentTimeBtn = document.getElementById('currentTimeBtn');
    if (currentTimeBtn) {
        currentTimeBtn.addEventListener('click', function() {
            setCurrentDateTime(false);
            updateHeatmap();
        });
    }

    const findNearestBtn = document.getElementById('findNearestBtn');
    if (findNearestBtn) {
        findNearestBtn.addEventListener('click', onFindNearestClick);
    }

    const geolocationBtn = document.getElementById('useGeolocationBtn');
    if (geolocationBtn) {
        geolocationBtn.addEventListener('click', () => attemptGeolocation());
    }

    const mapPickBtn = document.getElementById('enableMapPickBtn');
    if (mapPickBtn) {
        mapPickBtn.addEventListener('click', () => enableManualSelection('Click the map to choose your search location.'));
    }

    const addressBtn = document.getElementById('useAddressBtn');
    if (addressBtn) {
        addressBtn.addEventListener('click', handleAddressLookup);
    }

    if (addressInputEl) {
        addressInputEl.addEventListener('keydown', (event) => {
            if (event.key === 'Enter') {
                event.preventDefault();
                handleAddressLookup();
            }
        });
    }

    if (radiusSliderEl) {
        radiusSliderEl.addEventListener('input', updateRadiusBadge);
    }

    const locationModalClose = document.querySelector('#locationModal .close');
    if (locationModalClose) {
        locationModalClose.addEventListener('click', closeModal);
    }

    const nearestModal = document.getElementById('nearestModal');
    if (nearestModal) {
        const nearestClose = nearestModal.querySelector('.close');
        if (nearestClose) {
            nearestClose.addEventListener('click', closeNearestModal);
        }
    }

    window.addEventListener('click', function(event) {
        const locationModal = document.getElementById('locationModal');
        if (event.target === locationModal) {
            closeModal();
        }
        if (nearestModal && event.target === nearestModal) {
            closeNearestModal();
        }
    });
}

function updateRadiusBadge() {
    if (!radiusSliderEl || !radiusValueEl) {
        return;
    }
    const value = Number.parseFloat(radiusSliderEl.value || '0.5');
    radiusValueEl.textContent = `${value.toFixed(1)} miles`;
}

async function onFindNearestClick() {
    if (!selectedLocation) {
        if (!geolocationAttempted) {
            const success = await attemptGeolocation();
            if (!success) {
                return;
            }
        } else {
            enableManualSelection('Select a search location by clicking the map or entering an address.', true);
            return;
        }
    }

    if (!selectedLocation) {
        return;
    }

    await fetchNearestParkingOptions();
}

function updateLocationStatus(message, isError = false) {
    if (!locationStatusEl) {
        return;
    }
    locationStatusEl.textContent = message;
    locationStatusEl.classList.toggle('error', Boolean(isError));
}

function enableManualSelection(message, isError = false) {
    manualSelectionEnabled = true;
    if (map) {
        map.getContainer().classList.add('manual-select-mode');
    }
    updateLocationStatus(message || 'Click the map to choose your search location.', isError);
}

function disableManualSelection() {
    manualSelectionEnabled = false;
    if (map) {
        map.getContainer().classList.remove('manual-select-mode');
    }
}

async function attemptGeolocation(showStatus = true) {
    if (showStatus) {
        updateLocationStatus('Requesting your current location...');
    }

    geolocationAttempted = true;

    if (!navigator.geolocation) {
        enableManualSelection('Geolocation is not available. Click the map or enter an address instead.', true);
        return false;
    }

    return new Promise((resolve) => {
        navigator.geolocation.getCurrentPosition(
            (position) => {
                const { latitude, longitude } = position.coords;
                setSelectedLocation(latitude, longitude, 'geolocation', 'your current location');
                showSuccessMessage('Using your current location.');
                resolve(true);
            },
            (error) => {
                console.warn('Geolocation failed:', error);
                enableManualSelection('Could not access your location. Click the map or enter an address instead.', true);
                resolve(false);
            },
            { enableHighAccuracy: true, timeout: 10000, maximumAge: 300000 }
        );
    });
}

function handleMapClick(event) {
    if (!manualSelectionEnabled) {
        return;
    }
    const { lat, lng } = event.latlng;
    setSelectedLocation(lat, lng, 'map', 'map selection');
    showSuccessMessage('Location set from map click.');
}

function setSelectedLocation(lat, lng, source, description) {
    const numericLat = Number(lat);
    const numericLng = Number(lng);
    if (!Number.isFinite(numericLat) || !Number.isFinite(numericLng)) {
        return;
    }

    selectedLocation = {
        lat: numericLat,
        lng: numericLng,
        source: source || 'manual',
        description: description || (source === 'geolocation' ? 'your current location' : 'selected point')
    };

    disableManualSelection();

    if (map) {
        if (!selectedLocationMarker) {
            selectedLocationMarker = L.circleMarker([numericLat, numericLng], {
                radius: 10,
                color: '#ffffff',
                weight: 2,
                fillColor: '#4fbdba',
                fillOpacity: 0.9
            }).addTo(map);
            selectedLocationMarker.bindPopup('Search center');
        } else {
            selectedLocationMarker.setLatLng([numericLat, numericLng]);
        }
        map.setView([numericLat, numericLng], Math.max(map.getZoom(), 13));
    }

    updateLocationStatus(`Using ${selectedLocation.description} (${numericLat.toFixed(4)}, ${numericLng.toFixed(4)})`);
}

async function handleAddressLookup() {
    if (!addressInputEl) {
        return;
    }

    const address = addressInputEl.value.trim();
    if (!address) {
        updateLocationStatus('Enter an address or intersection to search near.', true);
        addressInputEl.focus();
        return;
    }

    updateLocationStatus('Looking up that address...');

    try {
        const response = await fetch(`/api/geocode?address=${encodeURIComponent(address)}`);
        const result = await response.json();

        if (result.status === 'success' && result.data) {
            const { lat, lng, normalizedAddress } = result.data;
            setSelectedLocation(lat, lng, 'address', normalizedAddress || address);
            showSuccessMessage('Location set from address search.');
        } else {
            const message = (result && result.message) ? result.message : 'Unable to resolve that address.';
            enableManualSelection(`${message} Try clicking the map instead.`, true);
        }
    } catch (error) {
        console.error('Error geocoding address:', error);
        enableManualSelection('Address lookup failed. Click the map to choose a location.', true);
    }
}

async function fetchNearestParkingOptions() {
    if (!selectedLocation) {
        return;
    }

    const daySelect = document.getElementById('daySelect');
    const hourSelect = document.getElementById('hourSelect');
    const day = daySelect ? daySelect.value : 'all';
    const hour = hourSelect ? hourSelect.value : 'all';
    const radiusValue = radiusSliderEl ? Number.parseFloat(radiusSliderEl.value || '0.5') : 0.5;

    const params = new URLSearchParams({
        lat: selectedLocation.lat.toString(),
        lng: selectedLocation.lng.toString(),
        radius: radiusValue.toString(),
        day,
        hour,
        limit: '20'
    });

    showNearestLoading(true);

    try {
        const response = await fetch(`/api/nearest-violations?${params.toString()}`);
        const result = await response.json();

        if (result.status === 'success') {
            const records = Array.isArray(result.data) ? result.data : [];
            renderNearestResults(records, result.metadata || { radius: radiusValue, day, hour });
            const summaryMessage = records.length
                ? `Found ${records.length} nearby location${records.length === 1 ? '' : 's'} within ${radiusValue.toFixed(1)} miles.`
                : 'No violation history found near that spot for the selected time window.';
            showSuccessMessage(summaryMessage);
        } else {
            showErrorMessage(result.message || 'Failed to find nearby locations.');
            renderNearestResults([], { radius: radiusValue, day, hour, totalFound: 0 });
        }
    } catch (error) {
        console.error('Error fetching nearest violations:', error);
        showErrorMessage('Error finding nearby locations. Please try again.');
    } finally {
        showNearestLoading(false);
    }
}

function showNearestLoading(isLoading) {
    const btn = document.getElementById('findNearestBtn');
    if (!btn) {
        return;
    }

    if (isLoading) {
        btn.innerHTML = '<span class="loading"></span> Searching...';
        btn.disabled = true;
    } else {
        btn.innerHTML = '<i class="fas fa-location-arrow"></i> Find Nearest Violations';
        btn.disabled = false;
    }
}

function renderNearestResults(results, metadata) {
    const container = document.getElementById('nearestContent');
    if (!container) {
        return;
    }

    const radiusValue = metadata && metadata.radius !== undefined
        ? Number(metadata.radius)
        : (radiusSliderEl ? Number(radiusSliderEl.value) : 0.5);
    const safeRadius = Number.isFinite(radiusValue) ? radiusValue : 0.5;

    const dayValue = metadata && metadata.day !== undefined ? metadata.day : 'all';
    const hourValue = metadata && metadata.hour !== undefined ? metadata.hour : 'all';

    const dayLabel = String(dayValue).toLowerCase() === 'all' ? 'all days' : dayValue;
    let hourLabel = 'all hours';
    if (String(hourValue).toLowerCase() !== 'all') {
        const hourNumber = Number(hourValue);
        hourLabel = Number.isFinite(hourNumber)
            ? `${hourNumber.toString().padStart(2, '0')}:00`
            : `${hourValue}:00`;
    }

    const locationLabel = (selectedLocation && selectedLocation.description)
        ? selectedLocation.description
        : 'your search point';

    let itemsHtml = '';

    if (!results || !results.length) {
        itemsHtml = '<div class="empty-state">No violation history near this spot for the selected window.</div>';
        renderNearestMarkers([]);
    } else {
        itemsHtml = results.map((entry, index) => {
            const distanceValue = Number(entry.distance);
            const formattedDistance = Number.isFinite(distanceValue) ? distanceValue.toFixed(2) : '-';
            const avgFineValue = Number(entry.avgFine);
            const formattedFine = Number.isFinite(avgFineValue) ? avgFineValue.toFixed(2) : '0.00';
            const riskLevel = entry.riskLevel || 'Unknown';
            const riskClass = `${riskLevel.toLowerCase()}-risk`;
            const accent = getRiskAccentColor(riskLevel);

            return `
                <div class="nearest-item ${riskClass}">
                    <div class="nearest-rank">${index + 1}</div>
                    <div class="nearest-details">
                        <h4>${entry.location}</h4>
                        <p class="nearest-meta"><span style="color: ${accent}; font-weight: 600;">${riskLevel} risk</span> &bull; ${entry.violationCount} tickets &bull; ${formattedDistance} mi away</p>
                        <p class="nearest-meta">${entry.violationTypes} violation types &bull; Avg fine $${formattedFine}</p>
                    </div>
                </div>
            `;
        }).join('');
        renderNearestMarkers(results);
    }

    container.innerHTML = `
        <div class="nearest-summary">
            <strong>${locationLabel}</strong> &bull; ${safeRadius.toFixed(1)} mi radius &bull; ${dayLabel}, ${hourLabel}
        </div>
        ${itemsHtml}
    `;

    openNearestModal();
}

function renderNearestMarkers(results) {
    if (!map) {
        return;
    }

    if (!nearestLayerGroup) {
        nearestLayerGroup = L.layerGroup().addTo(map);
    } else {
        nearestLayerGroup.clearLayers();
    }

    (results || []).forEach((entry) => {
        const lat = Number(entry.lat);
        const lng = Number(entry.lng);
        if (!Number.isFinite(lat) || !Number.isFinite(lng)) {
            return;
        }

        const riskLevel = entry.riskLevel || 'Unknown';
        const distanceValue = Number(entry.distance);
        const formattedDistance = Number.isFinite(distanceValue) ? distanceValue.toFixed(2) : '-';
        const accent = getRiskAccentColor(riskLevel);

        const marker = L.circleMarker([lat, lng], {
            radius: 7,
            color: '#ffffff',
            weight: 1,
            fillColor: accent,
            fillOpacity: 0.85
        });

        marker.bindPopup(`
            <div style="color: #1a1a2e;">
                <strong>${entry.location}</strong><br>
                ${formattedDistance} mi away<br>
                ${entry.violationCount} tickets (${riskLevel} risk)
            </div>
        `);

        marker.addTo(nearestLayerGroup);
    });
}

function getRiskAccentColor(level) {
    const normalized = (level || '').toLowerCase();
    if (normalized === 'low') {
        return '#2ecc71';
    }
    if (normalized === 'medium') {
        return '#f1c40f';
    }
    if (normalized === 'high') {
        return '#e74c3c';
    }
    return '#4fbdba';
}

function openNearestModal() {
    const modal = document.getElementById('nearestModal');
    if (modal) {
        modal.style.display = 'block';
    }
}

function closeNearestModal() {
    const modal = document.getElementById('nearestModal');
    if (modal) {
        modal.style.display = 'none';
    }
}

// Update heatmap with new data
async function updateHeatmap() {
    const day = document.getElementById('daySelect').value;
    const hour = document.getElementById('hourSelect').value;
    
    // Show loading state
    showLoading();
    
    try {
        const response = await fetch(`/api/heatmap-data?day=${day}&hour=${hour}`);
        const result = await response.json();
        
        if (result.status === 'success') {
            currentData = result.data;
            updateHeatmapLayer(result.data);
            updateHotspotCount(result.data.length);

            const dayLabel = day === 'all' ? 'all days' : day;
            let hourPhrase;
            if (hour === 'all') {
                hourPhrase = 'across all hours';
            } else {
                const hourNumber = Number(hour);
                const formattedHour = Number.isFinite(hourNumber)
                    ? `${hourNumber.toString().padStart(2, '0')}:00`
                    : `${hour}:00`;
                hourPhrase = `at ${formattedHour}`;
            }

            const message = `Showing ${result.data.length} high-risk locations for ${dayLabel} ${hourPhrase}`.trim();
            showSuccessMessage(message);
        } else {
            showErrorMessage('Failed to load heatmap data');
        }
    } catch (error) {
        console.error('Error fetching heatmap data:', error);
        showErrorMessage('Error loading data. Please try again.');
    } finally {
        hideLoading();
    }
}

// Update the heatmap layer
function updateHeatmapLayer(data) {
    console.log('[DEBUG] updateHeatmapLayer called with', data.length, 'locations');
    console.log('[DEBUG] Sample data:', data.slice(0, 3));
    console.log('[DEBUG] heatmapLayer exists?', !!heatmapLayer);

    if (!heatmapLayer) {
        console.error('[DEBUG] No heatmap layer exists!');
        return;
    }

    const validLocations = data.filter(location => Number.isFinite(location.lat) && Number.isFinite(location.lng));
    console.log('[DEBUG] Valid locations for heatmap:', validLocations.length);

    if (!validLocations.length) {
        window._pwMarkerLayer.clearLayers();
        console.warn('[DEBUG] No valid locations to render on heatmap.');
        return;
    }

    const MAX_HEATMAP_POINTS = 3000;
    let sampledLocations = validLocations;
    if (validLocations.length > MAX_HEATMAP_POINTS) {
        const step = Math.ceil(validLocations.length / MAX_HEATMAP_POINTS);
        sampledLocations = validLocations.filter((_, index) => index % step === 0).slice(0, MAX_HEATMAP_POINTS);
        console.log(`[DEBUG] Downsampled heatmap points from ${validLocations.length} to ${sampledLocations.length}`);
    }

    const maxCount = sampledLocations.reduce((max, location) => Math.max(max, Number(location.count) || 0), 0) || 1;

    const heatmapPoints = sampledLocations.map(location => {
        const normalized = Math.max(Math.min((Number(location.count) || 0) / maxCount, 1), 0.01);
        return {
            coords: [Number(location.lat), Number(location.lng), normalized],
            normalized,
            raw: location
        };
    });

    console.log('[DEBUG] Heatmap data prepared:', heatmapPoints.slice(0, 5));
    console.log('[DEBUG] Data format check - first point:', heatmapPoints[0]);
    console.log('[DEBUG] Heatmap maxCount:', maxCount);

    heatmapLayer.setLatLngs(heatmapPoints.map(point => point.coords));

    heatmapLayer.setOptions({
        max: 1,
        radius: 30,
        blur: 20,
        minOpacity: 0.35
    });

    if (heatmapLayer.redraw) {
        heatmapLayer.redraw();
        console.log('[DEBUG] Called redraw on heatmap layer');
    }

    console.log(`Heatmap updated with ${heatmapPoints.length} points`);

    if (heatmapLayer._canvas) {
        console.log('[DEBUG] Heatmap canvas exists:', heatmapLayer._canvas);
        console.log('[DEBUG] Canvas dimensions:', heatmapLayer._canvas.width, 'x', heatmapLayer._canvas.height);
    } else {
        console.error('[DEBUG] No canvas found for heatmap!');
    }

    window._pwMarkerLayer.clearLayers();

    heatmapPoints.forEach(point => {
        const { raw, normalized, coords } = point;
        if ((raw.count || 0) > 50) {
            const marker = L.circleMarker([coords[0], coords[1]], {
                radius: 8,
                fillColor: getMarkerColor(normalized),
                color: '#ffffff',
                weight: 2,
                opacity: 1,
                fillOpacity: 0.7
            }).addTo(window._pwMarkerLayer);

            marker.bindPopup(`
                <div style="color: #333;">
                    <strong>${raw.location}</strong><br>
                    Violations: ${raw.count}<br>
                    Avg Fine: $${raw.avgFine.toFixed(2)}<br>
                    <button onclick="showLocationDetails('${encodeURIComponent(raw.location)}')">View Details</button>
                </div>
            `);
        }
    });
}

// Get marker color based on intensity
function getMarkerColor(intensity) {
    if (intensity > 0.7) return '#ff0000';
    if (intensity > 0.4) return '#ffff00';
    return '#00ff00';
}

// Load general statistics
async function loadStatistics() {
    try {
        const response = await fetch('/api/statistics');
        const result = await response.json();
        
        if (result.status === 'success') {
            const stats = result.data;
            
            // Update quick stats
            document.getElementById('totalViolations').textContent = formatNumber(stats.totalViolations);
            
            // Calculate average fine from top violations
            const avgFine = stats.topViolations.reduce((sum, v) => sum + parseFloat(v.fine), 0) / stats.topViolations.length;
            document.getElementById('avgFine').textContent = `$${avgFine.toFixed(2)}`;
            
            // Update top violations
            updateTopViolations(stats.topViolations);
            
            // Update peak hours chart
            updatePeakHoursChart(stats.peakHours);
            
            // Update hot locations
            updateHotLocations(stats.hotLocations);
        }
    } catch (error) {
        console.error('Error loading statistics:', error);
    }
}

// Update top violations display
function updateTopViolations(violations) {
    const container = document.getElementById('topViolations');
    container.innerHTML = '';
    
    violations.forEach(violation => {
        const item = document.createElement('div');
        item.className = 'violation-item';
        item.innerHTML = `
            <div class="violation-info">
                <div class="violation-name">${violation.violation_type}</div>
                <div class="violation-count">${formatNumber(violation.count)} tickets</div>
            </div>
            <div class="violation-fine">$${violation.fine}</div>
        `;
        container.appendChild(item);
    });
}

// Update peak hours chart
function updatePeakHoursChart(peakHours) {
    const ctx = document.getElementById('peakHoursChart').getContext('2d');
    
    if (peakHoursChart) {
        peakHoursChart.destroy();
    }
    
    peakHoursChart = new Chart(ctx, {
        type: 'bar',
        data: {
            labels: peakHours.map(h => `${h.hour}:00`),
            datasets: [{
                label: 'Violations',
                data: peakHours.map(h => h.count),
                backgroundColor: 'rgba(79, 189, 186, 0.6)',
                borderColor: 'rgba(79, 189, 186, 1)',
                borderWidth: 2
            }]
        },
        options: {
            responsive: true,
            maintainAspectRatio: false,
            plugins: {
                legend: {
                    display: false
                }
            },
            scales: {
                y: {
                    beginAtZero: true,
                    grid: {
                        color: 'rgba(255, 255, 255, 0.1)'
                    },
                    ticks: {
                        color: '#a8a8a8'
                    }
                },
                x: {
                    grid: {
                        display: false
                    },
                    ticks: {
                        color: '#a8a8a8'
                    }
                }
            }
        }
    });
}

// Update hot locations
function updateHotLocations(locations) {
    const container = document.getElementById('hotLocations');
    container.innerHTML = '';
    
    locations.forEach(location => {
        const item = document.createElement('div');
        item.className = 'location-item';
        item.innerHTML = `
            <div class="violation-info">
                <div class="violation-name">${location.violation_location}</div>
                <div class="violation-count">${formatNumber(location.count)} violations</div>
            </div>
        `;
        item.addEventListener('click', () => showLocationDetails(location.violation_location));
        container.appendChild(item);
    });
}

// Update hotspot count
function updateHotspotCount(count) {
    document.getElementById('hotspotCount').textContent = count;
}

// Show location details
async function showLocationDetails(locationName) {
    const decodedLocation = decodeURIComponent(locationName);
    document.getElementById('modalLocationName').textContent = decodedLocation;
    
    try {
        const response = await fetch(`/api/location-details/${encodeURIComponent(decodedLocation)}`);
        const result = await response.json();
        
        if (result.status === 'success') {
            const data = result.data;
            const modalContent = document.getElementById('modalContent');
            
            modalContent.innerHTML = `
                <h3>Violation Patterns</h3>
                <div class="pattern-grid">
                    ${data.patterns.slice(0, 10).map(p => `
                        <div class="pattern-item">
                            <strong>${p.day_of_week} ${p.hour}:00</strong>
                            <span>${p.count} violations</span>
                            <span>Avg: $${p.avg_fine.toFixed(2)}</span>
                        </div>
                    `).join('')}
                </div>
                
                <h3>Violation Types</h3>
                <div class="violation-types">
                    ${data.violationTypes.map(v => `
                        <div class="type-item">
                            <span>${v.violation_type}</span>
                            <span>${v.count} tickets ($${v.fine})</span>
                        </div>
                    `).join('')}
                </div>
            `;
            
            document.getElementById('locationModal').style.display = 'block';
        }
    } catch (error) {
        console.error('Error loading location details:', error);
    }
}

// Close modal
function closeModal() {
    document.getElementById('locationModal').style.display = 'none';
}

// Utility functions
function formatNumber(num) {
    return num.toString().replace(/\B(?=(\d{3})+(?!\d))/g, ',');
}

function showLoading() {
    const btn = document.getElementById('updateBtn');
    btn.innerHTML = '<span class="loading"></span> Loading...';
    btn.disabled = true;
}

function hideLoading() {
    const btn = document.getElementById('updateBtn');
    btn.innerHTML = '<i class="fas fa-sync-alt"></i> Update Heat Map';
    btn.disabled = false;
}

function showSuccessMessage(message) {
    console.log('Success:', message);
    // Could add a toast notification here
}

function showErrorMessage(message) {
    console.error('Error:', message);
    // Could add a toast notification here
}

// Add some custom styles to the modal content
const style = document.createElement('style');
style.textContent = `
    .pattern-grid {
        display: grid;
        grid-template-columns: repeat(auto-fill, minmax(200px, 1fr));
        gap: 10px;
        margin: 15px 0;
    }
    
    .pattern-item {
        background: #0a0a0a;
        padding: 10px;
        border-radius: 8px;
        display: flex;
        flex-direction: column;
        gap: 5px;
    }
    
    .violation-types {
        display: flex;
        flex-direction: column;
        gap: 10px;
        margin: 15px 0;
    }
    
    .type-item {
        display: flex;
        justify-content: space-between;
        background: #0a0a0a;
        padding: 10px;
        border-radius: 8px;
    }
`;
document.head.appendChild(style); 