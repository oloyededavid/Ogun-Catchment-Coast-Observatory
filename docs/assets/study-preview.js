/* Two small motions for the study page. Both use real data and both stop for reduced-motion users.
   1. The explorer card plays the monthly mean rainfall of each unit (data/ogun_unit_monthly_timeseries.csv),
      one month at a time, on the unit outlines (data/ogun_subbasins.geojson).
   2. The three key figures count up to their values when they scroll into view. The values are written
      into the page by scripts/build_page.py; this script only animates them. */
(() => {
    'use strict';
    const reduced = matchMedia('(prefers-reduced-motion: reduce)').matches;

    // 2. counters
    const counters = Array.from(document.querySelectorAll('[data-count]'));
    const countUp = el => {
        const target = Number(el.dataset.count);
        if (!Number.isFinite(target) || reduced) return;
        const text = el.textContent;
        const start = performance.now(), dur = 1100;
        const step = now => {
            const k = Math.min(1, (now - start) / dur), eased = 1 - Math.pow(1 - k, 3);
            el.textContent = Math.round(target * eased).toLocaleString('en-GB');
            if (k < 1) requestAnimationFrame(step); else el.textContent = text;
        };
        el.textContent = '0';
        requestAnimationFrame(step);
    };
    if (counters.length && 'IntersectionObserver' in window && !reduced) {
        const io = new IntersectionObserver(entries => entries.forEach(e => {
            if (e.isIntersecting) { countUp(e.target); io.unobserve(e.target); }
        }), { threshold: 0.6 });
        counters.forEach(c => io.observe(c));
    }

    // 1. explorer card preview
    const canvas = document.getElementById('preview-canvas');
    const label = document.getElementById('preview-month');
    if (!canvas || !label) return;
    const ctx = canvas.getContext('2d');
    Promise.all([
        fetch('data/ogun_subbasins.geojson').then(r => { if (!r.ok) throw new Error(r.status); return r.json(); }),
        fetch('data/ogun_unit_monthly_timeseries.csv').then(r => { if (!r.ok) throw new Error(r.status); return r.text(); }),
    ]).then(([geo, csv]) => {
        const lines = csv.trim().split('\n');
        const head = lines[0].split(',');
        const iM = head.indexOf('year_month'), iZ = head.indexOf('zone_id'), iR = head.indexOf('rain_mm');
        const byMonth = new Map();
        lines.slice(1).forEach(l => {
            const c = l.split(',');
            if (!c[iR]) return;
            if (!byMonth.has(c[iM])) byMonth.set(c[iM], {});
            byMonth.get(c[iM])[c[iZ]] = Number(c[iR]);
        });
        const months = Array.from(byMonth.keys()).sort();
        const feats = geo.features;
        const all = feats.flatMap(f => (f.geometry.type === 'Polygon' ? [f.geometry.coordinates] : f.geometry.coordinates)
            .flatMap(poly => poly[0]));
        const minX = Math.min(...all.map(p => p[0])), maxX = Math.max(...all.map(p => p[0]));
        const minY = Math.min(...all.map(p => p[1])), maxY = Math.max(...all.map(p => p[1]));
        const pad = 26, W = canvas.width, H = canvas.height;
        const scale = Math.min((W - 2 * pad) / (maxX - minX), (H - 2 * pad) / (maxY - minY));
        const ox = (W - (maxX - minX) * scale) / 2, oy = (H - (maxY - minY) * scale) / 2;
        const X = x => ox + (x - minX) * scale, Y = y => H - (oy + (y - minY) * scale);
        const allVals = Array.from(byMonth.values()).flatMap(o => Object.values(o));
        const lo = Math.min(...allVals), hi = Math.max(...allVals);
        // blue ramp on black: low rainfall dark, high rainfall bright
        const colour = v => {
            const t = Math.max(0, Math.min(1, (v - lo) / (hi - lo || 1)));
            const a = [18, 44, 84], b = [158, 197, 255];
            return `rgb(${a.map((x, i) => Math.round(x + (b[i] - x) * t)).join(',')})`;
        };
        const draw = month => {
            ctx.clearRect(0, 0, W, H);
            const vals = byMonth.get(month) || {};
            feats.forEach(f => {
                const z = f.properties.zone_id;
                const polys = f.geometry.type === 'Polygon' ? [f.geometry.coordinates] : f.geometry.coordinates;
                ctx.beginPath();
                polys.forEach(poly => poly[0].forEach(([x, y], i) => (i ? ctx.lineTo(X(x), Y(y)) : ctx.moveTo(X(x), Y(y)))));
                ctx.closePath();
                ctx.fillStyle = typeof vals[z] === 'number' ? colour(vals[z]) : '#1b1b1b';
                ctx.fill();
                ctx.strokeStyle = '#2a2a2a';
                ctx.lineWidth = 1;
                ctx.stroke();
            });
            label.textContent = month + '  ·  mean monthly rainfall by unit';
        };
        if (reduced || months.length === 0) { draw(months[months.length - 1] || ''); return; }
        let i = 0;
        const tick = () => { draw(months[i]); i = (i + 1) % months.length; };
        tick();
        setInterval(tick, 380);
    }).catch(() => { label.textContent = ''; });
})();
