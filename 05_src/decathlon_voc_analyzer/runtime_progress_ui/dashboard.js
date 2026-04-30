const progressStateUrl = new URL(window.location.pathname.replace(/\.html$/, '.state.json'), window.location.origin).toString();
const fmtPercent = value => `${(value * 100).toFixed(1)}%`;
const statusClass = status => status === 'in_progress' ? 'running' : status === 'failed' ? 'broken' : status;
const modulesEl = document.getElementById('modules');
const rawEl = document.getElementById('raw');

function renderProgressDashboard(payload) {
    const banner = document.getElementById('status-banner');
    const bannerClass = payload.workflowStatus === 'completed' ? 'complete' : payload.workflowStatus === 'failed' ? 'failed' : 'running';
    banner.className = `status-banner ${bannerClass}`;
    document.getElementById('workflow-headline').textContent = payload.workflowHeadline ?? '--';
    document.getElementById('workflow-caption').textContent = payload.workflowCaption ?? '--';
    document.getElementById('workflow-note').textContent = payload.note || 'Workflow is running';
    document.getElementById('overall-percent').textContent = fmtPercent(payload.overallFraction || 0);
    document.getElementById('overall-meta').textContent = `ETA ${payload.overallEta ?? '--'} · Finish ${payload.overallFinish ?? '--'}`;
    document.getElementById('active-module').textContent = payload.activeModule ?? '--';
    document.getElementById('module-meta').textContent = `ETA ${payload.activeModuleEta ?? '--'} · Finish ${payload.activeModuleFinish ?? '--'}`;
    document.getElementById('active-step').textContent = payload.activeStep ?? '--';
    document.getElementById('step-meta').textContent = `ETA ${payload.activeStepEta ?? '--'} · Finish ${payload.activeStepFinish ?? '--'}`;
    document.getElementById('elapsed').textContent = payload.elapsed ?? '--';

    modulesEl.innerHTML = '';
    for (const module of payload.modules || []) {
        const moduleEl = document.createElement('div');
        moduleEl.className = 'module';
        const stepsHtml = (module.steps || []).map(step => `
            <div class="step ${step.isActive ? 'active' : ''}">
                <div class="row"><strong>${step.label}</strong><span class="status ${statusClass(step.status)}">${step.statusLabel}</span></div>
                <div class="bar"><div class="fill" style="width:${fmtPercent(step.fraction || 0)}"></div></div>
                <div class="detail">${step.detail || ''}</div>
                <div class="detail">${step.meta || ''}</div>
            </div>
        `).join('');
        moduleEl.innerHTML = `
            <div class="row"><strong>${module.label}</strong><span class="status ${statusClass(module.status)}">${module.statusLabel}</span></div>
            <div class="bar"><div class="fill" style="width:${fmtPercent(module.fraction || 0)}"></div></div>
            <div class="detail">${module.detail || ''}</div>
            <div class="detail">${module.meta || ''}</div>
            <div class="steps">${stepsHtml}</div>
        `;
        modulesEl.appendChild(moduleEl);
    }
    rawEl.textContent = JSON.stringify(payload, null, 2);
}

async function pollProgressState(initialPayload) {
    try {
        const response = await fetch(`${progressStateUrl}?t=${Date.now()}`, { cache: 'no-store' });
        if (!response.ok) {
            throw new Error(`HTTP ${response.status}`);
        }
        const statePayload = await response.json();
        const nextPayload = statePayload.dashboard ?? initialPayload;
        renderProgressDashboard(nextPayload);
        if (nextPayload.workflowStatus === 'completed' || nextPayload.workflowStatus === 'failed') {
            return;
        }
    } catch (_error) {
    }
    window.setTimeout(() => pollProgressState(initialPayload), 2000);
}

window.ProgressDashboard = {
    renderProgressDashboard,
    pollProgressState,
};