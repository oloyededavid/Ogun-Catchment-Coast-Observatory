/* Figure 2: monthly rainfall in each unit, from data/ogun_unit_monthly_timeseries.csv (rain_mm).
   Each segment fills to that month's rainfall relative to the largest month in the record, and drops fall in
   proportion to it. Values are read from the file, not typed here. Reduced-motion users get the static month. */
(() => {
    'use strict';
    const bands = Array.from(document.querySelectorAll('.band-seg[data-zone]'));
    if (!bands.length) return;
    const play = document.getElementById('band-play');
    const slider = document.getElementById('band-month');
    const out = document.getElementById('band-month-label');
    const status = document.getElementById('band-status');
    const reduced = matchMedia('(prefers-reduced-motion: reduce)').matches;
    const setStatus = m => { if (status) status.textContent = m; };
    const thumb = document.getElementById('band-thumb');
    const fill = document.getElementById('band-fill');
    // The static monthly-mean line is replaced by the live monthly value.
    bands.forEach(li => { const vals = li.querySelectorAll('.band-val'); if (vals.length) vals[vals.length - 1].style.display = 'none'; });

    fetch('data/ogun_unit_monthly_timeseries.csv')
        .then(r => { if (!r.ok) throw new Error(r.status); return r.text(); })
        .then(text => {
            const lines = text.trim().split('\n');
            const head = lines[0].split(',');
            const iM = head.indexOf('year_month'), iZ = head.indexOf('zone_id'), iR = head.indexOf('rain_mm');
            const rain = {};   // zone -> month -> mm
            const months = new Set();
            lines.slice(1).forEach(l => {
                const c = l.split(',');
                const m = c[iM], z = c[iZ], v = c[iR];
                months.add(m);
                (rain[z] = rain[z] || {})[m] = v === '' ? null : Number(v);
            });
            const monthList = Array.from(months).sort();
            const maxRain = Math.max(...Object.values(rain).flatMap(o => Object.values(o).filter(v => v !== null)));
            slider.max = String(monthList.length - 1);
            const state = bands.map(li => ({ li, zone: li.dataset.zone, water: li.querySelector('.band-water'),
                canvas: li.querySelector('.band-rain'), drops: [], ctx: null }));
            state.forEach(s => {
                s.ctx = s.canvas.getContext('2d');
                // drops contrast with the segment: white on dark segments, dark blue on light ones
                const m = getComputedStyle(s.li).backgroundColor.match(/\d+(\.\d+)?/g) || [255, 255, 255];
                const lum = (0.2126 * m[0] + 0.7152 * m[1] + 0.0722 * m[2]) / 255;
                s.drop = lum < 0.5 ? 'rgba(255,255,255,1)' : 'rgba(29,79,133,1)';
                s.alpha = lum < 0.5 ? 0.42 : 0.3;
                const r = s.li.getBoundingClientRect();
                s.canvas.width = Math.max(1, Math.round(r.width));
                s.canvas.height = Math.max(1, Math.round(r.height));
            });

            let idx = 0, timer = null, raf = null, last = 0;
            const valueAt = (zone, i) => { const v = (rain[zone] || {})[monthList[i]]; return v === undefined ? null : v; };

            function show(i) {
                idx = i;
                const m = monthList[i];
                slider.value = String(i);
                out.textContent = m;
                const pct = monthList.length > 1 ? (i / (monthList.length - 1)) * 100 : 0;
                if (thumb) thumb.style.left = pct.toFixed(2) + '%';
                if (fill) fill.style.width = pct.toFixed(2) + '%';
                state.forEach(s => {
                    const v = valueAt(s.zone, i);
                    const frac = v === null ? 0 : Math.min(1, v / maxRain);
                    s.water.style.height = `${(frac * 100).toFixed(1)}%`;
                    const live = s.li.querySelector('.band-live');
                    const txt = v === null ? "no value" : `${v.toFixed(0)} mm`;
                    if (live) live.textContent = txt;
                    else { const el = document.createElement('span'); el.className = 'band-live'; el.textContent = txt; s.li.appendChild(el); }
                    // drops: one per 4 mm of rain, up to 60
                    const n = v === null ? 0 : Math.min(60, Math.round(v / 4));
                    s.drops = Array.from({ length: n }, () => ({ x: Math.random(), y: Math.random(), sp: 0.4 + Math.random() * 0.6 }));
                });
                setStatus(`${m}. Blue fill height and drops show each unit's rainfall that month. Full height is the wettest unit-month in the record, ${maxRain.toFixed(0)} mm.`);
            }

            function draw(now) {
                const dt = last ? Math.min(0.1, (now - last) / 1000) : 0; last = now;
                state.forEach(s => {
                    const { ctx, canvas } = s;
                    ctx.clearRect(0, 0, canvas.width, canvas.height);
                    ctx.strokeStyle = s.drop; ctx.globalAlpha = s.alpha; ctx.lineWidth = 1.3; ctx.lineCap = 'round';
                    s.drops.forEach(d => {
                        d.y += d.sp * dt * 0.9; if (d.y > 1.05) { d.y = -0.05; d.x = Math.random(); }
                        const x = d.x * canvas.width, y = d.y * canvas.height;
                        ctx.beginPath(); ctx.moveTo(x, y); ctx.lineTo(x - 2, y - 8); ctx.stroke();
                    });
                    ctx.globalAlpha = 1;
                });
                if (!reduced && timer) raf = requestAnimationFrame(draw);
            }

            function start() {
                play.dataset.state = 'playing'; play.querySelector('.bp-label').textContent = 'Pause animation'; play.setAttribute('aria-pressed', 'true');
                timer = setInterval(() => show((idx + 1) % monthList.length), 900);
                if (!reduced) { last = 0; raf = requestAnimationFrame(draw); }
            }
            function stop() {
                play.dataset.state = 'paused'; play.querySelector('.bp-label').textContent = 'Play animation'; play.setAttribute('aria-pressed', 'false');
                clearInterval(timer); timer = null; cancelAnimationFrame(raf);
            }

            play.addEventListener('click', () => (timer ? stop() : start()));
            slider.addEventListener('input', () => { stop(); show(Number(slider.value)); });
            window.addEventListener('resize', () => state.forEach(s => {
                const r = s.li.getBoundingClientRect();
                s.canvas.width = Math.max(1, Math.round(r.width)); s.canvas.height = Math.max(1, Math.round(r.height));
            }));
            show(0);
            if (reduced) { stop(); } else { start(); }
        })
        .catch(() => { setStatus('Monthly rainfall could not be loaded. The band shows the 2019–2024 means.'); if (play) play.disabled = true; });
})();
