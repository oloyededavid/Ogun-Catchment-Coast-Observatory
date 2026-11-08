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
    const ctxRivers = document.getElementById('ctx-rivers');
    const ctxRiversNote = document.getElementById('ctx-rivers-note');
    const basemapSel = document.getElementById('basemap-select');
    const shareBtn = document.getElementById('share-view');
    const shareStatus = document.getElementById('share-status');
    const setState = (state, msg) => {
        host.dataset.state = state;
        if (status) status.textContent = msg || '';
    };
    setState('loading', 'Loading map…');
    if (typeof L === 'undefined') { setState('failed', 'The map library did not load. The unit values are listed in Table 1.'); return; }

    const VARS = {
        rain: { label: 'Mean rainfall', unit: 'mm per month', ramp: ['#e3eef9', '#08306b'], key: u => u.rain && u.rain.mean, fmt: v => v.toFixed(0), decimals: 0, source: 'CHIRPS, January 2019 to December 2024 (Google Earth Engine export)' },
        wet: { label: 'Wet-season rainfall', unit: 'mm per month, April–October', ramp: ['#e3eef9', '#08306b'], key: u => u.rain_wet_season_mean, fmt: v => v.toFixed(0), decimals: 0, source: 'CHIRPS, April–October months, 2019–2024' },
        soil: { label: 'Soil moisture (0–7 cm)', unit: 'm³ per m³', ramp: ['#f5f0e1', '#5a4a1f'], key: u => u.soil && u.soil.mean, fmt: v => v.toFixed(2), decimals: 2, source: 'ERA5-Land, volumetric water 0–7 cm, 2019–2024' },
        sar: { label: 'Radar inundation index', unit: 'km² per month, Z3–Z4 only', ramp: ['#fde3cf', '#7f2704'], key: u => u.sar && u.sar.mean, fmt: v => v.toFixed(2), decimals: 2, source: 'Sentinel-1 radar index, uncalibrated, 2019–2024' },
        dw: { label: 'Dynamic World flooding', unit: 'km² per month', ramp: ['#ebe4f3', '#4a1d6b'], key: u => u.dw && u.dw.mean, fmt: v => v.toFixed(1), decimals: 1, source: 'Dynamic World V1, months with a valid observation, 2019–2024' },
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

    const map = L.map(host, { zoomControl: true, attributionControl: true, scrollWheelZoom: false });
    map.attributionControl.setPrefix(false);
    map.attributionControl.addAttribution('Coordinates: WGS 84 (EPSG:4326)');
    map.createPane('context'); map.getPane('context').style.zIndex = 350;
    let tiles = null;
    function setBasemap(kind) {
        if (tiles) { map.removeLayer(tiles); tiles = null; }
        basemap = kind;
        if (BASEMAPS[kind]) tiles = L.tileLayer(BASEMAPS[kind], { maxZoom: 12, attribution: 'Basemap © Esri' }).addTo(map);
    }
    setBasemap(basemap);
    if (basemapSel) basemapSel.value = basemap;
    L.control.scale({ metric: true, imperial: false, position: 'bottomleft' }).addTo(map);
    const north = L.control({ position: 'topright' });
    north.onAdd = () => {
        const d = L.DomUtil.create('div', 'north-arrow');
        d.innerHTML = '<svg width="22" height="30" viewBox="0 0 22 30" aria-hidden="true"><path d="M11 0 L19 26 L11 21 L3 26 Z" fill="#111"/></svg><span>N</span>';
        return d;
    };
    north.addTo(map);

    let geo = null, units = null, layer = null, rasters = null, terrainLayer = null, landLayer = null, riverLayer = null, rivers = null;
    const ramp = (t, [a, b]) => {
        const pa = [1, 3, 5].map(i => parseInt(a.slice(i, i + 2), 16)), pb = [1, 3, 5].map(i => parseInt(b.slice(i, i + 2), 16));
        return `rgb(${pa.map((x, i) => Math.round(x + (pb[i] - x) * t)).join(',')})`;
    };
    const ctxOn = () => (ctxTerrain && ctxTerrain.checked) || (ctxLand && ctxLand.checked) || (ctxRivers && ctxRivers.checked);

    function valuesFor(v) {
        const vals = geo.features.map(f => VARS[v].key(units[f.properties.zone_id] || {})).filter(x => typeof x === 'number');
        return { min: Math.min(...vals), max: Math.max(...vals) };
    }

    function styleFor(f, v, range) {
        const x = VARS[v].key(units[f.properties.zone_id] || {});
        const dashed = f.properties.zone_id === 'Z5';
        const op = ctxOn() ? 0.5 : 0.85;
        if (typeof x !== 'number') {
            return { fillColor: '#ffffff', fillOpacity: ctxOn() ? 0.35 : 0.9, color: '#6b6b6b', weight: 1.2, dashArray: '4 4' };
        }
        const t = range.max > range.min ? (x - range.min) / (range.max - range.min) : 0.5;
        return { fillColor: ramp(Math.min(1, Math.max(0, t)), VARS[v].ramp), fillOpacity: op, color: f.properties.role_color, weight: 2, dashArray: dashed ? '6 4' : null };
    }

    function legendBlock(v, range) {
        const cfg = VARS[v];
        const n = geo.features.filter(f => typeof VARS[v].key(units[f.properties.zone_id] || {}) === 'number').length;
        const src = `<p class="legend-source">Source: ${cfg.source}.</p>`;
        if (n === 1) {
            const only = geo.features.find(f => typeof VARS[v].key(units[f.properties.zone_id] || {}) === 'number');
            return `<p class="legend-title">${cfg.label}<span>${cfg.unit}</span></p>
                <p class="legend-key">Only ${only.properties.zone_id} has a value: ${cfg.fmt(range.min)} ${cfg.unit.split(',')[0]}.</p>
                <p class="legend-key"><span class="hatch-key"></span>Not interpreted or not observed</p>${src}`;
        }
        const stops = [0, 0.25, 0.5, 0.75, 1].map(t => ramp(t, cfg.ramp));
        const lo = range.min.toFixed(cfg.decimals), hi = range.max.toFixed(cfg.decimals);
        return `<p class="legend-title">${cfg.label}<span>${cfg.unit}</span></p>
            <div class="legend-bar" style="background:linear-gradient(to right, ${stops.join(',')})"></div>
            <div class="legend-ends"><span>${lo}</span><span>${hi}</span></div>
            <p class="legend-key"><span class="hatch-key"></span>Not interpreted or not observed</p>${src}`;
    }

    function landcoverBlock() {
        if (!ctxLand || !ctxLand.checked || !rasters) return '';
        const rows = rasters.landcover.legend.map(c =>
            `<li><span class="swatch" style="background:${c.colour}"></span>${c.label}<span class="share">${c.share_pct.toFixed(1)}%</span></li>`).join('');
        return `<div class="legend-extra"><p class="legend-title">Land cover, 2021<span>share of the catchment area</span></p>
            <ul class="lc-list">${rows}</ul>
            <p class="legend-source">Source: ${rasters.landcover.source}. Overall accuracy for Africa ${rasters.landcover.accuracy_africa_pct}% (${rasters.landcover.citation}).</p></div>`;
    }

    function renderLegend(v, range) {
        legend.innerHTML = legendBlock(v, range) + landcoverBlock();
    }

    function drawContext() {
        if (terrainLayer) { map.removeLayer(terrainLayer); terrainLayer = null; }
        if (landLayer) { map.removeLayer(landLayer); landLayer = null; }
        if (riverLayer) { map.removeLayer(riverLayer); riverLayer = null; }
        if (rivers && ctxRivers && ctxRivers.checked) riverLayer = L.geoJSON(rivers, { pane: 'context', interactive: false, style: f => ({ color: '#1f4e5f', weight: Math.max(1, Math.min(3, (f.properties && f.properties.ORD_STRA ? f.properties.ORD_STRA : 3) - 2)), opacity: 0.9 }) }).addTo(map);
        if (!rasters) return;
        const b = [[rasters.bounds.south, rasters.bounds.west], [rasters.bounds.north, rasters.bounds.east]];
        if (ctxTerrain && ctxTerrain.checked) terrainLayer = L.imageOverlay('data/rasters/terrain.png', b, { pane: 'context', opacity: 0.9, alt: 'Terrain: hillshade of the catchment' }).addTo(map);
        if (ctxLand && ctxLand.checked) landLayer = L.imageOverlay('data/rasters/landcover.png', b, { pane: 'context', opacity: 0.9, alt: 'Land cover 2021 for the catchment' }).addTo(map);
    }

    function share() {
        const p = new URLSearchParams({ var: current, base: basemap });
        if (ctxTerrain && ctxTerrain.checked) p.set('terrain', '1');
        if (ctxLand && ctxLand.checked) p.set('landcover', '1');
        if (ctxRivers && ctxRivers.checked) p.set('rivers', '1');
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
                const shown = typeof x === 'number' ? `${VARS[v].fmt(x)} ${VARS[v].unit.split(',')[0]}` : 'not interpreted for this unit';
                lyr.bindPopup(`<strong>${id} · ${f.properties.zone_name}</strong><br>${VARS[v].label}: ${shown}<br>Area ${Math.round(f.properties.area_km2).toLocaleString('en-GB')} km²`);
                lyr.bindTooltip(id, { permanent: true, direction: 'center', className: 'unit-label', interactive: false });
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
        map.fitBounds(layer.getBounds(), { padding: [18, 18] });
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
        fetch('data/ogun_rivers.geojson').then(r => { if (!r.ok) throw new Error(r.status); return r.json(); }).catch(() => null),
    ]).then(([g, s, rs, rv]) => {
        geo = g; units = s.units; rasters = rs; rivers = rv;
        if (ctxRivers && rivers) { ctxRivers.disabled = false; if (ctxRiversNote) ctxRiversNote.textContent = ''; ctxRivers.checked = params.get('rivers') === '1'; }
        if (ctxTerrain) ctxTerrain.checked = wantTerrain && !!rasters;
        if (ctxLand) ctxLand.checked = wantLand && !!rasters;
        if (ctxTerrain && !rasters) ctxTerrain.disabled = true;
        if (ctxLand && !rasters) ctxLand.disabled = true;
        drawContext();
        draw(current);
        setState('ready', 'Click a unit for its values. Radar values are not shown for the units Z1 and Z2.');
    }).catch(() => {
        setState('failed', 'The map data could not be loaded. The unit values are listed in Table 1.');
    });

    buttons.forEach(b => b.addEventListener('click', () => { if (geo) draw(b.dataset.var); }));
    [ctxTerrain, ctxLand, ctxRivers].forEach(c => c && c.addEventListener('change', () => { if (geo) { drawContext(); draw(current); } }));
    if (basemapSel) basemapSel.addEventListener('change', () => { setBasemap(basemapSel.value); share(); });
    if (shareBtn) shareBtn.addEventListener('click', () => {
        const url = share();
        const done = () => { if (shareStatus) shareStatus.textContent = 'Link copied.'; };
        if (navigator.clipboard && navigator.clipboard.writeText) navigator.clipboard.writeText(url).then(done, () => { if (shareStatus) shareStatus.textContent = url; });
        else if (shareStatus) shareStatus.textContent = url;
    });
})();
