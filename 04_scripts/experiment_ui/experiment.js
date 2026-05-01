const LOG_URL = '/experiment_results/experiment_log.jsonl';
const SUMMARY_URL = '/experiment_results/experiment_summary.json';

const CONDITIONS = [
    { key: 'full_system', label: '完整系统', type: 'baseline' },
    { key: 'ablation_no_qp', label: '消融：无 Question Planning', type: 'ablation' },
    { key: 'ablation_no_image', label: '消融：无 Image Route', type: 'ablation' },
    { key: 'ablation_no_rerank', label: '消融：无 Reranking', type: 'ablation' },
    { key: 'ablation_no_attribution', label: '消融：无 Claim Attribution', type: 'ablation' },
    { key: 'control_lewis2020', label: '对照：Lewis et al. 2020', type: 'control' },
    { key: 'control_jarvis', label: '对照：JARVIS', type: 'control' },
    { key: 'control_vericite', label: '对照：VeriCite', type: 'control' },
];

const RUNNING_STALE_MS = 30 * 60 * 1000;

async function fetchLog() {
    try {
        const response = await fetch(`${LOG_URL}?t=${Date.now()}`, { cache: 'no-store' });
        if (!response.ok) return [];
        const text = await response.text();
        if (!text.trim()) return [];
        return text.trim().split('\n').map(line => {
            try { return JSON.parse(line); } catch { return null; }
        }).filter(Boolean);
    } catch {
        return [];
    }
}

async function fetchSummary() {
    try {
        const response = await fetch(`${SUMMARY_URL}?t=${Date.now()}`, { cache: 'no-store' });
        if (!response.ok) return null;
        return await response.json();
    } catch {
        return null;
    }
}

function formatDuration(seconds) {
    if (!Number.isFinite(seconds) || seconds < 0) return '--';
    const h = Math.floor(seconds / 3600);
    const m = Math.floor((seconds % 3600) / 60);
    const s = Math.round(seconds % 60);
    if (h > 0) return `${h}h ${m}m`;
    if (m > 0) return `${m}m ${s}s`;
    return `${s}s`;
}

function escapeHtml(value) {
    return String(value ?? '')
        .replace(/&/g, '&amp;')
        .replace(/</g, '&lt;')
        .replace(/>/g, '&gt;')
        .replace(/"/g, '&quot;')
        .replace(/'/g, '&#39;');
}

function latestByRunId(entries) {
    const latest = new Map();
    for (const entry of entries) {
        if (entry.run_id) latest.set(entry.run_id, entry);
    }
    return [...latest.values()];
}

function totalFromSummary(summary, latestEntries) {
    if (summary?.planned_total_runs != null) return summary.planned_total_runs;
    if (summary?.total_runs != null) return summary.total_runs;
    return latestEntries.length;
}

function isRunningSummaryStale(summary) {
    if (summary?.runner_state !== 'running' || !summary.updated_at) return false;
    const updatedAt = Date.parse(summary.updated_at);
    return Number.isFinite(updatedAt) && Date.now() - updatedAt > RUNNING_STALE_MS;
}

function render() {
    void refresh();
}

async function refresh() {
    const entries = await fetchLog();
    const summary = await fetchSummary();
    const latestEntries = latestByRunId(entries);
    const completed = latestEntries.filter(e => e.status === 'success');
    const failed = latestEntries.filter(e => e.status === 'error');
    const totalCompleted = summary?.completed_runs ?? summary?.successful_runs ?? completed.length;
    const totalFailed = summary?.failed_runs ?? failed.length;
    const totalRuns = totalFromSummary(summary, latestEntries);
    const remainingRuns = summary?.remaining_runs ?? Math.max(totalRuns - totalCompleted - totalFailed, 0);
    const skippedRuns = summary?.skipped_runs ?? 0;

    const banner = document.getElementById('status-banner');
    const headline = document.getElementById('status-headline');
    const caption = document.getElementById('status-caption');
    const stale = isRunningSummaryStale(summary);

    if (!summary && latestEntries.length === 0) {
        banner.className = 'status-banner failed';
        headline.textContent = '实验尚未启动';
        caption.textContent = '还没有找到实验日志或状态摘要';
    } else if (summary?.runner_state === 'completed' && remainingRuns === 0) {
        banner.className = totalFailed > 0 ? 'status-banner failed' : 'status-banner completed';
        headline.textContent = totalFailed > 0 ? '实验完成但有失败' : '实验全部完成';
        caption.textContent = `成功 ${totalCompleted} / ${totalRuns}，失败 ${totalFailed}，跳过 ${skippedRuns}`;
    } else if (summary?.runner_state === 'running' && !stale) {
        banner.className = 'status-banner running';
        headline.textContent = '实验运行中';
        caption.textContent = `已成功 ${totalCompleted} / ${totalRuns}，失败 ${totalFailed}，剩余 ${remainingRuns}`;
    } else if (summary?.runner_state === 'running' && stale) {
        banner.className = 'status-banner failed';
        headline.textContent = '实验状态可能已停滞';
        caption.textContent = `最后状态更新时间：${summary.updated_at}`;
    } else if (totalFailed > 0) {
        banner.className = 'status-banner failed';
        headline.textContent = '实验有失败记录';
        caption.textContent = `成功 ${totalCompleted} / ${totalRuns}，失败 ${totalFailed}`;
    } else {
        banner.className = 'status-banner completed';
        headline.textContent = '实验状态已记录';
        caption.textContent = `成功 ${totalCompleted} / ${totalRuns}`;
    }

    document.getElementById('meta-completed').textContent = totalRuns > 0 ? `${totalCompleted} / ${totalRuns}` : '--';
    document.getElementById('meta-success-rate').textContent =
        (totalCompleted + totalFailed) > 0 ? `${((totalCompleted / (totalCompleted + totalFailed)) * 100).toFixed(1)}%` : '--';

    const durations = completed
        .map(e => Number(e.duration_seconds))
        .filter(value => Number.isFinite(value) && value > 0);
    if (durations.length > 0 && remainingRuns > 0 && summary?.runner_state === 'running' && !stale) {
        const avgSeconds = durations.reduce((sum, value) => sum + value, 0) / durations.length;
        document.getElementById('meta-eta').textContent = formatDuration(avgSeconds * remainingRuns);
    } else {
        document.getElementById('meta-eta').textContent = '--';
    }

    const currentRun = summary?.current_run_id || latestEntries[latestEntries.length - 1]?.run_id;
    document.getElementById('meta-current').textContent = currentRun || '--';

    const collection = document.getElementById('condition-collection');
    collection.innerHTML = '';

    for (const cond of CONDITIONS) {
        const condEntries = latestEntries.filter(e => e.condition === cond.key);
        const condCompleted = condEntries.filter(e => e.status === 'success');
        const condFailed = condEntries.filter(e => e.status === 'error');
        const perConditionTotal = summary?.condition_totals?.[cond.key] ?? condEntries.length;
        const condFraction = perConditionTotal > 0 ? condCompleted.length / perConditionTotal : 0;
        const fillState = condCompleted.length === perConditionTotal && perConditionTotal > 0
            ? 'completed'
            : condFailed.length > 0 && condCompleted.length === 0
                ? 'failed'
                : 'running';

        const typeBadge = cond.type === 'baseline'
            ? '<span class="badge baseline">基线</span>'
            : cond.type === 'ablation'
                ? '<span class="badge ablation">消融</span>'
                : '<span class="badge control">对照</span>';

        const card = document.createElement('div');
        card.className = 'nav-card';
        card.innerHTML = `
            <div class="nav-card__button">
                <div class="charge-track"><div class="charge-fill ${fillState}" style="width:${Math.min(condFraction * 100, 100).toFixed(1)}%"></div></div>
                <div class="nav-card__content">
                    <div class="nav-card__title">${escapeHtml(cond.label)} ${typeBadge}</div>
                    <div class="nav-card__subtitle">${condCompleted.length}/${perConditionTotal || '--'} 个商品已完成 · ${condFailed.length} 个失败</div>
                </div>
            </div>
            <div class="nav-card__stats">
                <div class="stat-line"><span class="stat-line__label">进度</span><span class="stat-line__value">${perConditionTotal > 0 ? (condFraction * 100).toFixed(1) : '--'}%</span></div>
                <div class="stat-line"><span class="stat-line__label">平均 Aspects</span><span class="stat-line__value">${condCompleted.length > 0 ? (condCompleted.reduce((s, e) => s + (e.aspect_count || 0), 0) / condCompleted.length).toFixed(1) : '--'}</span></div>
                <div class="stat-line"><span class="stat-line__label">平均 Claims</span><span class="stat-line__value">${condCompleted.length > 0 ? (condCompleted.reduce((s, e) => s + (e.claim_count || 0), 0) / condCompleted.length).toFixed(1) : '--'}</span></div>
            </div>
        `;
        collection.appendChild(card);
    }

    const recentEl = document.getElementById('recent-runs');
    recentEl.innerHTML = '';
    const recent = entries.slice(-10).reverse();
    if (recent.length === 0) {
        recentEl.innerHTML = '<div class="empty-state">暂无运行记录</div>';
    } else {
        for (const entry of recent) {
            const row = document.createElement('div');
            row.className = 'stat-line';
            const statusDot = entry.status === 'success'
                ? '<span style="color:#248a3d">●</span>'
                : '<span style="color:#c9342f">●</span>';
            row.innerHTML = `
                <span class="stat-line__label">${statusDot} ${escapeHtml(entry.condition)}</span>
                <span class="stat-line__value" style="font-size:12px">${escapeHtml(entry.category)}/${escapeHtml(entry.product_id)}</span>
            `;
            recentEl.appendChild(row);
        }
    }

    const shouldPoll = !summary || summary.runner_state !== 'completed' || remainingRuns > 0;
    if (shouldPoll) {
        window.setTimeout(refresh, 3000);
    }
}

window.addEventListener('DOMContentLoaded', () => {
    void render();
});
