/* Interactive study-area map for the Ogun study page.
   Reads data/ogun_subbasins.geojson and data/unit_summary.json (written by scripts/make_unit_summary.py).
   States: loading -> ready, or failed (the page keeps its text and shows a message).
   No value is typed here: every number shown is read from unit_summary.json. */
(() => {
    'use strict';
    const host = document.getElementById('study-map');
    if (!host) return;
    const status = document.getElementById('study-map-status');
    const legend = document.getElementById('study-map-legend');
    const buttons = Array.from(document.querySelectorAll('[data-var]'));
    const setState = (state, msg) => {
        host.dataset.state = state;
        if (status) status.textContent = msg || '';
    };
    setState('loading', 'Loading map…');
    if (typeof L === 'undefined') { setState('failed', 'The map library did not load. The unit values are listed in Table 1.'); return; }

    const VARS = {
        rain: { label: 'Mean rainfall', unit: 'mm per month', ramp: ['#e3eef9', '#08306b'], key: u => u.rain && u.rain.mean, fmt: v => v.toFixed(0), decimals: 0 },
        wet: { label: 'Wet-season rainfall', unit: 'mm per month, April–October', ramp: ['#e3eef9', '#08306b'], key: u => u.rain_wet_season_mean, fmt: v => v.toFixed(0), decimals: 0 },
        soil: { label: 'Soil moisture (0–7 cm)', unit: 'm³ per m³', ramp: ['#f5f0e1', '#5a4a1f'], key: u => u.soil && u.soil.mean, fmt: v => v.toFixed(2), decimals: 2 },
        sar: { label: 'Radar inundation index', unit: 'km² per month, Z3–Z4 only', ramp: ['#fde3cf', '#7f2704'], key: u => u.sar && u.sar.mean, fmt: v => v.toFixed(2), decimals: 2 },
        dw: { label: 'Dynamic World flooding', unit: 'km² per month', ramp: ['#ebe4f3', '#4a1d6b'], key: u => u.dw && u.dw.mean, fmt: v => v.toFixed(1), decimals: 1 },
        ndti: { label: 'Lagoon turbidity (NDTI)', unit: 'uncalibrated index, Z5 only', ramp: ['#e4eef3', '#1f4e5f'], key: u => u.ndti && u.ndti.mean, fmt: v => v.toFixed(3), decimals: 3 },
    };

    const map = L.map(host, { zoomControl: true, attributionControl: true, scrollWheelZoom: false });
    map.attributionControl.setPrefix(false);
    map.attributionControl.addAttribution('Coordinates: WGS 84 (EPSG:4326)');
    L.tileLayer('https://server.arcgisonline.com/ArcGIS/rest/services/Canvas/World_Light_Gray_Base/MapServer/tile/{z}/{y}/{x}',
        { maxZoom: 12, attribution: 'Basemap © Esri' }).addTo(map);
    L.control.scale({ metric: true, imperial: false, position: 'bottomleft' }).addTo(map);
    const north = L.control({ position: 'topright' });
    north.onAdd = () => {
        const d = L.DomUtil.create('div', 'north-arrow');
        d.innerHTML = '<svg width="22" height="30" viewBox="0 0 22 30" aria-hidden="true"><path d="M11 0 L19 26 L11 21 L3 26 Z" fill="#111"/></svg><span>N</span>';
        return d;
    };
    north.addTo(map);

    let geo = null, units = null, layer = null, current = 'rain';

    const ramp = (t, [a, b]) => {
        const pa = [1, 3, 5].map(i => parseInt(a.slice(i, i + 2), 16)), pb = [1, 3, 5].map(i => parseInt(b.slice(i, i + 2), 16));
        return `rgb(${pa.map((x, i) => Math.round(x + (pb[i] - x) * t)).join(',')})`;
    };

    function valuesFor(v) {
        const vals = geo.features.map(f => VARS[v].key(units[f.properties.zone_id] || {})).filter(x => typeof x === 'number');
        return { min: Math.min(...vals), max: Math.max(...vals) };
    }

    function styleFor(f, v, range) {
        const x = VARS[v].key(units[f.properties.zone_id] || {});
        const dashed = f.properties.zone_id === 'Z5';
        if (typeof x !== 'number') {
            return { fillColor: '#ffffff', fillOpacity: 0.9, color: '#6b6b6b', weight: 1.2, dashArray: '4 4' };
        }
        const t = range.max > range.min ? (x - range.min) / (range.max - range.min) : 0.5;
        return { fillColor: ramp(Math.min(1, Math.max(0, t)), VARS[v].ramp), fillOpacity: 0.85, color: f.properties.role_color, weight: 2, dashArray: dashed ? '6 4' : null };
    }

    function renderLegend(v, range) {
        const cfg = VARS[v];
        const n = geo.features.filter(f => typeof VARS[v].key(units[f.properties.zone_id] || {}) === 'number').length;
        if (n === 1) {
            const only = geo.features.find(f => typeof VARS[v].key(units[f.properties.zone_id] || {}) === 'number');
            legend.innerHTML = `<p class="legend-title">${cfg.label}<span>${cfg.unit}</span></p>
                <p class="legend-key">Only ${only.properties.zone_id} has a value: ${cfg.fmt(range.min)} ${cfg.unit.split(',')[0]}.</p>
                <p class="legend-key"><span class="hatch-key"></span>Not interpreted or not observed</p>`;
            return;
        }
        const stops = [0, 0.25, 0.5, 0.75, 1].map(t => ramp(t, cfg.ramp));
        const lo = range.min.toFixed(cfg.decimals), hi = range.max.toFixed(cfg.decimals);
        legend.innerHTML = `<p class="legend-title">${cfg.label}<span>${cfg.unit}</span></p>
            <div class="legend-bar" style="background:linear-gradient(to right, ${stops.join(',')})"></div>
            <div class="legend-ends"><span>${lo}</span><span>${hi}</span></div>
            <p class="legend-key"><span class="hatch-key"></span>Not interpreted or not observed</p>`;
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
    }

    Promise.all([
        fetch('data/ogun_subbasins.geojson').then(r => { if (!r.ok) throw new Error(r.status); return r.json(); }),
        fetch('data/unit_summary.json').then(r => { if (!r.ok) throw new Error(r.status); return r.json(); }),
    ]).then(([g, s]) => {
        geo = g; units = s.units;
        draw(current);
        setState('ready', 'Click a unit for its values. Radar values are not shown for the units Z1 and Z2.');
    }).catch(() => {
        setState('failed', 'The map data could not be loaded. The unit values are listed in Table 1.');
    });

    buttons.forEach(b => b.addEventListener('click', () => { if (geo) draw(b.dataset.var); }));
})();
