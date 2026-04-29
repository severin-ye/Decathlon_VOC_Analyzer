async function renderCategoryPage() {
    const stateUrl = document.body.dataset.sessionStateUrl;
    const categoryKey = document.body.dataset.category;
    const titleEl = document.getElementById('page-title');
    const noteEl = document.getElementById('page-note');
    const banner = document.getElementById('status-banner');
    const headlineEl = document.getElementById('status-headline');
    const captionEl = document.getElementById('status-caption');
    const productCountEl = document.getElementById('meta-product-count');
    const reviewLimitEl = document.getElementById('meta-review-limit');
    const currentTargetEl = document.getElementById('meta-current-product');
    const collectionEl = document.getElementById('product-collection');
    const summaryEl = document.getElementById('summary-body');

    async function refresh() {
        const session = await window.LauncherUI.fetchJson(stateUrl);
        const category = (session.categories || []).find(item => item.category === categoryKey);
        if (!category) {
            collectionEl.innerHTML = '<div class="empty-state">未找到当前品类的运行信息。</div>';
            return;
        }
        category.products = await window.LauncherUI.hydrateProducts(category.products || []);
        const aggregate = window.LauncherUI.categoryAggregate(category);
        banner.className = `status-banner ${window.LauncherUI.statusClass(category.status)}`;
        headlineEl.textContent = `${category.category} 品类进度`;
        captionEl.textContent = `当前品类共有 ${aggregate.totalCount} 个商品，已完成 ${aggregate.completedCount} 个。`;
        titleEl.textContent = category.category;
        noteEl.textContent = category.detail || session.note || '--';
        productCountEl.textContent = String(aggregate.totalCount);
        reviewLimitEl.textContent = String(category.reviewLimit || '--');
        currentTargetEl.textContent = category.currentProductId || '--';

        collectionEl.innerHTML = '';
        for (const product of category.products) {
            const card = document.createElement('a');
            card.className = 'nav-card';
            card.href = product.productPageUrl;
            card.innerHTML = `
                <div class="nav-card__button">
                    <div class="charge-track"><div class="charge-fill ${product.status}" style="width:${window.LauncherUI.formatPercent(product.fraction || 0)}"></div></div>
                    <div class="nav-card__content">
                        <div class="nav-card__title">${product.productId}</div>
                        <div class="nav-card__subtitle">评论数 ${product.reviewLimit || '--'} · ${product.activeText || '--'}</div>
                    </div>
                </div>
                <div class="nav-card__stats">
                    <div class="stat-line"><span class="stat-line__label">进度</span><span class="stat-line__value">${window.LauncherUI.formatPercent(product.fraction || 0)}</span></div>
                    <div class="stat-line"><span class="stat-line__label">预计剩余</span><span class="stat-line__value">${product.etaText || '--'}</span></div>
                    <div class="stat-line"><span class="stat-line__label">预计完成</span><span class="stat-line__value">${product.finishText || '--'}</span></div>
                </div>
            `;
            collectionEl.appendChild(card);
        }

        summaryEl.innerHTML = category.products.length
            ? category.products.map(product => `<div class="stat-line"><span class="stat-line__label">${product.productId}</span><span class="stat-line__value">${product.status}</span></div>`).join('')
            : '<div class="empty-state">当前品类没有已选商品。</div>';

        if (session.status !== 'completed' && session.status !== 'failed') {
            window.setTimeout(refresh, 2000);
        }
    }

    await refresh();
}

window.addEventListener('DOMContentLoaded', () => {
    void renderCategoryPage();
});