/* Scroll progress along the top edge, and reveal on scroll. Both stop for reduced-motion users. */
(() => {
    'use strict';
    const reduced = matchMedia('(prefers-reduced-motion: reduce)').matches;
    const bar = document.createElement('div');
    bar.className = 'scroll-progress';
    bar.setAttribute('aria-hidden', 'true');
    document.body.appendChild(bar);
    let ticking = false;
    const update = () => {
        const max = document.documentElement.scrollHeight - innerHeight;
        bar.style.transform = `scaleX(${max > 0 ? Math.min(1, scrollY / max) : 0})`;
        ticking = false;
    };
    addEventListener('scroll', () => { if (!ticking) { ticking = true; requestAnimationFrame(update); } }, { passive: true });
    update();

    // Header navigation: the link for the last section whose top has passed 30% of the viewport is highlighted.
    const navLinks = Array.from(document.querySelectorAll('.toc a[href^="#"]'));
    const pairs = navLinks.map(a => ({ a, el: document.getElementById(a.getAttribute('href').slice(1)) })).filter(x => x.el);
    if (pairs.length) {
        let current = null, pending = false;
        const update = () => {
            pending = false;
            const line = innerHeight * 0.3;
            let hit = null;
            pairs.forEach(x => { if (x.el.getBoundingClientRect().top <= line) hit = x; });
            const id = hit ? hit.a.getAttribute('href') : null;
            if (id === current) return;
            current = id;
            pairs.forEach(x => {
                const on = x.a.getAttribute('href') === id;
                x.a.classList.toggle('is-current', on);
                if (on) x.a.setAttribute('aria-current', 'location'); else x.a.removeAttribute('aria-current');
            });
        };
        const schedule = () => { if (!pending) { pending = true; requestAnimationFrame(update); } };
        addEventListener('scroll', schedule, { passive: true });
        addEventListener('resize', schedule);
        update();
    }

    if (reduced || !('IntersectionObserver' in window)) return;
    const io = new IntersectionObserver(entries => entries.forEach(e => {
        if (e.isIntersecting) { e.target.classList.add('in'); io.unobserve(e.target); }
    }), { threshold: 0.12 });
    document.querySelectorAll('[data-reveal], .reveal').forEach(el => io.observe(el));
})();


/* Back to top: appears after the first screen; each block in a section eases in as it reaches the viewer */
(() => {
    'use strict';
    const btn = document.getElementById('to-top');
    if (btn) {
        const show = () => btn.classList.toggle('is-visible', scrollY > innerHeight * 0.8);
        addEventListener('scroll', show, { passive: true });
        btn.addEventListener('click', () => {
            const reduced = matchMedia('(prefers-reduced-motion: reduce)').matches;
            window.scrollTo({ top: 0, behavior: reduced ? 'auto' : 'smooth' });
        });
        show();
    }
    const reduced = matchMedia('(prefers-reduced-motion: reduce)').matches;
    if (reduced || !('IntersectionObserver' in window)) return;
    const blocks = document.querySelectorAll('main section > h2, main section > h3, main section > p, main section > figure, main section > ol, main section > ul, main section > .catch-share, main section > .band-controls, main section > .cta-card, main section > .table-wrap, main section > .pipeline');
    const io = new IntersectionObserver(entries => entries.forEach(e => {
        if (e.isIntersecting) { e.target.classList.add('in'); io.unobserve(e.target); }
    }), { threshold: 0.02, rootMargin: '0px 0px 8% 0px' });
    let i = 0;
    blocks.forEach(el => {
        el.classList.add('rv');
        el.style.setProperty('--d', `${((i++ % 3) * 0.07).toFixed(2)}s`);
        io.observe(el);
    });
})();
