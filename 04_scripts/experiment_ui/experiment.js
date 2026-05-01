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

function latestRunMap(entries, summary) {
    const latest = new Map();
    for (const entry of [...entries, ...(summary?.runs || [])]) {
        if (entry.run_id) latest.set(entry.run_id, entry);
    }
    return latest;
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

function conditionByKey(key) {
    return CONDITIONS.find(cond => cond.key === key) || { key, label: key, type: 'control' };
}

function runIdFor(category, productId, condition) {
    return `${category}__${productId}__${condition}`;
}

function experimentUrl(params = {}) {
    const search = new URLSearchParams();
    for (const [key, value] of Object.entries(params)) {
        if (value) search.set(key, value);
    }
    return `experiment.html${search.toString() ? `?${search.toString()}` : ''}`;
}

function setBreadcrumbs(items) {
    const breadcrumbs = document.getElementById('breadcrumbs');
    breadcrumbs.innerHTML = items.map((item, index) => {
        const label = escapeHtml(item.label);
        if (!item.href) return `<li>${label}</li>`;
        return `<li><a href="${escapeHtml(item.href)}">${label}</a></li>${index < items.length - 1 ? '<li>/</li>' : ''}`;
    }).join('');
}

function statusDot(status) {
    if (status === 'success') return '<span style="color:#248a3d">●</span>';
    if (status === 'error') return '<span style="color:#c9342f">●</span>';
    return '<span style="color:#d28b00">●</span>';
}

function runStatusLabel(entry, summary) {
    if (entry.status === 'success') return '成功';
    if (entry.status === 'error') return '失败';
    if (summary?.current_run_id === entry.run_id && summary?.runner_state === 'running') return '运行中';
    return '待运行';
}

function runStatusClass(entry, summary) {
    if (entry.status === 'success') return 'completed';
    if (entry.status === 'error') return 'failed';
    if (summary?.current_run_id === entry.run_id && summary?.runner_state === 'running') return 'running';
    return 'running';
}

function runDetailHref(entry) {
    return entry.progress_dashboard_url || experimentUrl({ run: entry.run_id });
}

function buildPlannedRuns(summary, runMap, conditionKey = null) {
    const selectedProducts = summary?.selected_products || {};
    const categories = summary?.categories || Object.keys(selectedProducts);
    const conditionKeys = conditionKey ? [conditionKey] : (summary?.conditions || CONDITIONS.map(cond => cond.key));
    const runs = [];
    for (const category of categories) {
        for (const productId of selectedProducts[category] || []) {
            for (const condition of conditionKeys) {
                const run_id = runIdFor(category, productId, condition);
                runs.push({
                    run_id,
                    category,
                    product_id: productId,
                    condition,
                    status: 'pending',
                    ...(runMap.get(run_id) || {}),
                });
            }
        }
    }
    return runs;
}

function updateMetaCard(index, label, value, sub) {
    const card = document.querySelectorAll('.meta-card')[index];
    if (!card) return;
    card.querySelector('.meta-label').textContent = label;
    card.querySelector('.meta-value').textContent = value;
    card.querySelector('.meta-sub').textContent = sub;
}

function render() {
    void refresh();
}

async function refresh() {
    const entries = await fetchLog();
    const summary = await fetchSummary();
    const runMap = latestRunMap(entries, summary);
    const latestEntries = [...runMap.values()];
    const params = new URLSearchParams(window.location.search);
    const runId = params.get('run');
    const conditionKey = params.get('condition');
    if (runId) {
        renderRunDetail(entries, summary, runMap, runId);
        return;
    }
    if (conditionKey) {
        renderConditionDetail(entries, summary, runMap, conditionKey);
        return;
    }
    renderOverview(entries, summary, latestEntries);
}

function renderOverview(entries, summary, latestEntries) {
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
    setBreadcrumbs([{ label: '总览' }]);
    document.getElementById('page-title').textContent = '消融实验与对照实验';
    document.getElementById('page-note').textContent = `实时追踪 ${CONDITIONS.length} 个实验条件在 ${Object.values(summary?.selected_products || {}).reduce((sum, products) => sum + products.length, 0) || 15} 个商品上的运行进度`;
    updateMetaCard(0, '已完成', '--', '成功 / 总计');
    updateMetaCard(1, '成功率', '--', '成功运行占比');
    updateMetaCard(2, '预计剩余', '--', '基于平均单条耗时');
    updateMetaCard(3, '当前运行', '--', '品类 / 商品 / 条件');

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

        const link = document.createElement('a');
        link.className = 'nav-card';
        link.href = experimentUrl({ condition: cond.key });
        link.innerHTML = `
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
        collection.appendChild(link);
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

function renderConditionDetail(entries, summary, runMap, conditionKey) {
    const condition = conditionByKey(conditionKey);
    let runs = buildPlannedRuns(summary, runMap, conditionKey);
    if (runs.length === 0) {
        runs = latestByRunId(entries.filter(entry => entry.condition === conditionKey));
    }
    const completed = runs.filter(entry => entry.status === 'success');
    const failed = runs.filter(entry => entry.status === 'error');
    const total = summary?.condition_totals?.[conditionKey] ?? runs.length;
    const current = runs.find(entry => summary?.current_run_id === entry.run_id);
    const fraction = total > 0 ? completed.length / total : 0;
    const averageDuration = completed.length > 0
        ? completed.reduce((sum, entry) => sum + (Number(entry.duration_seconds) || 0), 0) / completed.length
        : Number.NaN;

    setBreadcrumbs([
        { label: '总览', href: experimentUrl() },
        { label: condition.label },
    ]);
    document.getElementById('page-title').textContent = condition.label;
    document.getElementById('page-note').textContent = '点击商品运行记录可查看该 run 的模块与细分步骤进度。';
    document.getElementById('status-banner').className = failed.length > 0 && completed.length === 0
        ? 'status-banner failed'
        : (completed.length === total && total > 0 ? 'status-banner completed' : 'status-banner running');
    document.getElementById('status-headline').textContent = `${condition.label} 进度`;
    document.getElementById('status-caption').textContent = `成功 ${completed.length} / ${total || '--'}，失败 ${failed.length}，当前 ${current?.product_id || '--'}`;
    updateMetaCard(0, '已完成', total > 0 ? `${completed.length} / ${total}` : '--', '当前条件成功运行数');
    updateMetaCard(1, '失败数', String(failed.length), '当前条件失败运行数');
    updateMetaCard(2, '平均耗时', formatDuration(averageDuration), '成功 run 平均耗时');
    updateMetaCard(3, '当前商品', current?.product_id || '--', '正在运行的商品');

    document.querySelector('.panel h2').textContent = '商品运行记录';
    document.querySelector('aside.panel h2').textContent = '条件摘要';
    const collection = document.getElementById('condition-collection');
    collection.innerHTML = '';
    if (runs.length === 0) {
        collection.innerHTML = '<div class="empty-state">当前还没有实验计划信息。</div>';
    } else {
        for (const entry of runs) {
            const card = document.createElement('a');
            card.className = 'nav-card';
            card.href = runDetailHref(entry);
            const statusClassName = runStatusClass(entry, summary);
            const runFraction = entry.status === 'success' ? 1 : (summary?.current_run_id === entry.run_id ? 0.5 : 0);
            card.innerHTML = `
                <div class="nav-card__button">
                    <div class="charge-track"><div class="charge-fill ${statusClassName}" style="width:${(runFraction * 100).toFixed(1)}%"></div></div>
                    <div class="nav-card__content">
                        <div class="nav-card__title">${statusDot(entry.status)} ${escapeHtml(entry.product_id)}</div>
                        <div class="nav-card__subtitle">${escapeHtml(entry.category)} · ${runStatusLabel(entry, summary)} · ${entry.progress_dashboard_url ? '可查看实时阶段' : '静态详情'}</div>
                    </div>
                </div>
                <div class="nav-card__stats">
                    <div class="stat-line"><span class="stat-line__label">Aspects</span><span class="stat-line__value">${entry.aspect_count ?? '--'}</span></div>
                    <div class="stat-line"><span class="stat-line__label">Questions</span><span class="stat-line__value">${entry.question_count ?? '--'}</span></div>
                    <div class="stat-line"><span class="stat-line__label">Claims</span><span class="stat-line__value">${entry.claim_count ?? '--'}</span></div>
                </div>
            `;
            collection.appendChild(card);
        }
    }

    const recentEl = document.getElementById('recent-runs');
    recentEl.innerHTML = `
        <div class="stat-line"><span class="stat-line__label">进度</span><span class="stat-line__value">${total > 0 ? (fraction * 100).toFixed(1) : '--'}%</span></div>
        <div class="stat-line"><span class="stat-line__label">平均 Aspects</span><span class="stat-line__value">${completed.length > 0 ? (completed.reduce((sum, entry) => sum + (entry.aspect_count || 0), 0) / completed.length).toFixed(1) : '--'}</span></div>
        <div class="stat-line"><span class="stat-line__label">平均 Claims</span><span class="stat-line__value">${completed.length > 0 ? (completed.reduce((sum, entry) => sum + (entry.claim_count || 0), 0) / completed.length).toFixed(1) : '--'}</span></div>
    `;

    if (!summary || summary.runner_state !== 'completed') {
        window.setTimeout(refresh, 3000);
    }
}

function renderRunDetail(entries, summary, runMap, runId) {
    const fallbackParts = runId.split('__');
    const entry = runMap.get(runId) || {
        run_id: runId,
        category: fallbackParts[0] || '--',
        product_id: fallbackParts[1] || '--',
        condition: fallbackParts[2] || '--',
        status: 'pending',
    };
    const condition = conditionByKey(entry.condition);
    setBreadcrumbs([
        { label: '总览', href: experimentUrl() },
        { label: condition.label, href: experimentUrl({ condition: entry.condition }) },
        { label: entry.product_id },
    ]);
    document.getElementById('page-title').textContent = entry.run_id;
    document.getElementById('page-note').textContent = entry.progress_dashboard_url
        ? '此 run 已生成实时阶段页面，可从下方入口打开完整模块详情。'
        : '旧日志或尚未开始的 run 没有实时阶段页面，下方展示已记录的静态结果。';
    document.getElementById('status-banner').className = `status-banner ${runStatusClass(entry, summary)}`;
    document.getElementById('status-headline').textContent = runStatusLabel(entry, summary);
    document.getElementById('status-caption').textContent = entry.error || `${entry.category} / ${entry.product_id} / ${condition.label}`;
    updateMetaCard(0, '状态', runStatusLabel(entry, summary), '当前 run 状态');
    updateMetaCard(1, '模式', entry.analysis_mode || '--', '分析或对照模式');
    updateMetaCard(2, '耗时', formatDuration(Number(entry.duration_seconds)), '已记录运行耗时');
    updateMetaCard(3, 'Claims', entry.claim_count != null ? `${entry.supported_claims ?? 0} / ${entry.claim_count}` : '--', 'supported / total');

    document.querySelector('.panel h2').textContent = '细分阶段';
    document.querySelector('aside.panel h2').textContent = '运行详情';
    const collection = document.getElementById('condition-collection');
    const dashboardLink = entry.progress_dashboard_url
        ? `<a class="detail-link" href="${escapeHtml(entry.progress_dashboard_url)}">打开实时阶段 Dashboard</a>`
        : '<div class="empty-state">没有可打开的实时阶段 Dashboard。</div>';
    collection.innerHTML = `
        ${dashboardLink}
        <div class="stage-list">
            <div class="stat-line"><span class="stat-line__label">抽取评论 / Aspects</span><span class="stat-line__value">${entry.aspect_count ?? '--'}</span></div>
            <div class="stat-line"><span class="stat-line__label">问题规划 / Questions</span><span class="stat-line__value">${entry.question_count ?? '--'}</span></div>
            <div class="stat-line"><span class="stat-line__label">检索证据 / Retrievals</span><span class="stat-line__value">${entry.retrieval_count ?? '--'}</span></div>
            <div class="stat-line"><span class="stat-line__label">Claim 归因</span><span class="stat-line__value">${entry.claim_count ?? '--'}</span></div>
            <div class="stat-line"><span class="stat-line__label">产物落盘</span><span class="stat-line__value">${entry.artifact_path ? '已写入' : '--'}</span></div>
        </div>
    `;

    const recentEl = document.getElementById('recent-runs');
    recentEl.innerHTML = `
        <div class="stat-line"><span class="stat-line__label">Category</span><span class="stat-line__value">${escapeHtml(entry.category)}</span></div>
        <div class="stat-line"><span class="stat-line__label">Product</span><span class="stat-line__value">${escapeHtml(entry.product_id)}</span></div>
        <div class="stat-line"><span class="stat-line__label">Condition</span><span class="stat-line__value">${escapeHtml(condition.label)}</span></div>
        <div class="stat-line"><span class="stat-line__label">Started</span><span class="stat-line__value">${escapeHtml(entry.started_at || '--')}</span></div>
        <div class="stat-line"><span class="stat-line__label">Finished</span><span class="stat-line__value">${escapeHtml(entry.finished_at || '--')}</span></div>
    `;

    if (!summary || (summary.runner_state !== 'completed' && summary.current_run_id === runId)) {
        window.setTimeout(refresh, 3000);
    }
}

window.addEventListener('DOMContentLoaded', () => {
    void render();
});
