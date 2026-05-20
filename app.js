(function () {
    'use strict';

    const ICON_LINK = '<svg xmlns="http://www.w3.org/2000/svg" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2"><path d="M10 13a5 5 0 0 0 7.54.54l3-3a5 5 0 0 0-7.07-7.07l-1.72 1.71"/><path d="M14 11a5 5 0 0 0-7.54-.54l-3 3a5 5 0 0 0 7.07 7.07l1.71-1.71"/></svg>';
    const ICON_MD = '<svg xmlns="http://www.w3.org/2000/svg" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2"><path d="M14 2H6a2 2 0 0 0-2 2v16a2 2 0 0 0 2 2h12a2 2 0 0 0 2-2V8z"/><polyline points="14 2 14 8 20 8"/><line x1="16" y1="13" x2="8" y2="13"/><line x1="16" y1="17" x2="8" y2="17"/></svg>';
    const ICON_IMG = '<svg xmlns="http://www.w3.org/2000/svg" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2"><rect x="3" y="3" width="18" height="18" rx="2"/><circle cx="8.5" cy="8.5" r="1.5"/><polyline points="21 15 16 10 5 21"/></svg>';
    const ICON_OPEN = '<svg xmlns="http://www.w3.org/2000/svg" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2"><path d="M18 13v6a2 2 0 0 1-2 2H5a2 2 0 0 1-2-2V8a2 2 0 0 1 2-2h6"/><polyline points="15 3 21 3 21 9"/><line x1="10" y1="14" x2="21" y2="3"/></svg>';

    const CATEGORY_LABELS = {
        images: 'Image',
        data: 'Data',
        css: 'CSS',
        js: 'JS',
        md: 'MD',
        other: 'Other',
    };

    const VIEW_STORAGE_KEY = 'openterface_assets_view';
    const SORT_STORAGE_KEY = 'openterface_assets_sort';

    const SORT_LABELS = {
        name: 'Name A–Z',
        'date-desc': 'Newest first',
        'date-asc': 'Oldest first',
    };

    let manifest = null;
    let viewMode = 'comfortable';
    let sortMode = 'name';
    let activeCategory = 'all';
    let searchQuery = '';
    let debounceTimer = null;
    let lightboxUrl = '';

    const statsBar = document.getElementById('stats-bar');
    const domainLink = document.getElementById('domain-link');
    const searchInput = document.getElementById('search-input');
    const searchClear = document.getElementById('search-clear');
    const categoryTabs = document.getElementById('category-tabs');
    const statusEl = document.getElementById('status');
    const gridEl = document.getElementById('grid');
    const emptyState = document.getElementById('empty-state');
    const scrollTopBtn = document.getElementById('scroll-top');
    const lightbox = document.getElementById('lightbox');
    const lightboxImg = document.getElementById('lightbox-img');
    const lightboxCaption = document.getElementById('lightbox-caption');
    const lightboxOpen = document.getElementById('lightbox-open');
    const lightboxCopy = document.getElementById('lightbox-copy');
    const viewToggle = document.getElementById('view-toggle');
    const sortSelect = document.getElementById('sort-select');

    function escapeHtml(str) {
        const div = document.createElement('div');
        div.textContent = str;
        return div.innerHTML;
    }

    function formatSize(bytes) {
        if (!bytes || bytes <= 0) return '';
        if (bytes < 1024) return bytes + ' B';
        if (bytes < 1024 * 1024) return (bytes / 1024).toFixed(1) + ' KB';
        return (bytes / (1024 * 1024)).toFixed(1) + ' MB';
    }

    function formatBuildTime(iso) {
        if (!iso) return '';
        try {
            const d = new Date(iso);
            return d.toLocaleString(undefined, {
                month: 'short',
                day: 'numeric',
                hour: '2-digit',
                minute: '2-digit',
            });
        } catch {
            return iso;
        }
    }

    function formatAssetDate(iso) {
        if (!iso) return '';
        try {
            const d = new Date(iso);
            return d.toLocaleDateString(undefined, {
                year: 'numeric',
                month: 'short',
                day: 'numeric',
            });
        } catch {
            return '';
        }
    }

    function fileEmoji(ext) {
        if (ext === '.apk') return '📱';
        if (ext === '.json' || ext === '.csv') return '📊';
        if (ext === '.css') return '🎨';
        if (ext === '.js') return '⚡';
        if (ext === '.md') return '📝';
        return '📄';
    }

    function fileExtLabel(ext) {
        const labels = {
            '.json': 'JSON',
            '.csv': 'CSV',
            '.apk': 'APK',
            '.txt': 'TXT',
            '.xml': 'XML',
        };
        if (labels[ext]) return labels[ext];
        const bare = (ext || '').replace(/^\./, '');
        return bare ? bare.toUpperCase() : 'FILE';
    }

    function filePreviewLabel(asset) {
        if (asset.category === 'data') return fileExtLabel(asset.ext);
        const byCategory = { css: 'CSS', js: 'JS', md: 'MD' };
        if (byCategory[asset.category]) return byCategory[asset.category];
        return fileExtLabel(asset.ext);
    }

    async function copyText(text, btn) {
        try {
            await navigator.clipboard.writeText(text);
        } catch {
            const ta = document.createElement('textarea');
            ta.value = text;
            ta.style.position = 'fixed';
            ta.style.left = '-9999px';
            document.body.appendChild(ta);
            ta.select();
            document.execCommand('copy');
            document.body.removeChild(ta);
        }
        if (btn) {
            btn.classList.add('copied');
            setTimeout(() => btn.classList.remove('copied'), 1500);
        }
    }

    function renderStats() {
        if (!manifest) return;
        const s = manifest.stats || {};
        const parts = [
            `<span class="stat-chip"><strong>${s.total || 0}</strong> assets</span>`,
            `<span class="stat-chip">${s.images || 0} images</span>`,
            `<span class="stat-chip">${s.data || 0} data</span>`,
        ];
        if (manifest.generated_at) {
            const built = `Built ${formatBuildTime(manifest.generated_at)}`;
            const title = manifest.commit ? `${built} · ${manifest.commit}` : built;
            parts.push(
                `<span class="stat-chip stat-chip-muted" title="${escapeHtml(title)}">${escapeHtml(built)}</span>`
            );
        }
        statsBar.innerHTML = parts.join('');

        if (manifest.base_url && domainLink) {
            domainLink.innerHTML = `<a href="${escapeHtml(manifest.base_url)}" target="_blank" rel="noopener noreferrer">${escapeHtml(manifest.base_url.replace(/^https?:\/\//, ''))}</a>`;
        }
    }

    function setViewMode(mode) {
        viewMode = mode === 'compact' ? 'compact' : 'comfortable';
        try {
            localStorage.setItem(VIEW_STORAGE_KEY, viewMode);
        } catch {
            /* ignore */
        }
        gridEl.classList.toggle('view-compact', viewMode === 'compact');
        if (viewToggle) {
            viewToggle.querySelectorAll('.view-btn').forEach((btn) => {
                const active = btn.dataset.view === viewMode;
                btn.classList.toggle('active', active);
                btn.setAttribute('aria-pressed', active ? 'true' : 'false');
            });
        }
    }

    function compareAssets(a, b) {
        const tsA = Number(a.modified_ts) || 0;
        const tsB = Number(b.modified_ts) || 0;
        if (sortMode === 'date-desc') {
            return tsB - tsA || a.path.localeCompare(b.path);
        }
        if (sortMode === 'date-asc') {
            return tsA - tsB || a.path.localeCompare(b.path);
        }
        return a.path.localeCompare(b.path);
    }

    function collectAssets() {
        const list = [];
        (manifest.categories || []).forEach((cat) => {
            (cat.assets || []).forEach((asset) => {
                asset.category = cat.id;
                list.push(asset);
            });
        });
        list.sort(compareAssets);
        return list;
    }

    function setSortMode(mode) {
        if (!['name', 'date-desc', 'date-asc'].includes(mode)) mode = 'name';
        sortMode = mode;
        try {
            localStorage.setItem(SORT_STORAGE_KEY, sortMode);
        } catch {
            /* ignore */
        }
        if (sortSelect) sortSelect.value = sortMode;
    }

    function initSortSelect() {
        try {
            const saved = localStorage.getItem(SORT_STORAGE_KEY);
            if (saved && ['name', 'date-desc', 'date-asc'].includes(saved)) {
                sortMode = saved;
            }
        } catch {
            /* ignore */
        }
        setSortMode(sortMode);
        if (!sortSelect) return;
        sortSelect.addEventListener('change', () => {
            setSortMode(sortSelect.value);
            renderGrid();
            scrollToResults();
        });
    }

    function initViewToggle() {
        try {
            const saved = localStorage.getItem(VIEW_STORAGE_KEY);
            if (saved === 'compact' || saved === 'comfortable') {
                viewMode = saved;
            }
        } catch {
            /* ignore */
        }
        setViewMode(viewMode);
        if (!viewToggle) return;
        viewToggle.querySelectorAll('.view-btn').forEach((btn) => {
            btn.addEventListener('click', () => {
                if (btn.dataset.view !== viewMode) {
                    setViewMode(btn.dataset.view);
                }
            });
        });
    }

    function renderTabs() {
        if (!manifest) return;
        const cats = manifest.categories || [];
        let html = `<button type="button" class="tab-btn active" data-category="all" role="tab" aria-selected="true">All <span class="count">${manifest.stats?.total || 0}</span></button>`;
        cats.forEach((cat) => {
            const count = cat.assets?.length || 0;
            html += `<button type="button" class="tab-btn" data-category="${escapeHtml(cat.id)}" role="tab" aria-selected="false">${escapeHtml(cat.title)} <span class="count">${count}</span></button>`;
        });
        categoryTabs.innerHTML = html;
        categoryTabs.querySelectorAll('.tab-btn').forEach((btn) => {
            btn.addEventListener('click', () => {
                categoryTabs.querySelectorAll('.tab-btn').forEach((b) => {
                    b.classList.remove('active');
                    b.setAttribute('aria-selected', 'false');
                });
                btn.classList.add('active');
                btn.setAttribute('aria-selected', 'true');
                activeCategory = btn.dataset.category;
                applyFilters(true);
            });
        });
    }

    function buildActionsHtml(asset, isImage, extraClass) {
        const cls = extraClass ? `card-actions ${extraClass}` : 'card-actions';
        const mdLink = `[${asset.name}](${asset.url})`;
        const mdImg = `![${asset.name}](${asset.url})`;
        let html = `<div class="${cls}" data-md-link="${escapeHtml(mdLink)}" data-md-img="${escapeHtml(mdImg)}">`;
        html += `<button type="button" class="icon-btn" data-copy="url" title="Copy URL" aria-label="Copy URL">${ICON_LINK}</button>`;
        html += `<button type="button" class="icon-btn" data-copy="md" title="Copy markdown link" aria-label="Copy markdown link">${ICON_MD}</button>`;
        if (isImage) {
            html += `<button type="button" class="icon-btn" data-copy="img" title="Copy markdown image" aria-label="Copy markdown image">${ICON_IMG}</button>`;
        }
        html += `<a class="icon-btn" href="${escapeHtml(asset.url)}" target="_blank" rel="noopener noreferrer" title="Open in new tab" aria-label="Open in new tab">${ICON_OPEN}</a>`;
        html += `</div>`;
        return { html, mdLink, mdImg };
    }

    function buildCard(asset) {
        const isImage = asset.is_image;
        const displayPath = '/' + asset.path;
        const sizeLabel = formatSize(asset.size_bytes);
        const catLabel = CATEGORY_LABELS[asset.category] || asset.category;
        const cardClass = isImage ? 'asset-card asset-card-image' : 'asset-card asset-card-file';

        let html = `<article class="${cardClass}" data-path="${escapeHtml(asset.path.toLowerCase())}" data-category="${escapeHtml(asset.category)}" data-search="${escapeHtml(asset.search_text || '')}">`;

        const overlayActions = buildActionsHtml(asset, isImage, 'card-actions--overlay');

        if (isImage) {
            html += `<div class="card-media">`;
            html += `<button type="button" class="thumb-wrap" data-preview="${escapeHtml(asset.url)}" aria-label="Preview ${escapeHtml(asset.name)}">`;
            html += `<img class="thumb" src="${escapeHtml(asset.url)}" alt="${escapeHtml(asset.name)}" loading="lazy" decoding="async" onerror="this.classList.add('thumb--error')">`;
            html += `</button>`;
            html += overlayActions.html;
            html += `</div>`;
        } else {
            html += `<div class="card-media card-media--file">`;
            html += `<div class="file-preview" data-ext="${escapeHtml(asset.ext)}" data-cat="${escapeHtml(asset.category)}">`;
            html += `<span class="file-preview-ext">${escapeHtml(filePreviewLabel(asset))}</span>`;
            html += `<span class="file-preview-icon" aria-hidden="true">${fileEmoji(asset.ext)}</span>`;
            html += `</div>`;
            html += overlayActions.html;
            html += `</div>`;
        }

        html += `<div class="card-body">`;
        html += `<div class="card-header-row">`;
        html += `<div class="card-name" title="${escapeHtml(asset.name + ' — ' + displayPath)}">${escapeHtml(asset.name)}</div>`;
        html += `<span class="category-badge" data-cat="${escapeHtml(asset.category)}">${escapeHtml(catLabel)}</span>`;
        html += `</div>`;

        const metaParts = [];
        if (asset.modified_at) metaParts.push(formatAssetDate(asset.modified_at));
        if (asset.folder && asset.folder !== '(root)') metaParts.push(asset.folder);
        if (sizeLabel) metaParts.push(sizeLabel);
        if (metaParts.length) {
            html += `<div class="card-meta">${escapeHtml(metaParts.join(' · '))}</div>`;
        }

        html += `<code class="card-path" title="${escapeHtml(displayPath)}">${escapeHtml(displayPath)}</code>`;

        if (asset.alternates && asset.alternates.length > 0) {
            const alt = asset.alternates[0];
            html += `<span class="alt-chip"><a href="${escapeHtml(alt.url)}" target="_blank" rel="noopener noreferrer">Also as ${escapeHtml(alt.ext)}</a></span>`;
        }

        html += `</div></article>`;

        const el = document.createElement('div');
        el.innerHTML = html;
        const card = el.firstElementChild;

        card.querySelectorAll('.card-actions').forEach((actionsEl) => {
            actionsEl.querySelectorAll('[data-copy]').forEach((btn) => {
                btn.addEventListener('click', (e) => {
                    e.stopPropagation();
                    const kind = btn.dataset.copy;
                    let text = asset.url;
                    if (kind === 'md') text = overlayActions.mdLink;
                    if (kind === 'img') text = overlayActions.mdImg;
                    copyText(text, btn);
                });
            });
        });

        const previewBtn = card.querySelector('[data-preview]');
        if (previewBtn) {
            previewBtn.addEventListener('click', () => openLightbox(asset.url, asset.name, displayPath));
        }

        return card;
    }

    function scrollToResults() {
        const sticky = document.querySelector('.toolbar-sticky');
        if (sticky) {
            const top = sticky.getBoundingClientRect().bottom + window.scrollY - 8;
            window.scrollTo({ top: Math.max(0, top), behavior: 'smooth' });
        }
    }

    function applyFilters(scroll) {
        if (!manifest) return;
        const cards = gridEl.querySelectorAll('.asset-card');
        let visible = 0;
        cards.forEach((card) => {
            const cat = card.dataset.category || '';
            const search = card.dataset.search || '';
            let show = true;
            if (activeCategory !== 'all' && cat !== activeCategory) show = false;
            if (searchQuery && !search.includes(searchQuery)) show = false;
            card.classList.toggle('hidden', !show);
            if (show) visible++;
        });

        const hasResults = visible > 0;
        emptyState.classList.toggle('hidden', hasResults);
        gridEl.classList.toggle('hidden', !hasResults);

        let statusText = hasResults
            ? `Showing ${visible} of ${manifest.stats?.total || visible} assets`
            : 'No assets match your filters.';
        if (searchQuery) statusText += ` · “${searchQuery}”`;
        if (activeCategory !== 'all') {
            const label = CATEGORY_LABELS[activeCategory] || activeCategory;
            statusText += ` · ${label} only`;
        }
        if (sortMode !== 'name' && SORT_LABELS[sortMode]) {
            statusText += ` · ${SORT_LABELS[sortMode]}`;
        }
        statusEl.textContent = statusText;
        statusEl.classList.toggle('error', !hasResults);

        if (scroll) scrollToResults();
    }

    function renderGrid() {
        if (!manifest) return;
        gridEl.innerHTML = '';
        const fragment = document.createDocumentFragment();

        collectAssets().forEach((asset) => {
            fragment.appendChild(buildCard(asset));
        });

        gridEl.appendChild(fragment);
        applyFilters(false);
    }

    function openLightbox(url, name, path) {
        lightboxUrl = url;
        lightboxImg.src = url;
        lightboxImg.alt = name || '';
        lightboxCaption.textContent = path ? name + ' — ' + path : name;
        lightboxOpen.href = url;
        lightbox.classList.remove('hidden');
        document.body.style.overflow = 'hidden';
    }

    function closeLightbox() {
        lightbox.classList.add('hidden');
        lightboxImg.src = '';
        lightboxUrl = '';
        document.body.style.overflow = '';
    }

    lightbox.querySelector('.lightbox-close').addEventListener('click', closeLightbox);
    lightbox.addEventListener('click', (e) => {
        if (e.target === lightbox) closeLightbox();
    });
    lightboxCopy.addEventListener('click', () => copyText(lightboxUrl, lightboxCopy));

    document.addEventListener('keydown', (e) => {
        if (e.key === 'Escape') closeLightbox();
        if (e.key === '/' && document.activeElement !== searchInput) {
            e.preventDefault();
            searchInput.focus();
        }
    });

    searchInput.addEventListener('input', () => {
        const val = searchInput.value;
        searchClear.classList.toggle('hidden', !val);
        clearTimeout(debounceTimer);
        debounceTimer = setTimeout(() => {
            searchQuery = val.trim().toLowerCase();
            applyFilters(true);
        }, 150);
    });

    searchClear.addEventListener('click', () => {
        searchInput.value = '';
        searchQuery = '';
        searchClear.classList.add('hidden');
        searchInput.focus();
        applyFilters(true);
    });

    window.addEventListener('scroll', () => {
        scrollTopBtn.classList.toggle('hidden', window.scrollY < 400);
    });

    scrollTopBtn.addEventListener('click', () => {
        window.scrollTo({ top: 0, behavior: 'smooth' });
    });

    async function init() {
        statusEl.textContent = 'Loading catalog…';
        gridEl.classList.add('hidden');
        try {
            const res = await fetch('./assets.json');
            if (!res.ok) throw new Error(`HTTP ${res.status}`);
            manifest = await res.json();
            renderStats();
            renderTabs();
            initSortSelect();
            initViewToggle();
            renderGrid();
            gridEl.classList.remove('hidden');
        } catch (err) {
            statusEl.textContent = 'Failed to load assets.json. Run build and generate_manifest.py first.';
            statusEl.classList.add('error');
            console.error(err);
        }
    }

    const logoutBtn = document.getElementById('logout-btn');
    if (logoutBtn && window.AssetGate) {
        logoutBtn.addEventListener('click', () => {
            window.AssetGate.logout();
            location.reload();
        });
    }

    if (window.AssetGate) {
        window.AssetGate.requireAuth(init);
    } else {
        init();
    }
})();
