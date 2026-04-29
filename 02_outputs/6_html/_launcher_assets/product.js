async function renderProductPage() {
    const stateUrl = document.body.dataset.sessionStateUrl;
    const categoryKey = document.body.dataset.category;
    const productKey = document.body.dataset.productId;
    const titleEl = document.getElementById('page-title');
    const noteEl = document.getElementById('page-note');
    const banner = document.getElementById('status-banner');
    const headlineEl = document.getElementById('status-headline');
    const captionEl = document.getElementById('status-caption');
    const reviewLimitEl = document.getElementById('meta-review-limit');
    const progressEl = document.getElementById('meta-progress');
    const etaEl = document.getElementById('meta-eta');
    const finishEl = document.getElementById('meta-finish');
    const viewerEl = document.getElementById('product-viewer');
    const summaryEl = document.getElementById('summary-body');

    async function refresh() {
        const session = await window.LauncherUI.fetchJson(stateUrl);
        const category = (session.categories || []).find(item => item.category === categoryKey);
        const product = category?.products?.find(item => item.productId === productKey);
        if (!category || !product) {
            viewerEl.innerHTML = '<div class="empty-state">未找到当前商品的运行信息。</div>';
            return;
        }
        const hydrated = (await window.LauncherUI.hydrateProducts([product]))[0];
        banner.className = `status-banner ${window.LauncherUI.statusClass(hydrated.status)}`;
        headlineEl.textContent = `${productKey} 商品详情`;
        captionEl.textContent = `这里展示的是 ${productKey} 的详细进度页，保留你之前习惯的单商品视图。`;
        titleEl.textContent = `${categoryKey} / ${productKey}`;
        noteEl.textContent = hydrated.activeText || product.detail || session.note || '--';
        reviewLimitEl.textContent = String(hydrated.reviewLimit || '--');
        progressEl.textContent = window.LauncherUI.formatPercent(hydrated.fraction || 0);
        etaEl.textContent = hydrated.etaText || '--';
        finishEl.textContent = hydrated.finishText || '--';

        viewerEl.innerHTML = hydrated.liveProgressUrl
            ? `<iframe class="viewer-frame" src="${hydrated.liveProgressUrl}" title="${productKey}-live-progress"></iframe>`
            : '<div class="empty-state">当前商品还没有 live 进度页。</div>';

        summaryEl.innerHTML = `
            <div class="stat-line"><span class="stat-line__label">状态</span><span class="stat-line__value">${hydrated.status}</span></div>
            <div class="stat-line"><span class="stat-line__label">开始时间</span><span class="stat-line__value">${hydrated.startedAt || '--'}</span></div>
            <div class="stat-line"><span class="stat-line__label">完成时间</span><span class="stat-line__value">${hydrated.completedAt || '--'}</span></div>
            <div class="stat-line"><span class="stat-line__label">退出码</span><span class="stat-line__value">${hydrated.exitCode ?? '--'}</span></div>
        `;

        if (session.status !== 'completed' && session.status !== 'failed') {
            window.setTimeout(refresh, 2000);
        }
    }

    await refresh();
}

window.addEventListener('DOMContentLoaded', () => {
    void renderProductPage();
});