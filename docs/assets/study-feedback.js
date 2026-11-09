/* Reactions and page views. The site has no server: counts are kept by the public Abacus counter
   (abacus.jasoncameron.dev). A view is counted once per browser session, a reaction once per browser.
   No names, addresses or cookies are stored. Counts are read and written on the live site only. */
(() => {
    'use strict';
    const COUNTER = 'https://abacus.jasoncameron.dev';
    const NS = 'oloyededavid-ogun-surface-water-v1';
    const LIVE = location.hostname === 'oloyededavid.github.io' && !navigator.webdriver;
    const KEY = { 'Useful': 'useful', 'Interesting': 'interesting', 'Needs clarity': 'clarity' };
    const STORE = 'ogun-reaction-1';
    const fmt = n => Number(n).toLocaleString('en-GB');
    const store = {
        get: (k, t = sessionStorage) => { try { return t.getItem(k); } catch (e) { return null; } },
        set: (k, v, t = sessionStorage) => { try { t.setItem(k, v); } catch (e) { /* storage blocked */ } },
    };
    const count = (op, key) => fetch(`${COUNTER}/${op}/${NS}/${key}`)
        .then(r => (r.ok ? r.json() : r.status === 404 ? { value: 0 } : Promise.reject(r.status)))
        .then(j => Number(j.value) || 0);
    const show = (label, n) => { const el = document.querySelector(`.react[data-react="${label}"] .rc`); if (el) el.textContent = n ? fmt(n) : ''; };

    if (LIVE) {
        const v = document.getElementById('views');
        if (v) {
            const seen = store.get('ogun-viewed');
            count(seen ? 'get' : 'hit', 'views')
                .then(n => { if (!seen) store.set('ogun-viewed', '1'); if (n) { v.textContent = `${fmt(n)} page views`; v.hidden = false; } })
                .catch(() => {});
        }
        Object.entries(KEY).forEach(([label, key]) => {
            if (document.querySelector(`.react[data-react="${label}"]`)) count('get', key).then(n => show(label, n)).catch(() => {});
        });
    }

    const buttons = Array.from(document.querySelectorAll('.react'));
    const status = document.getElementById('react-status');
    if (!buttons.length || !status) return;
    let reaction = store.get(STORE, localStorage) || '';
    const mark = () => buttons.forEach(b => {
        b.setAttribute('aria-pressed', String(b.dataset.react === reaction));
        b.classList.toggle('is-other', !!reaction && b.dataset.react !== reaction);
    });
    mark();
    if (reaction) status.textContent = 'Thanks, your reaction is counted.';
    buttons.forEach(b => b.addEventListener('click', () => {
        if (reaction) {
            status.textContent = reaction === b.dataset.react ? 'Thanks, your reaction is counted.' : 'You have already reacted from this browser.';
            return;
        }
        reaction = b.dataset.react;
        store.set(STORE, reaction, localStorage);
        mark();
        status.textContent = 'Thank you! Counted.';
        const rc = b.querySelector('.rc');
        const before = Number((rc.textContent || '0').replace(/,/g, '')) || 0;
        rc.textContent = fmt(before + 1);
        b.classList.add('pop');
        if (LIVE) count('hit', KEY[reaction]).then(n => show(reaction, n)).catch(() => {});
    }));
})();
