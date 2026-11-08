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
        // black and white only: brighter fill = more rainfall that month
        const shade = v => {
            const t = Math.max(0, Math.min(1, (v - lo) / (hi - lo || 1)));
            const c = Math.round(40 + 170 * t);
            return `rgb(${c},${c},${c})`;
        };
        const centre = f => {
            const ring = (f.geometry.type === 'Polygon' ? f.geometry.coordinates : f.geometry.coordinates[0])[0];
            const xs = ring.map(p => p[0]), ys = ring.map(p => p[1]);
            return [X((Math.min(...xs) + Math.max(...xs)) / 2), Y((Math.min(...ys) + Math.max(...ys)) / 2)];
        };
        const zones = feats.map(f => f.properties.zone_id);
        const centres = Object.fromEntries(feats.map(f => [f.properties.zone_id, centre(f)]));
        const drawBase = (month) => {
            ctx.clearRect(0, 0, W, H);
            const vals = byMonth.get(month) || {};
            feats.forEach(f => {
                const z = f.properties.zone_id;
                const polys = f.geometry.type === 'Polygon' ? [f.geometry.coordinates] : f.geometry.coordinates;
                ctx.beginPath();
                polys.forEach(poly => poly[0].forEach(([x, y], i) => (i ? ctx.lineTo(X(x), Y(y)) : ctx.moveTo(X(x), Y(y)))));
                ctx.closePath();
                ctx.fillStyle = typeof vals[z] === 'number' ? shade(vals[z]) : '#141414';
                ctx.fill();
                ctx.strokeStyle = '#000';
                ctx.lineWidth = 1.2;
                ctx.stroke();
            });
        };
        const drawCursor = (x, y, pressed) => {
            ctx.save();
            ctx.translate(x, y);
            if (pressed) { ctx.beginPath(); ctx.arc(0, 0, 16, 0, Math.PI * 2); ctx.strokeStyle = 'rgba(255,255,255,.7)'; ctx.lineWidth = 2; ctx.stroke(); }
            ctx.beginPath(); ctx.moveTo(0, 0); ctx.lineTo(0, 18); ctx.lineTo(5, 13.5); ctx.lineTo(9, 21); ctx.lineTo(12, 19.5); ctx.lineTo(8.5, 12.5); ctx.lineTo(14, 12.5); ctx.closePath();
            ctx.fillStyle = '#fff'; ctx.strokeStyle = '#000'; ctx.lineWidth = 1; ctx.fill(); ctx.stroke();
            ctx.restore();
        };
        const drawTip = (x, y, text) => {
            ctx.save();
            ctx.font = '13px sans-serif';
            const w = ctx.measureText(text).width + 16;
            const tx = Math.min(W - w - 6, Math.max(6, x + 14)), ty = Math.max(8, y - 34);
            ctx.fillStyle = '#fff'; ctx.fillRect(tx, ty, w, 26);
            ctx.fillStyle = '#000'; ctx.fillText(text, tx + 8, ty + 17);
            ctx.restore();
        };
        // Scripted click-through: the cursor visits each unit in turn, clicks, and the tooltip shows that unit's real value for the month shown.
        const steps = [];
        for (let k = 0; k < months.length; k++) zones.forEach(z => steps.push({ month: months[k], zone: z }));
        const pos = { x: W * 0.5, y: H * 0.12 };
        let si = 0, phase = 0, t0 = performance.now();
        const frame = now => {
            const st = steps[si % steps.length];
            const target = centres[st.zone];
            const k = Math.min(1, (now - t0) / 480);
            const x = pos.x + (target[0] - pos.x) * k, y = pos.y + (target[1] - pos.y) * k;
            drawBase(st.month);
            const pressed = k >= 1 && now - t0 < 480 + 260;
            const v = (byMonth.get(st.month) || {})[st.zone];
            if (k >= 1) drawTip(target[0], target[1], typeof v === 'number' ? `${st.zone} · ${v.toFixed(0)} mm · ${st.month}` : `${st.zone} · no value`);
            drawCursor(x, y, pressed);
            label.textContent = st.month + '  ·  mean monthly rainfall by unit';
            if (now - t0 >= 480 + 900) { pos.x = target[0]; pos.y = target[1]; si += 1; t0 = now; }
            if (!reduced) requestAnimationFrame(frame);
        };
        if (reduced) {
            const first = steps[0]; drawBase(first.month);
            const v = (byMonth.get(first.month) || {})[first.zone];
            drawCursor(centres[first.zone][0], centres[first.zone][1], false);
            drawTip(centres[first.zone][0], centres[first.zone][1], typeof v === 'number' ? `${first.zone} · ${v.toFixed(0)} mm · ${first.month}` : first.zone);
            label.textContent = first.month + '  ·  mean monthly rainfall by unit';
        } else {
            const start = performance.now(); t0 = start;
            requestAnimationFrame(frame);
        }
        if (reduced || months.length === 0) return;
    }).catch(() => { label.textContent = ''; });
})();
