/* Interactive monthly series for Figure 3 (Chart.js, vendored in docs/vendor).
   Reads data/ogun_monthly_timeseries.csv. Each chart draws in once when it scrolls into view;
   the animation is off for users who prefer reduced motion. If the data cannot be loaded, the
   static image in the page's <noscript> fallback remains. No value is typed here. */
(() => {
    'use strict';
    const holders = Array.from(document.querySelectorAll('[data-series]'));
    if (!holders.length) return;
    const reduced = matchMedia('(prefers-reduced-motion: reduce)').matches;
    if (typeof Chart === 'undefined') return;

    const setStatus = (msg) => { const s = document.getElementById('series-status'); if (s) s.textContent = msg; };

    fetch('data/ogun_monthly_timeseries.csv')
        .then(r => { if (!r.ok) throw new Error(r.status); return r.text(); })
        .then(text => {
            const lines = text.trim().split('\n');
            const head = lines[0].split(',');
            const col = name => head.indexOf(name);
            const rows = lines.slice(1).map(l => l.split(','));
            const labels = rows.map(r => r[col('year_month')]);
            const series = name => rows.map(r => { const v = r[col(name)]; return v === '' || v === undefined ? null : Number(v); });
            const specs = {
                rain: () => ({
                    type: 'bar',
                    data: { labels, datasets: [
                        { label: 'Rainfall (mm/month)', data: series('rain_mm'), backgroundColor: '#8fb7e3', yAxisID: 'y' },
                        { label: 'Soil moisture (m³/m³)', data: series('shallow_sm_m3m3'), type: 'line', borderColor: '#3c8d6e', borderWidth: 1.6, pointRadius: 0, yAxisID: 'y2', spanGaps: false },
                    ] },
                    axes: { y: 'Rainfall (mm per month)', y2: 'Soil moisture (m³/m³)' },
                }),
                radar: () => ({
                    type: 'line',
                    data: { labels, datasets: [{ label: 'Radar inundation index (km²)', data: series('sar_flood_km2'), borderColor: '#c0501a', backgroundColor: '#c0501a', borderWidth: 1.6, pointRadius: 0, spanGaps: false }] },
                    axes: { y: 'Radar index (km²)' },
                }),
                dw: () => ({
                    type: 'line',
                    data: { labels, datasets: [{ label: 'Dynamic World flooding (km²)', data: series('dw_flood_km2'), borderColor: '#7a5aa6', backgroundColor: '#7a5aa6', borderWidth: 1.6, pointRadius: 0, spanGaps: false }] },
                    axes: { y: 'Dynamic World (km²)' },
                }),
                ndti: () => ({
                    type: 'line',
                    data: { labels, datasets: [{ label: 'Lagoon turbidity (NDTI, uncalibrated)', data: series('estuary_ndti'), borderColor: '#8a6d1f', backgroundColor: '#8a6d1f', borderWidth: 1.6, pointRadius: 0, spanGaps: false }] },
                    axes: { y: 'Lagoon NDTI' },
                }),
            };
            const charts = [];
            holders.forEach(h => {
                const key = h.dataset.series;
                const canvas = h.querySelector('canvas');
                if (!canvas || !specs[key]) return;
                const spec = specs[key]();
                const scales = {
                    x: { ticks: { maxTicksLimit: 8, autoSkip: true, color: '#4a4a4a', font: { size: 13 } }, grid: { display: false } },
                    y: { title: { display: true, text: spec.axes.y, color: '#4a4a4a', font: { size: 13 } }, ticks: { color: '#4a4a4a', font: { size: 13 } }, grid: { color: '#e6e5df' } },
                };
                if (spec.axes.y2) scales.y2 = { position: 'right', title: { display: true, text: spec.axes.y2, color: '#4a4a4a', font: { size: 13 } }, ticks: { color: '#4a4a4a', font: { size: 13 } }, grid: { display: false } };
                const chart = new Chart(canvas, {
                    type: spec.type,
                    data: spec.data,
                    options: {
                        responsive: true, maintainAspectRatio: false, animation: false,
                        interaction: { mode: 'index', intersect: false },
                        plugins: { legend: { labels: { boxWidth: 12, font: { size: 13 } } }, tooltip: { callbacks: { label: c => `${c.dataset.label}: ${c.parsed.y === null ? 'no valid value' : Number(c.parsed.y).toFixed(3)}` } } },
                        scales,
                    },
                });
                charts.push({ el: h, chart, spec });
            });
            // Draw each chart the first time it is visible, so the animation is seen.
            const io = 'IntersectionObserver' in window ? new IntersectionObserver(entries => {
                entries.forEach(e => {
                    if (!e.isIntersecting) return;
                    const item = charts.find(c => c.el === e.target);
                    if (item && !item.drawn) {
                        item.drawn = true;
                        if (!reduced) { item.chart.options.animation = { duration: 1400, easing: 'easeOutQuart' }; item.chart.reset(); }
                        item.chart.update();
                    }
                    io.unobserve(e.target);
                });
            }, { threshold: 0.25 }) : null;
            charts.forEach(c => { c.drawn = false; if (io) io.observe(c.el); else { c.chart.options.animation = false; c.chart.update(); } });
            setStatus('Hover over a chart to read a month’s values. Gaps are months with no valid observation.');
        })
        .catch(() => {
            holders.forEach(h => h.classList.add('is-fallback'));
            setStatus('The interactive charts could not be loaded. The static figure below shows the same series.');
        });
})();
