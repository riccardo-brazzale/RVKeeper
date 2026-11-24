(() => {
    const desktop = window.matchMedia('(min-width: 761px)');
    const path = window.location.pathname;
    const updateBackButton = (root = document) => {
        const backRow = root.querySelector('[data-back-row]');
        if (backRow) backRow.hidden = false;
    };
    updateBackButton();
    document.addEventListener('click', (event) => {
        const backLink = event.target.closest('[data-back-button]');
        if (!backLink || event.defaultPrevented || event.button !== 0 || event.metaKey || event.ctrlKey || event.shiftKey || event.altKey) return;
        event.preventDefault();
        window.location.assign(backLink.href);
    });
    document.addEventListener('click', (event) => {
        const addButton = event.target.closest('[data-formset-add]');
        if (addButton) {
            const formset = addButton.closest('[data-formset]');
            const totalForms = formset?.querySelector('input[name$="-TOTAL_FORMS"]');
            const template = formset?.querySelector('template[data-formset-empty]');
            const rows = formset?.querySelector('[data-formset-rows]');
            if (!totalForms || !template || !rows) return;
            const index = Number(totalForms.value);
            rows.insertAdjacentHTML('beforeend', template.innerHTML.replace(/__prefix__/g, String(index)));
            totalForms.value = String(index + 1);
            return;
        }
        const removeButton = event.target.closest('[data-formset-remove]');
        if (!removeButton) return;
        const row = removeButton.closest('[data-formset-row]');
        const deleteField = row?.querySelector('input[name$="-DELETE"]');
        if (deleteField) {
            deleteField.checked = true;
            row.hidden = true;
        }
    });
    document.addEventListener('submit', (event) => {
        const form = event.target;
        if (!(form instanceof HTMLFormElement) || !form.dataset.confirm) return;
        if (!window.confirm(form.dataset.confirm)) event.preventDefault();
    });
    const updatePartUnit = (select) => {
        const output = select.closest('.form-field')?.querySelector('[data-part-unit-output]');
        if (!output) return;
        const unit = select.selectedOptions[0]?.dataset.unit;
        output.textContent = unit ? `${output.dataset.unitLabel}: ${unit}` : '';
    };
    const filterPartOptions = (searchInput) => {
        const field = searchInput.closest('.form-field');
        const select = field?.querySelector('select[data-part-select]');
        if (!select) return;
        const query = searchInput.value.trim().toLocaleLowerCase();
        for (const option of select.options) {
            if (!option.value) continue;
            option.hidden = Boolean(query) && !option.dataset.search?.includes(query);
        }
        const selectedOption = select.selectedOptions[0];
        if (query && selectedOption?.value && selectedOption.hidden) {
            select.value = '';
            updatePartUnit(select);
        }
    };
    document.addEventListener('input', (event) => {
        const searchInput = event.target.closest('input[data-part-search]');
        if (searchInput) filterPartOptions(searchInput);
    });
    document.addEventListener('change', (event) => {
        const select = event.target.closest('select[data-part-select]');
        if (!select) return;
        const searchInput = select.closest('.form-field')?.querySelector('input[data-part-search]');
        if (searchInput) {
            searchInput.value = '';
            filterPartOptions(searchInput);
        }
        updatePartUnit(select);
    });
    document.querySelectorAll('select[data-part-select]').forEach((select) => {
        updatePartUnit(select);
        const searchInput = select.closest('.form-field')?.querySelector('input[data-part-search]');
        if (searchInput) filterPartOptions(searchInput);
    });
    const notificationStack = document.querySelector('[data-notification-feed-url]');
    if (notificationStack) {
        let notificationCursor = Number(notificationStack.dataset.afterId || 0);
        let hasLoggedNotificationError = false;
        const updateUnreadCount = (count) => {
            document.querySelectorAll('[data-notification-count]').forEach((badge) => {
                badge.textContent = count > 99 ? '99+' : String(count);
                badge.hidden = count < 1;
            });
        };
        const showNotification = (item) => {
            const toast = document.createElement('a');
            toast.className = 'notification-toast';
            const requestedUrl = item.link || notificationStack.dataset.notificationPageUrl;
            const target = new URL(requestedUrl, window.location.href);
            toast.href = target.origin === window.location.origin
                ? target.href
                : notificationStack.dataset.notificationPageUrl;
            const title = document.createElement('strong');
            title.textContent = item.title;
            toast.append(title);
            if (item.body) {
                const body = document.createElement('span');
                body.textContent = item.body;
                toast.append(body);
            }
            notificationStack.append(toast);
            window.setTimeout(() => toast.remove(), 12000);
        };
        const pollNotifications = async () => {
            if (document.visibilityState === 'hidden') return;
            try {
                const url = new URL(notificationStack.dataset.notificationFeedUrl, window.location.href);
                url.searchParams.set('after', String(notificationCursor));
                const response = await fetch(url.href, { credentials: 'same-origin' });
                if (!response.ok) throw new Error(`Notification feed returned ${response.status}`);
                const data = await response.json();
                updateUnreadCount(Number(data.unread_count) || 0);
                for (const item of data.notifications || []) {
                    showNotification(item);
                }
                notificationCursor = Math.max(notificationCursor, Number(data.cursor) || 0);
                hasLoggedNotificationError = false;
            } catch (error) {
                if (!hasLoggedNotificationError) {
                    console.error('Unable to update RVKeeper notifications.', error);
                    hasLoggedNotificationError = true;
                }
            }
        };
        pollNotifications();
        window.setInterval(pollNotifications, 15000);
        document.addEventListener('visibilitychange', pollNotifications);
        document.addEventListener('rvkeeper:page-loaded', pollNotifications);
    }
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
        const activeLink = candidates[0]?.link;
        activeLink?.setAttribute('aria-current', 'page');
        const activeGroup = activeLink?.closest('details.sidebar-group');
        sidebar.querySelectorAll('details.sidebar-group').forEach((group) => {
            group.open = activeGroup ? group === activeGroup || group.open : false;
        });
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
            const destination = new URL(response.url || requestedUrl, window.location.href);
            const requested = new URL(requestedUrl, window.location.href);
            if (requested.hash) destination.hash = requested.hash;
            if (push) window.history.pushState({ rvkeeperCanGoBack: true }, '', destination.href);
            updateBackButton(content);
            setActiveLink();
            content.focus({ preventScroll: true });
            if (destination.hash) {
                window.requestAnimationFrame(() => document.getElementById(decodeURIComponent(destination.hash.slice(1)))?.scrollIntoView({ block: 'start' }));
            } else {
                window.scrollTo({ top: 0, behavior: 'instant' });
            }
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
        if (event.defaultPrevented || !(form instanceof HTMLFormElement) || !content.contains(form) || form.target || form.dataset.noSpa === 'true') return;
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
