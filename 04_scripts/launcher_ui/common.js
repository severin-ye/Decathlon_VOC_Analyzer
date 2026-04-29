function launcherWithBust(url) {
    return `${url}${url.includes('?') ? '&' : '?'}t=${Date.now()}`;
}

async function launcherFetchJson(url) {
    const response = await fetch(launcherWithBust(url), { cache: 'no-store' });
    if (!response.ok) {
        throw new Error(`HTTP ${response.status}`);
    }
    return response.json();
}

function launcherFormatPercent(value) {
    const normalized = Number.isFinite(value) ? Math.max(0, Math.min(1, value)) : 0;
    return `${(normalized * 100).toFixed(1)}%`;
}

function launcherIsoToMs(value) {
    if (!value) {
        return null;
    }
    const parsed = Date.parse(value);
    return Number.isFinite(parsed) ? parsed : null;
}

function launcherFormatDuration(seconds) {
    if (!Number.isFinite(seconds) || seconds < 0) {
        return '--';
    }
    const rounded = Math.round(seconds);
    const hours = Math.floor(rounded / 3600);
    const minutes = Math.floor((rounded % 3600) / 60);
    const secs = rounded % 60;
    if (hours > 0) {
        return `${hours}h ${minutes}m`;
    }
    if (minutes > 0) {
        return `${minutes}m ${secs}s`;
    }
    return `${secs}s`;
}

function launcherFormatClockFromNow(seconds) {
    if (!Number.isFinite(seconds) || seconds < 0) {
        return '--';
    }
    const date = new Date(Date.now() + seconds * 1000);
    return date.toLocaleTimeString('zh-CN', { hour: '2-digit', minute: '2-digit', second: '2-digit', hour12: false });
}

function launcherProductStaticProgress(product) {
    if (product.status === 'completed') {
        return 1;
    }
    if (product.status === 'failed') {
        return 0;
    }
    return 0;
}

function launcherAverageCompletedDurationMs(products) {
    const durations = products
        .map(product => {
            const started = launcherIsoToMs(product.startedAt);
            const completed = launcherIsoToMs(product.completedAt);
            if (started === null || completed === null || completed <= started) {
                return null;
            }
            return completed - started;
        })
        .filter(value => value !== null);
    if (!durations.length) {
        return null;
    }
    return durations.reduce((sum, value) => sum + value, 0) / durations.length;
}

async function launcherReadProductRuntime(product) {
    if (!product.liveProgressStateUrl) {
        return null;
    }
    try {
        const payload = await launcherFetchJson(product.liveProgressStateUrl);
        return payload.dashboard || null;
    } catch (_error) {
        return null;
    }
}

async function launcherHydrateProducts(products) {
    const runtimes = await Promise.all(products.map(product => launcherReadProductRuntime(product)));
    return products.map((product, index) => {
        const runtime = runtimes[index];
        const fraction = runtime ? (runtime.overallFraction || 0) : launcherProductStaticProgress(product);
        const status = runtime
            ? (runtime.workflowStatus === 'completed' ? 'completed' : (product.status === 'failed' ? 'failed' : 'running'))
            : product.status;
        return {
            ...product,
            runtime,
            fraction,
            status,
            etaSeconds: runtime && Number.isFinite(runtime.overallEtaSeconds) ? runtime.overallEtaSeconds : null,
            etaText: runtime?.overallEta || '--',
            finishText: runtime?.overallFinish || '--',
            activeText: runtime?.activeStep || runtime?.note || product.detail || '--',
        };
    });
}

function launcherCategoryAggregate(category) {
    const products = category.products || [];
    const total = products.length || 1;
    const fraction = products.reduce((sum, product) => sum + (product.fraction || 0), 0) / total;
    const completedCount = products.filter(product => product.status === 'completed').length;
    const runningProducts = products.filter(product => product.status === 'running');
    const pendingCount = products.filter(product => product.status === 'pending').length;
    const averageDurationMs = launcherAverageCompletedDurationMs(products);
    let etaSeconds = null;
    if (runningProducts.length && Number.isFinite(runningProducts[0].etaSeconds)) {
        etaSeconds = runningProducts[0].etaSeconds;
        if (averageDurationMs !== null) {
            etaSeconds += (pendingCount + Math.max(0, runningProducts.length - 1)) * (averageDurationMs / 1000);
        }
    } else if (averageDurationMs !== null && pendingCount > 0) {
        etaSeconds = pendingCount * (averageDurationMs / 1000);
    }
    const finishText = etaSeconds !== null ? launcherFormatClockFromNow(etaSeconds) : '--';
    const status = category.status === 'failed'
        ? 'failed'
        : (completedCount === products.length && products.length > 0 ? 'completed' : (runningProducts.length ? 'running' : category.status));
    return {
        fraction,
        completedCount,
        totalCount: products.length,
        etaSeconds,
        etaText: etaSeconds !== null ? launcherFormatDuration(etaSeconds) : '--',
        finishText,
        status,
    };
}

function launcherStatusHeadline(status) {
    if (status === 'completed') {
        return '已完成所有流程';
    }
    if (status === 'failed') {
        return '流程执行失败';
    }
    return '工作流运行中';
}

function launcherStatusClass(status) {
    if (status === 'completed') {
        return 'completed';
    }
    if (status === 'failed') {
        return 'failed';
    }
    return 'running';
}

window.LauncherUI = {
    fetchJson: launcherFetchJson,
    hydrateProducts: launcherHydrateProducts,
    categoryAggregate: launcherCategoryAggregate,
    formatPercent: launcherFormatPercent,
    formatDuration: launcherFormatDuration,
    formatClockFromNow: launcherFormatClockFromNow,
    statusHeadline: launcherStatusHeadline,
    statusClass: launcherStatusClass,
};