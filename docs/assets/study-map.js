/* Interactive study-area map for the Ogun study page.
   Reads data/ogun_subbasins.geojson, data/unit_summary.json and data/rasters/rasters.json (written by
   scripts/make_unit_summary.py and scripts/make_terrain_landcover.py).
   States: loading -> ready, or failed (the page keeps its text and shows a message).
   Shareable view: the chosen variable, context layers and basemap are kept in the URL hash.
   No value is typed here: every number shown is read from the data files. */
(() => {
    'use strict';
    const host = document.getElementById('study-map');
    if (!host) return;
    const status = document.getElementById('study-map-status');
    const legend = document.getElementById('study-map-legend');
    const buttons = Array.from(document.querySelectorAll('[data-var]'));
    const ctxTerrain = document.getElementById('ctx-terrain');
    const ctxLand = document.getElementById('ctx-landcover');
    const setState = (state, msg) => {
        host.dataset.state = state;
        if (status) status.textContent = msg || '';
    };
    setState('loading', 'Loading map…');
    if (typeof L === 'undefined') { setState('failed', 'The map library did not load. The unit values are listed in Table 1.'); return; }

    const VARS = {
        rain: { label: 'Mean rainfall', unit: 'mm per month', ramp: ['#e3eef9', '#08306b'], key: u => u.rain && u.rain.mean, fmt: v => v.toFixed(0), decimals: 0, source: 'CHIRPS, January 2019 to December 2024 (Google Earth Engine export)' },
        soil: { label: 'Soil moisture (0–7 cm)', unit: 'm³ per m³', ramp: ['#f1f5e6', '#3d5a1c'], key: u => u.soil && u.soil.mean, fmt: v => v.toFixed(2), decimals: 2, source: 'ERA5-Land, volumetric water 0–7 cm, 2019–2024' },
        sar: { label: 'Radar inundation index', unit: 'km² per month, Z3–Z4 only', ramp: ['#fde3cf', '#7f2704'], key: u => u.sar && u.sar.mean, fmt: v => v.toFixed(2), decimals: 2, source: 'Sentinel-1 radar water mask, detection uncalibrated, 2019–2024' },
        dw: { label: 'Dynamic World water', unit: 'km² per month; higher in the dry season, not a flood measure', ramp: ['#ebe4f3', '#4a1d6b'], key: u => u.dw && u.dw.mean, fmt: v => v.toFixed(1), decimals: 1, source: 'Dynamic World V1, months with a valid observation, 2019–2024' },
        ndti: { label: 'Lagoon turbidity (NDTI)', unit: 'uncalibrated index, Z5 only', ramp: ['#e4eef3', '#1f4e5f'], key: u => u.ndti && u.ndti.mean, fmt: v => v.toFixed(3), decimals: 3, source: 'Sentinel-2 NDTI over open water, uncalibrated, 2019–2024' },
    };
    const BASEMAPS = {
        light: 'https://server.arcgisonline.com/ArcGIS/rest/services/Canvas/World_Light_Gray_Base/MapServer/tile/{z}/{y}/{x}',
        none: null,
    };
    const params = new URLSearchParams(location.hash.replace(/^#/, ''));
    let current = VARS[params.get('var')] ? params.get('var') : 'rain';
    let basemap = BASEMAPS[params.get('base')] !== undefined ? params.get('base') : 'light';
    const wantTerrain = params.get('terrain') === '1';
    const wantLand = params.get('landcover') === '1';

    const map = L.map(host, { zoomControl: true, attributionControl: true, scrollWheelZoom: false, zoomSnap: 0.25, zoomDelta: 0.5 });
    map.attributionControl.setPrefix(false);
    map.attributionControl.addAttribution('Coordinates: WGS 84 (EPSG:4326)');
    map.createPane('context'); map.getPane('context').style.zIndex = 350;
    let tiles = null;
    function setBasemap(kind) {
        if (tiles) { map.removeLayer(tiles); tiles = null; }
        basemap = kind;
        if (BASEMAPS[kind]) tiles = L.tileLayer(BASEMAPS[kind], { maxZoom: 12, attribution: 'Tiles © Esri — Esri, DeLorme, NAVTEQ' }).addTo(map);
    }
    setBasemap(basemap);
    // keep the map sized to its grid cell when the legend beside it changes height
    // refit to the units unless the reader has already panned or zoomed
    let userMoved = false;
    map.on('dragstart', () => { userMoved = true; });
    host.addEventListener('click', e => { if (e.target.closest('.leaflet-control-zoom')) userMoved = true; });
    if ('ResizeObserver' in window) new ResizeObserver(() => {
        map.invalidateSize();
        if (!userMoved && layer) map.fitBounds(layer.getBounds(), { padding: mapPad() });
    }).observe(host);
    L.control.scale({ metric: true, imperial: false, position: 'bottomleft' }).addTo(map);
    const north = L.control({ position: 'topright' });
    north.onAdd = () => {
        const d = L.DomUtil.create('div', 'north-arrow');
        d.innerHTML = '<svg width="22" height="30" viewBox="0 0 22 30" aria-hidden="true"><path d="M11 0 L19 26 L11 21 L3 26 Z" fill="#111"/></svg><span>N</span>';
        return d;
    };
    north.addTo(map);

    let geo = null, units = null, layer = null, rasters = null, terrainLayer = null, landLayer = null;
    const ramp = (t, [a, b]) => {
        const pa = [1, 3, 5].map(i => parseInt(a.slice(i, i + 2), 16)), pb = [1, 3, 5].map(i => parseInt(b.slice(i, i + 2), 16));
        return `rgb(${pa.map((x, i) => Math.round(x + (pb[i] - x) * t)).join(',')})`;
    };
    const ctxOn = () => (ctxTerrain && ctxTerrain.checked) || (ctxLand && ctxLand.checked);
    const ctxLandOn = () => !!(ctxLand && ctxLand.checked);
    const absentText = v => (v === 'sar' ? 'masked as unreliable (radar, Z1–Z2)' : 'not measured for this unit');
    const lum = c => { const m = /rgb\((\d+),(\d+),(\d+)\)/.exec(c || ''); if (!m) return 1; return (0.2126 * m[1] + 0.7152 * m[2] + 0.0722 * m[3]) / 255; };
    // point well inside a ring (largest distance to the edge), found on a grid
    const labelPoint = ring => {
        const xs = ring.map(p => p[0]), ys = ring.map(p => p[1]);
        const inside = (x, y) => { let c = false; for (let i = 0, j = ring.length - 1; i < ring.length; j = i++) { const [xi, yi] = ring[i], [xj, yj] = ring[j]; if ((yi > y) !== (yj > y) && x < (xj - xi) * (y - yi) / (yj - yi) + xi) c = !c; } return c; };
        const edge = (x, y) => { let d = Infinity; for (let i = 0, j = ring.length - 1; i < ring.length; j = i++) { const [xi, yi] = ring[i], [xj, yj] = ring[j]; const dx = xj - xi, dy = yj - yi; const t = Math.max(0, Math.min(1, ((x - xi) * dx + (y - yi) * dy) / (dx * dx + dy * dy || 1))); d = Math.min(d, Math.hypot(xi + t * dx - x, yi + t * dy - y)); } return d; };
        let best = null, bd = -1;
        const n = 24;
        for (let i = 0; i <= n; i++) for (let j = 0; j <= n; j++) {
            const x = Math.min(...xs) + (Math.max(...xs) - Math.min(...xs)) * i / n, y = Math.min(...ys) + (Math.max(...ys) - Math.min(...ys)) * j / n;
            if (!inside(x, y)) continue;
            const d = edge(x, y); if (d > bd) { bd = d; best = [x, y]; }
        }
        return best || [(Math.min(...xs) + Math.max(...xs)) / 2, (Math.min(...ys) + Math.max(...ys)) / 2];
    };
    let labelLayers = [];
    let titleCtl = null;
    // leave room at the bottom for the attribution on narrow screens so it does not cover the lagoon zone
    const mapPad = () => (host.clientWidth < 600 ? [18, 56] : [18, 18]);

    function valuesFor(v) {
        const catch4 = geo.features.filter(f => f.properties.zone_id !== 'Z5').map(f => VARS[v].key(units[f.properties.zone_id] || {})).filter(x => typeof x === 'number');
        const src = catch4.length >= 2 ? catch4 : geo.features.map(f => VARS[v].key(units[f.properties.zone_id] || {})).filter(x => typeof x === 'number');
        return { min: Math.min(...src), max: Math.max(...src) };
    }

    function styleFor(f, v, range) {
        const x = VARS[v].key(units[f.properties.zone_id] || {});
        const dashed = f.properties.zone_id === 'Z5';
        const op = ctxLandOn() ? 0 : 0.85;
        if (typeof x !== 'number') {
            return { fillColor: '#ffffff', fillOpacity: ctxLandOn() ? 0 : 0.9, color: '#6b6b6b', weight: 1.2, dashArray: '4 4' };
        }
        // Z5 is outside the catchment: neutral fill, except for the turbidity variable where it carries the value
        if (f.properties.zone_id === 'Z5' && v !== 'ndti') return { fillColor: '#ebe9e2', fillOpacity: 0.9, color: '#6b6b6b', weight: 1.2, dashArray: '6 4' };
        const t = range.max > range.min ? (x - range.min) / (range.max - range.min) : 0.5;
        return { fillColor: ramp(Math.min(1, Math.max(0, t)), VARS[v].ramp), fillOpacity: op, color: '#3d3d3d', weight: 1.2, dashArray: dashed ? '6 4' : null };
    }

    function legendBlock(v, range) {
        const cfg = VARS[v];
        const n = geo.features.filter(f => typeof VARS[v].key(units[f.properties.zone_id] || {}) === 'number').length;
        const src = `<p class="legend-source">Source: ${cfg.source}.</p>`;
        if (n === 1) {
            const only = geo.features.find(f => typeof VARS[v].key(units[f.properties.zone_id] || {}) === 'number');
            return `<p class="legend-title">${cfg.label}<span>${cfg.unit}</span></p>
                <p class="legend-key">Only ${only.properties.zone_id} has a value: ${cfg.fmt(range.min)} ${cfg.unit.split(',')[0]}.</p>
                <p class="legend-key"><span class="hatch-key"></span>${absentText(current)}</p>${src}`;
        }
        const stops = [0, 0.25, 0.5, 0.75, 1].map(t => ramp(t, cfg.ramp));
        const ticks = [0, 0.25, 0.5, 0.75, 1].map(t => (range.min + (range.max - range.min) * t).toFixed(cfg.decimals));
        const end = range.max > range.min ? `<p class="legend-source">Colour scale set by Z1–Z4; Z5 is shown at the nearest end.</p>` : '';
        return `<p class="legend-title">${cfg.label}<span>${cfg.unit}</span></p>
            <div class="legend-bar" style="background:linear-gradient(to right, ${stops.join(',')})"></div>
            <div class="legend-ticks">${ticks.map(t => `<span>${t}</span>`).join('')}</div>
            <p class="legend-key"><span class="hatch-key"></span>${absentText(current)}</p>${end}${src}`;
    }

    function terrainBlock() {
        if (!ctxTerrain || !ctxTerrain.checked || !rasters) return '';
        const e = rasters.terrain;
        return `<div class="legend-extra"><p class="legend-title">Terrain<span>Copernicus DEM, 30 m; hillshade with elevation tint</span></p>
            <div class="legend-bar" style="background:linear-gradient(to right, #f3efe2, #6b4f2a)"></div>
            <div class="legend-ends"><span>${e.elevation_min_m.toFixed(0)} m</span><span>${e.elevation_max_m.toFixed(0)} m</span></div>
            <p class="legend-source">Source: ${e.source}. Elevation 0 m is water in the DEM, not land.</p></div>`;
    }

    function unitsKey() {
        return `<div class="legend-extra"><p class="legend-title">Units</p><ul class="lc-list">
            <li><span class="zbadge">Z1</span>Upper Ogun headwaters</li>
            <li><span class="zbadge">Z2</span>Oyan–Ofiki tributary</li>
            <li><span class="zbadge">Z3</span>Middle Ogun mainstem</li>
            <li><span class="zbadge">Z4</span>Lower Ogun alluvial corridor</li>
            <li><span class="zbadge dashed">Z5</span>Lagoon zone, outside the catchment (dashed outline)</li></ul></div>`;
    }

    function landcoverBlock() {
        if (!ctxLand || !ctxLand.checked || !rasters) return '';
        const rows = rasters.landcover.legend.map(c =>
            `<li><span class="swatch" style="background:${c.colour}"></span>${c.label}<span class="share">${c.share_pct.toFixed(1)}%</span></li>`).join('');
        return `<div class="legend-extra"><p class="legend-title">Land cover, 2021<span>share of the catchment area</span></p>
            <ul class="lc-list">${rows}</ul>
            <p class="legend-source">Shown for Z1–Z4 only; the data fills are hidden while this layer is on. Source: ${rasters.landcover.source}. Overall accuracy for Africa ${rasters.landcover.accuracy_africa_pct}% (${rasters.landcover.citation}).</p></div>`;
    }

    function renderLegend(v, range) {
        legend.innerHTML = legendBlock(v, range) + terrainBlock() + landcoverBlock() + unitsKey();
    }

    function drawContext() {
        if (terrainLayer) { map.removeLayer(terrainLayer); terrainLayer = null; }
        if (landLayer) { map.removeLayer(landLayer); landLayer = null; }
        if (!rasters) return;
        const b = [[rasters.bounds.south, rasters.bounds.west], [rasters.bounds.north, rasters.bounds.east]];
        if (ctxTerrain && ctxTerrain.checked) terrainLayer = L.imageOverlay('data/rasters/terrain.png', b, { pane: 'context', opacity: 0.9, alt: 'Terrain: hillshade of the catchment' }).addTo(map);
        if (ctxLand && ctxLand.checked) landLayer = L.imageOverlay('data/rasters/landcover.png', b, { pane: 'context', opacity: 0.9, alt: 'Land cover 2021 for the catchment' }).addTo(map);
    }

    function share() {
        const p = new URLSearchParams({ var: current, base: basemap });
        if (ctxTerrain && ctxTerrain.checked) p.set('terrain', '1');
        if (ctxLand && ctxLand.checked) p.set('landcover', '1');
        history.replaceState(null, '', '#' + p.toString());
        return location.href;
    }

    function draw(v) {
        current = v;
        const range = valuesFor(v);
        if (layer) map.removeLayer(layer);
        layer = L.geoJSON(geo, {
            style: f => styleFor(f, v, range),
            onEachFeature: (f, lyr) => {
                const id = f.properties.zone_id, u = units[id] || {};
                const x = VARS[v].key(u);
                const shown = typeof x === 'number' ? `${VARS[v].fmt(x)} ${VARS[v].unit.split(',')[0]}` : absentText(v);
                lyr.bindPopup(`<strong>${id} · ${f.properties.zone_name}</strong><br>${VARS[v].label}: ${shown}<br>Area ${Math.round(f.properties.area_km2).toLocaleString('en-GB')} km²`);

                lyr.on('add', () => {
                    const el = lyr.getElement();
                    if (!el || el.dataset.keyboard) return;
                    el.dataset.keyboard = '1';
                    el.setAttribute('tabindex', '0');
                    el.setAttribute('role', 'button');
                    el.setAttribute('aria-label', `${id} ${f.properties.zone_name}: ${VARS[v].label}, ${typeof VARS[v].key(u) === 'number' ? VARS[v].fmt(VARS[v].key(u)) + ' ' + VARS[v].unit.split(',')[0] : 'not interpreted'}. Press Enter for details.`);
                    el.addEventListener('keydown', e => { if (e.key === 'Enter' || e.key === ' ') { e.preventDefault(); lyr.openPopup(); } });
                });
                lyr.on('mouseover', () => lyr.setStyle({ weight: 3.5 }));
                lyr.on('mouseout', () => lyr.setStyle({ weight: 2 }));
            },
        }).addTo(map);
        labelLayers.forEach(l => map.removeLayer(l)); labelLayers = [];
        geo.features.forEach(f => {
            const id = f.properties.zone_id;
            const polys = f.geometry.type === 'Polygon' ? [f.geometry.coordinates] : f.geometry.coordinates;
            const ring = polys[0][0].map(([x, y]) => [x, y]);
            const pt = labelPoint(ring);
            const fill = styleFor(f, v, range).fillColor;
            const dark = lum(fill) < 0.55 && ctxLandOn() === false;
            const tt = L.tooltip({ permanent: true, direction: id === 'Z5' ? 'right' : 'center', offset: id === 'Z5' ? [10, 0] : [0, 0], className: 'unit-label' + (id === 'Z5' ? ' z5' : '') + (dark ? ' on-dark' : ''), interactive: false })
                .setLatLng([pt[1], pt[0]]).setContent(id);
            // unit names are not written on the map: the key and the hover popups identify each unit
        });
        map.fitBounds(layer.getBounds(), { padding: mapPad() });
        if (!titleCtl) {
            titleCtl = L.control({ position: 'topleft' });
            titleCtl.onAdd = () => { const d = L.DomUtil.create('div', 'map-title'); d.id = 'map-title'; return d; };
            titleCtl.addTo(map);
        }
        document.getElementById('map-title').textContent = VARS[v].label + ', 2019–2024';
        renderLegend(v, range);
        buttons.forEach(b => { const on = b.dataset.var === v; b.setAttribute('aria-pressed', on ? 'true' : 'false'); });
        share();
    }

    function refresh() {
        drawContext();
        if (geo) draw(current);
    }

    Promise.all([
        fetch('data/ogun_subbasins.geojson').then(r => { if (!r.ok) throw new Error(r.status); return r.json(); }),
        fetch('data/unit_summary.json').then(r => { if (!r.ok) throw new Error(r.status); return r.json(); }),
        fetch('data/rasters/rasters.json').then(r => { if (!r.ok) throw new Error(r.status); return r.json(); }).catch(() => null),
    ]).then(([g, s, rs]) => {
        geo = g; units = s.units; rasters = rs;
        if (ctxTerrain) ctxTerrain.checked = wantTerrain && !!rasters;
        if (ctxLand) ctxLand.checked = wantLand && !!rasters;
        if (ctxTerrain && !rasters) ctxTerrain.disabled = true;
        if (ctxLand && !rasters) ctxLand.disabled = true;
        drawContext();
        draw(current);
        setState('ready', '');
    }).catch(() => {
        setState('failed', 'The map data could not be loaded. The unit values are listed in Table 1.');
    });

    buttons.forEach(b => b.addEventListener('click', () => { if (geo) draw(b.dataset.var); }));
    [ctxTerrain, ctxLand].forEach(c => c && c.addEventListener('change', () => { if (geo) { drawContext(); draw(current); } }));
    window.addEventListener('resize', () => { map.invalidateSize(); if (layer) map.fitBounds(layer.getBounds(), { padding: mapPad() }); });
})();
