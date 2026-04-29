async function renderOverviewPage() {
    const stateUrl = document.body.dataset.sessionStateUrl;
    const titleEl = document.getElementById('page-title');
    const noteEl = document.getElementById('page-note');
    const banner = document.getElementById('status-banner');
    const headlineEl = document.getElementById('status-headline');
    const captionEl = document.getElementById('status-caption');
    const categoryCountEl = document.getElementById('meta-category-count');
    const productCountEl = document.getElementById('meta-product-count');
    const runModeEl = document.getElementById('meta-run-mode');
    const currentTargetEl = document.getElementById('meta-current-target');
    const collectionEl = document.getElementById('category-collection');
    const summaryEl = document.getElementById('summary-body');

    async function refresh() {
        const session = await window.LauncherUI.fetchJson(stateUrl);
        const categories = await Promise.all((session.categories || []).map(async category => ({
            ...category,
            products: await window.LauncherUI.hydrateProducts(category.products || []),
        })));
        const statusClass = window.LauncherUI.statusClass(session.status);
        banner.className = `status-banner ${statusClass}`;
        headlineEl.textContent = window.LauncherUI.statusHeadline(session.status);
        captionEl.textContent = session.status === 'completed'
            ? `总控页会停留在完成状态。开始于 ${session.startedAt || '--'}，完成于 ${session.completedAt || '--'}。`
            : (session.status === 'failed'
                ? `执行在 ${session.currentCategory || '--'} / ${session.currentProductId || '--'} 处中断。`
                : `页面会持续更新到所有选中品类结束。开始于 ${session.startedAt || '--'}。`);
        titleEl.textContent = '多品类工作流总览';
        noteEl.textContent = session.note || '--';
        categoryCountEl.textContent = String(categories.length);
        productCountEl.textContent = String(categories.reduce((sum, category) => sum + (category.products || []).length, 0));
        runModeEl.textContent = session.runModeLabel || '--';
        currentTargetEl.textContent = session.currentCategory && session.currentProductId
            ? `${session.currentCategory} / ${session.currentProductId}`
            : '--';

        collectionEl.innerHTML = '';
        for (const category of categories) {
            const aggregate = window.LauncherUI.categoryAggregate(category);
            const card = document.createElement('a');
            card.className = 'nav-card';
            card.href = category.categoryPageUrl;
            card.innerHTML = `
                <div class="nav-card__button">
                    <div class="charge-track"><div class="charge-fill ${aggregate.status}" style="width:${window.LauncherUI.formatPercent(aggregate.fraction)}"></div></div>
                    <div class="nav-card__content">
                        <div class="nav-card__title">${category.category}</div>
                        <div class="nav-card__subtitle">${aggregate.completedCount}/${aggregate.totalCount} 个商品已推进 · 当前 ${category.currentProductId || '--'}</div>
                    </div>
                </div>
                <div class="nav-card__stats">
                    <div class="stat-line"><span class="stat-line__label">进度</span><span class="stat-line__value">${window.LauncherUI.formatPercent(aggregate.fraction)}</span></div>
                    <div class="stat-line"><span class="stat-line__label">预计剩余</span><span class="stat-line__value">${aggregate.etaText}</span></div>
                    <div class="stat-line"><span class="stat-line__label">预计完成</span><span class="stat-line__value">${aggregate.finishText}</span></div>
                </div>
            `;
            collectionEl.appendChild(card);
        }

        summaryEl.innerHTML = categories.length
            ? categories.map(category => {
                const aggregate = window.LauncherUI.categoryAggregate(category);
                return `<div class="stat-line"><span class="stat-line__label">${category.category}</span><span class="stat-line__value">${aggregate.completedCount}/${aggregate.totalCount}</span></div>`;
            }).join('')
            : '<div class="empty-state">当前没有已选品类。</div>';

        if (session.status !== 'completed' && session.status !== 'failed') {
            window.setTimeout(refresh, 2000);
        }
    }

    await refresh();
}

window.addEventListener('DOMContentLoaded', () => {
    void renderOverviewPage();
});