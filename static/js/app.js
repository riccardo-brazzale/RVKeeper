(() => {
    const desktop = window.matchMedia('(min-width: 761px)');
    const path = window.location.pathname;
    // Il pannello admin mantiene il proprio comportamento e layout Django.
    if (!desktop.matches || path.startsWith('/admin/')) return;

    const content = document.querySelector('#page-content');
    const sidebar = document.querySelector('#primary-navigation');
    if (!content || !sidebar) return;

    const progress = document.createElement('div');
    progress.className = 'spa-progress';
    progress.setAttribute('role', 'progressbar');
    progress.setAttribute('aria-label', 'Caricamento pagina');
    document.body.append(progress);

    let progressTimer;
    const showProgress = () => {
        window.clearTimeout(progressTimer);
        progress.classList.remove('is-done');
        progress.classList.add('is-loading');
    };
    const hideProgress = () => {
        progress.classList.remove('is-loading');
        progress.classList.add('is-done');
        progressTimer = window.setTimeout(() => progress.classList.remove('is-done'), 220);
    };

    const setActiveLink = () => {
        const currentPath = window.location.pathname;
        const links = [...sidebar.querySelectorAll('a[href]')];
        links.forEach((link) => link.removeAttribute('aria-current'));
        const candidates = links
            .map((link) => ({ link, path: new URL(link.href, window.location.href).pathname }))
            .filter(({ path: linkPath }) => linkPath === currentPath || (linkPath !== '/' && currentPath.startsWith(linkPath)));
        candidates.sort((a, b) => b.path.length - a.path.length);
        candidates[0]?.link.setAttribute('aria-current', 'page');
    };

    const applyResponse = async (response, requestedUrl, push) => {
            if (!response.ok || !response.headers.get('content-type')?.includes('text/html')) {
                return false;
            }
            const html = await response.text();
            const nextDocument = new DOMParser().parseFromString(html, 'text/html');
            const nextContent = nextDocument.querySelector('#page-content');
            if (!nextContent) return false;

            content.replaceChildren(...[...nextContent.childNodes].map((node) => document.importNode(node, true)));
            document.title = nextDocument.title || document.title;
            if (push) window.history.pushState({}, '', response.url || requestedUrl);
            setActiveLink();
            content.focus({ preventScroll: true });
            window.scrollTo({ top: 0, behavior: 'instant' });
            document.dispatchEvent(new CustomEvent('rvkeeper:page-loaded'));
            return true;
    };

    const loadPage = async (url, { push = true, fallback = true } = {}) => {
        showProgress();
        try {
            const response = await fetch(url, {
                headers: { 'X-Requested-With': 'XMLHttpRequest' },
                credentials: 'same-origin',
            });
            const applied = await applyResponse(response, url, push);
            if (!applied && fallback) window.location.assign(url);
        } catch (error) {
            if (fallback) window.location.assign(url);
        } finally {
            hideProgress();
        }
    };

    document.addEventListener('click', (event) => {
        if (event.defaultPrevented || event.button !== 0 || event.metaKey || event.ctrlKey || event.shiftKey || event.altKey) return;
        const link = event.target.closest('a[href]');
        if (!link || link.target || link.hasAttribute('download')) return;
        const url = new URL(link.href, window.location.href);
        if (url.origin !== window.location.origin || url.pathname.startsWith('/admin/') || url.hash && url.pathname === window.location.pathname) return;
        event.preventDefault();
        loadPage(url.href);
    });

    document.addEventListener('submit', (event) => {
        const form = event.target;
        if (!(form instanceof HTMLFormElement) || !content.contains(form) || form.target || form.dataset.noSpa === 'true') return;
        const url = new URL(form.action || window.location.href, window.location.href);
        if (url.origin !== window.location.origin || url.pathname.startsWith('/admin/')) return;
        const method = form.method.toLowerCase();
        if (method === 'get') {
            if (form.querySelector('input[type="file"]')) return;
            event.preventDefault();
            const params = new URLSearchParams(new FormData(form));
            url.search = params.toString();
            loadPage(url.href);
            return;
        }
        if (method !== 'post') {
            event.preventDefault();
            form.submit();
            return;
        }

        event.preventDefault();
        showProgress();
        const submitter = event.submitter;
        const body = submitter ? new FormData(form, submitter) : new FormData(form);
        fetch(url.href, {
            method: 'POST',
            body,
            headers: { 'X-Requested-With': 'XMLHttpRequest' },
            credentials: 'same-origin',
        }).then(async (response) => {
            const applied = await applyResponse(response, url.href, true);
            if (!applied) window.location.assign(response.url || window.location.href);
        }).catch(() => window.location.reload()).finally(hideProgress);
    });

    window.addEventListener('popstate', () => loadPage(window.location.href, { push: false, fallback: false }));
    setActiveLink();
})();
