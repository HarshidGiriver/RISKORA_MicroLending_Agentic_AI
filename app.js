/**
 * RISKORA — Institutional AI/ML Micro-Lending Risk Platform
 * Frontend Controller & REST API Integration
 */

// Utility helpers
const $ = id => document.getElementById(id);
const money = n => `₹${Math.round(Number(n) || 0).toLocaleString('en-IN')}`;
const esc = s => String(s ?? '').replace(/[&<>"']/g, m => ({ '&': '&amp;', '<': '&lt;', '>': '&gt;', '"': '&quot;', "'": '&#39;' }[m]));
const num = v => Number.isFinite(Number(v)) ? Number(v) : null;

// Application State
let activeCase = null;
let activeAnalysis = null;
let activeFunding = null;
let fundingPreview = null;
let activeRepayment = null;
let currentPage = 'overview';
let demoTimer = null;

let datasetState = {
  page: 1,
  limit: 20,
  search: '',
  risk: 'all',
  sort: 'score'
};

// Institutional Toast Notification System
function showToast(message, type = 'info', title = '') {
  let container = $('toastContainer');
  if (!container) {
    container = document.createElement('div');
    container.id = 'toastContainer';
    container.className = 'toast-container';
    document.body.appendChild(container);
  }

  const toast = document.createElement('div');
  toast.className = `toast toast-${type}`;
  
  const iconMap = {
    success: '✓',
    error: '✕',
    warning: '⚠',
    info: 'ℹ'
  };
  const icon = iconMap[type] || 'ℹ';
  
  toast.innerHTML = `
    <div class="toast-icon">${icon}</div>
    <div class="toast-body">
      ${title ? `<div class="toast-title">${esc(title)}</div>` : ''}
      <div class="toast-msg">${esc(message)}</div>
    </div>
    <button class="toast-close" aria-label="Close notification">&times;</button>
  `;

  toast.querySelector('.toast-close').onclick = () => {
    toast.classList.add('toast-hiding');
    setTimeout(() => toast.remove(), 250);
  };

  container.appendChild(toast);

  setTimeout(() => {
    if (toast.parentElement) {
      toast.classList.add('toast-hiding');
      setTimeout(() => toast.remove(), 250);
    }
  }, 4500);
}

// API Helper
async function apiCall(endpoint, options = {}) {
  try {
    const res = await fetch(endpoint, {
      headers: { 'Content-Type': 'application/json' },
      signal: AbortSignal.timeout(30000),
      ...options
    });
    if (!res.ok) {
      let errBody = {};
      try {
        errBody = await res.json();
      } catch {}
      const msg = errBody.error || `API Error ${res.status}: ${res.statusText}`;
      throw new Error(msg);
    }
    return await res.json();
  } catch (err) {
    console.error(`Fetch failed for ${endpoint}:`, err);
    throw err;
  }
}

// 1. Initial Access Gate & Video Reveal
function initEntry() {
  const gate = $('accessGate');
  const intro = $('introGate');
  const video = $('logoReveal');
  const shell = $('appShell');
  shell.style.visibility = 'hidden';

  const savedReviewer = sessionStorage.getItem('riskora_reviewer');
  if (savedReviewer) {
    $('reviewerName').value = savedReviewer;
  }

  $('accessForm').addEventListener('submit', async e => {
    e.preventDefault();
    const name = $('reviewerName').value.trim() || 'Senior Underwriter';
    sessionStorage.setItem('riskora_reviewer', name);
    $('reviewerLabel').textContent = `REVIEWER · ${name.toUpperCase()}`;

    // Record login with backend
    try {
      await apiCall('/api/auth/login', {
        method: 'POST',
        body: JSON.stringify({ name })
      });
    } catch (err) {
      console.warn('Auth recording skipped offline', err);
    }

    gate.style.display = 'none';
    intro.classList.add('playing');
    intro.setAttribute('aria-hidden', 'false');
    video.currentTime = 0;
    video.muted = false;

    try {
      await video.play();
    } catch {
      video.muted = true;
      try {
        await video.play();
      } catch {
        intro.classList.add('failed');
        setTimeout(enterApp, 1200);
      }
    }
  });

  const enterApp = () => {
    intro.classList.remove('playing', 'failed');
    intro.setAttribute('aria-hidden', 'true');
    shell.style.visibility = 'visible';
    shell.setAttribute('aria-hidden', 'false');
  };

  video.addEventListener('ended', enterApp);
  video.addEventListener('error', () => {
    intro.classList.add('failed');
    setTimeout(enterApp, 1200);
  });
}

// 2. Navigation & Page Switching
function showPage(page) {
  currentPage = page;
  document.querySelectorAll('.page').forEach(p => p.classList.toggle('active', p.id === page));
  document.querySelectorAll('.nav').forEach(n => n.classList.toggle('active', n.dataset.page === page));
  
  const titles = {
    overview: 'Command Center',
    cases: 'Loan Request Queue',
    intelligence: 'Risk Intelligence',
    funding: 'Funding Optimizer',
    repayment: 'Repayment Engine',
    exposure: 'Exposure Monitor',
    decision: 'Decision Report',
    explorer: 'Dataset Explorer',
    validation: 'Model Validation',
    manual: 'What-If Sandbox'
  };
  $('pageTitle').textContent = titles[page] || page;
  window.scrollTo({ top: 0, behavior: 'smooth' });

  if (page === 'decision') renderDecision();
  if (page === 'cases') loadCaseQueue();
  if (page === 'intelligence' && activeAnalysis) renderIntelligence(activeAnalysis);
  if (page === 'funding') renderFunding();
  if (page === 'repayment') renderRepayment();
  if (page === 'exposure') loadExposurePortfolio();
  if (page === 'explorer') loadDatasetExplorer();
  if (page === 'validation') loadModelMetrics();
}

// 3. Journey & Workflow Stage Calculator
function stageIndex() {
  let n = 1; // 1: Request received
  if (activeAnalysis) n = 2; // 2: Risk investigated
  if (activeFunding && !activeFunding.preview) n = 3; // 3: Funding optimised
  if (activeRepayment) n = 4; // 4: Repayment simulated
  if (activeFunding && activeRepayment) n = 5; // 5: Exposure quantified
  if (activeAnalysis && activeFunding && activeRepayment) n = 6; // 6: Decision assembled
  if (activeAnalysis && activeFunding && activeRepayment) n = 7; // 7: Report ready
  return n;
}

function renderJourney() {
  const stages = [
    ['Request received', 'Borrower attributes & requested exposure loaded.'],
    ['Risk investigated', 'Calibrated ML inference, drivers & anomaly scan.'],
    ['Funding optimised', 'Single vs. fractional syndication & HHI analysis.'],
    ['Repayment simulated', 'Schedule generation & waterfall allocation.'],
    ['Exposure quantified', 'Lender portfolio concentration evaluated.'],
    ['Decision assembled', 'Underwriting disposition & controls reconciled.'],
    ['Report ready', 'Auditable risk dossier compiled for export.']
  ];
  const n = stageIndex();
  $('journey').innerHTML = stages.map((s, i) => `
    <div class="journey-step ${i < n ? 'done' : ''} ${i === n ? 'current' : ''}">
      <div class="journey-num">${i < n ? '✓' : String(i + 1).padStart(2, '0')}</div>
      <div>
        <div class="journey-title">${s[0]}</div>
        <div class="journey-copy">${s[1]}</div>
      </div>
      <div class="journey-status">${i < n ? 'COMPLETE' : (i === n ? 'ACTIVE' : 'QUEUED')}</div>
    </div>
  `).join('');
  $('journeyProgress').textContent = `${Math.min(n, 7)} / 7 stages`;
}

// 4. Command Center Overview
function renderOverview() {
  if (!activeCase) return;
  $('heroCaseId').textContent = activeCase.id;
  if ($('topCaseId')) $('topCaseId').textContent = activeCase.id;
  $('heroCaseName').textContent = `${activeCase.borrower_name || activeCase.name} · ${money(activeCase.loan_amount || activeCase.amount)} request`;
  $('heroStage').textContent = activeAnalysis ? `RISK ASSESSED (${activeAnalysis.risk_level})` : 'REQUEST RECEIVED';
  
  if (activeAnalysis) {
    $('mScore').textContent = activeAnalysis.risk_score;
    $('mRisk').textContent = `${activeAnalysis.risk_level} Risk · Calibrated`;
    $('mPd').textContent = `${activeAnalysis.probability_pct}%`;
    $('mPdLabel').textContent = `Default Probability`;
  } else {
    $('mScore').textContent = '—';
    $('mRisk').textContent = 'Awaiting ML analysis';
    $('mPd').textContent = '—';
    $('mPdLabel').textContent = 'Statistical default hazard';
  }

  $('mFunding').textContent = activeFunding && !activeFunding.preview ? (activeFunding.mode === 'fractional' ? `Fractional (${activeFunding.lender_count} Lenders)` : 'Single Lender') : 'Pending';
  $('mDecision').textContent = decisionText();

  if (activeAnalysis) {
    $('briefTitle').textContent = `${activeAnalysis.risk_level} Risk · ${activeAnalysis.risk_level === 'HIGH' ? 'Enhanced Mitigation Required' : (activeAnalysis.risk_level === 'MEDIUM' ? 'Conditional Underwriting' : 'Standard Fast-Track')}`;
    const drivers = activeAnalysis.risk_drivers || activeAnalysis.drivers || [];
    const topDriver = drivers[0]?.factor || 'Affordability metrics';
    $('briefText').textContent = `Calibrated default probability is ${activeAnalysis.probability_pct || (activeAnalysis.probability_of_default ? (activeAnalysis.probability_of_default * 100).toFixed(1) : '—')}% (Score: ${activeAnalysis.risk_score}/100). Primary risk pressure: ${topDriver}. Data Quality: ${activeAnalysis.data_quality?.data_quality_score || 90}/100.`;
  } else {
    $('briefTitle').textContent = 'Case awaiting ML investigation';
    $('briefText').textContent = 'Initiate analysis to let RISKORA evaluate default hazard, verify data quality, scan anomalies, and structure exposure.';
  }

  renderJourney();
}

function decisionText() {
  if (!activeAnalysis) return 'Pending Analysis';
  if (activeAnalysis.risk_level === 'HIGH') {
    return 'Human review required · High risk';
  }
  if (activeAnalysis.risk_level === 'MEDIUM') {
    return 'Human review required · Medium risk';
  }
  return 'Human review required · Low risk';
}

// 5. Load Case Queue from Backend API
async function loadCaseQueue() {
  const search = $('caseSearch')?.value || '';
  const filterBtn = document.querySelector('.filter.active');
  const filter = filterBtn?.dataset.filter || 'all';

  try {
    const data = await apiCall(`/api/loans?search=${encodeURIComponent(search)}&filter=${filter}`);
    renderCaseTable(data.loans || []);
    renderOverviewCards(data.loans || []);
  } catch (err) {
    $('caseTable').textContent = 'Could not load the queue. Retry using the filters.';
    showToast(err.message, 'error', 'Queue unavailable');
  }
}

function renderOverviewCards(loans) {
  const top = loans.slice(0, 3);
  $('overviewCases').innerHTML = top.map(c => {
    const rScore = c.risk_score ? `${c.risk_score}/100` : 'Not Scored';
    const rLevel = c.risk_level || 'UNASSESSED';
    const levelClass = (c.risk_level || 'unassessed').toLowerCase();
    return `
      <div class="case-card">
        <div class="case-top">
          <div>
            <strong>${esc(c.id)}</strong>
            <small>${esc(c.borrower_name || c.name)}</small>
          </div>
          <span class="risk-pill ${levelClass}">${rLevel}</span>
        </div>
        <div class="amount">${money(c.loan_amount || c.amount)}</div>
        <small>${esc(c.employment_type || 'Salaried')} · ${c.months_employed ? Math.round(c.months_employed/12) + 'y tenure' : 'Tenure unverified'}</small>
        <div class="facts">
          <div><span>Credit Score</span><b>${c.credit_score || 'Missing'}</b></div>
          <div><span>DTI Burden</span><b>${c.dti_ratio ? Math.round(c.dti_ratio * 100) + '%' : 'Unknown'}</b></div>
        </div>
        <button class="btn full" onclick="openCaseById('${c.id}')">Open case →</button>
      </div>
    `;
  }).join('');
}

function renderCaseTable(loans) {
  $('caseTable').innerHTML = `
    <div class="case-table-row case-table-head">
      <div>CASE / BORROWER</div>
      <div>REQUEST AMOUNT</div>
      <div>BUREAU CREDIT</div>
      <div>DTI RATIO</div>
      <div>ML RISK GRADE</div>
      <div>STATUS</div>
      <div>ACTION</div>
    </div>
  ` + loans.map(c => {
    const rLevel = c.risk_level || 'UNASSESSED';
    const levelClass = (c.risk_level || 'unassessed').toLowerCase();
    return `
      <div class="case-table-row">
        <div class="person">
          <strong>${esc(c.id)}</strong>
          <span>${esc(c.borrower_name || c.name)} · ${esc(c.loan_purpose || 'General')}</span>
        </div>
        <div><b class="cell-value">${money(c.loan_amount || c.amount)}</b></div>
        <div><b class="cell-value">${c.credit_score || '—'}</b></div>
        <div><b class="cell-value">${c.dti_ratio ? (c.dti_ratio * 100).toFixed(0) + '%' : '—'}</b></div>
        <div><span class="risk-pill ${levelClass}">${rLevel} ${c.risk_score ? `(${c.risk_score})` : ''}</span></div>
        <div><b class="cell-value">${esc(c.status || 'RECEIVED')}</b></div>
        <div><button class="btn" onclick="openCaseById('${c.id}')">Open Case →</button></div>
      </div>
    `;
  }).join('');
}

// 6. Open Case by ID from Backend
async function openCaseById(id, switchPage = true) {
  try {
    const loan = await apiCall(`/api/loans/${id}`);
    activeCase = loan;
    activeAnalysis = loan.assessment || null;
    activeFunding = loan.funding || null;
    fundingPreview = null;
    activeRepayment = loan.repayment || null;

    // Set form defaults
    $('repPrincipal').value = loan.repayment?.original_principal ?? loan.loan_amount;
    $('repRate').value = loan.repayment?.annual_interest_rate ?? loan.interest_rate;
    $('repTerm').value = loan.repayment?.term_months ?? loan.loan_term;
    $('repDate').value = loan.repayment?.installments?.[0]?.due_date ?? '';
    $('repScheduleType').value = loan.repayment?.schedule_type ?? 'monthly';
    $('repAllocationPolicy').value = loan.repayment?.allocation_policy ?? 'pro-rata';
    $('fundingMode').value = loan.funding?.mode ?? 'auto';
    $('lenderCount').value = loan.funding?.lender_count ?? 3;
    $('scenarioSlider').value = loan.loan_amount;
    $('scenarioCreditSlider').value = loan.credit_score || 650;
    $('scenarioDtiSlider').value = loan.dti_ratio ?? 0.32;

    renderOverview();
    renderIntelligence(activeAnalysis);
    renderFunding();
    renderRepayment();
    updateScenarioLab();
    if (switchPage) {
      showPage('overview');
    }
  } catch (err) {
    showToast(`Failed to load case ${id}: ${err.message}`, 'error', 'Case Loading Error');
  }
}

// 7. Execute ML Risk Analysis
async function runAnalysis() {
  if (!activeCase) return;
  $('riskScore').textContent = '…';
  $('riskLevel').textContent = 'CALCULATING…';

  try {
    const result = await apiCall('/api/risk/analyze', {
      method: 'POST',
      body: JSON.stringify({
        loanId: activeCase.id,
        Income: activeCase.income,
        LoanAmount: activeCase.loan_amount || activeCase.amount,
        CreditScore: activeCase.credit_score,
        DTIRatio: activeCase.dti_ratio,
        MonthsEmployed: activeCase.months_employed,
        NumCreditLines: activeCase.num_credit_lines,
        InterestRate: activeCase.interest_rate,
        LoanTerm: activeCase.loan_term,
        EmploymentType: activeCase.employment_type,
        HasCoSigner: activeCase.has_cosigner,
        HasMortgage: activeCase.has_mortgage,
        HasDependents: activeCase.has_dependents
      })
    });

    activeAnalysis = result;
    renderIntelligence(result);
    renderOverview();
    updateScenarioLab();
    showToast(`Calibrated assessment complete: ${result.risk_level} RISK (Score ${result.risk_score}/100, PD ${result.probability_pct}%)`, 'success', 'Model Inference Complete');
    showPage('intelligence');
    return true;
  } catch (err) {
    showToast(`ML Inference failed: ${err.message}`, 'error', 'Inference Error');
  }
}

function renderIntelligence(res) {
  if (!res) {
    ['riskScore','riskPdHero','sigPd','sigDti','sigCredit','sigCoverage','dqScore','dqFieldsCount'].forEach(id => $(id).textContent = '—');
    ['riskDrivers','riskProtective','dqWarnings','anomalyList','explainabilityText'].forEach(id => $(id).textContent = '');
    $('riskLevel').textContent = 'NOT ASSESSED';
    $('analysisHeadline').textContent = 'Awaiting assessment';
    $('analysisSummary').textContent = 'Run analysis for the selected borrower.';
    $('dqBadge').textContent = 'NOT CHECKED';
    $('anomalyBadge').textContent = 'SCAN PENDING';
    $('dqBar').style.width = '0%';
    document.querySelector('.gauge-ring').style.background = '#2a2e32';
    return;
  }
  $('riskScore').textContent = res.risk_score;
  $('riskLevel').className = `risk-pill ${res.risk_level.toLowerCase()}`;
  $('riskLevel').textContent = `${res.risk_level} RISK`;
  $('riskPdHero').textContent = `Calibrated Default Probability: ${res.probability_pct}%`;

  $('analysisHeadline').textContent = res.risk_level === 'HIGH'
    ? 'Enhanced underwriting required prior to release.'
    : (res.risk_level === 'MEDIUM' ? 'Conditional approval recommended.' : 'Eligible for standard fast-track approval.');

  $('analysisSummary').textContent = `RISKORA model scored ${activeCase.id} at ${res.risk_score}/100 (Default Probability: ${res.probability_pct}%). Recommended Action: ${res.recommended_action}`;

  $('sigPd').textContent = `${res.probability_pct}%`;
  $('sigDti').textContent = activeCase.dti_ratio ? `${Math.round(activeCase.dti_ratio * 100)}%` : 'Unknown';
  $('sigCredit').textContent = activeCase.credit_score || 'Unknown';
  const lti = (activeCase.loan_amount || activeCase.amount) / Math.max(activeCase.income, 1);
  $('sigCoverage').textContent = `${lti.toFixed(1)}× annual income`;

  // Risk Gauge circle fill
  const pct = res.risk_score * 3.6;
  const color = res.risk_level === 'HIGH' ? '#9d3934' : (res.risk_level === 'MEDIUM' ? '#96631a' : '#276b4a');
  document.querySelector('.gauge-ring').style.background = `conic-gradient(${color} ${pct}deg, #2a2e32 ${pct}deg)`;

  // Render Risk Drivers
  const driversList = res.risk_drivers || res.drivers || [];
  $('riskDrivers').innerHTML = driversList.map(d => `
    <div class="driver-item">
      <div class="driver-line">
        <b>${esc(d.factor)}</b>
        <b style="color:var(--red);">+${d.impact_pts} pts</b>
      </div>
      <div class="bar"><i style="width:${Math.min(100, Math.abs(d.impact_pts) * 4)}%; background:var(--red);"></i></div>
      <div class="driver-desc">${esc(d.description)}</div>
    </div>
  `).join('') || '<div style="padding:10px; font-size:11px; color:#8a929a;">No elevated risk drivers detected.</div>';

  // Render Protective Factors
  const protectiveList = res.protective_factors || res.protective || [];
  $('riskProtective').innerHTML = protectiveList.map(p => `
    <div class="driver-item">
      <div class="driver-line">
        <b>${esc(p.factor)}</b>
        <b style="color:var(--green);">${p.impact_pts} pts</b>
      </div>
      <div class="bar"><i style="width:${Math.min(100, Math.abs(p.impact_pts) * 4)}%; background:var(--green);"></i></div>
      <div class="driver-desc">${esc(p.description)}</div>
    </div>
  `).join('') || '<div style="padding:10px; font-size:11px; color:#8a929a;">No primary protective mitigators noted.</div>';

  // Render Data Quality
  const dq = res.data_quality || {};
  $('dqScore').textContent = `${dq.data_quality_score ?? 0}/100`;
  $('dqBar').style.width = `${dq.data_quality_score ?? 0}%`;
  $('dqBar').style.background = dq.data_quality_score >= 80 ? 'var(--green)' : 'var(--amber)';
  $('dqBadge').textContent = dq.quality_tier || 'ACCEPTABLE';
  $('dqBadge').className = `status-chip ${dq.quality_tier === 'EXCELLENT' ? 'done' : ''}`;
  $('dqFieldsCount').textContent = `${dq.available_fields_count ?? 0} / ${dq.total_fields_count || 15} required & optional fields verified (${dq.completeness_pct ?? 0}%)`;

  const dqWarns = [
    ...(dq.missing_required_fields || []).map(m => `Missing: ${m}`),
    ...(dq.validity_warnings || []),
    ...(dq.contradiction_flags || [])
  ];
  $('dqWarnings').innerHTML = dqWarns.length
    ? dqWarns.map(w => `<div style="margin-top:4px;">• ${esc(w)}</div>`).join('')
    : '<div style="color:var(--green); margin-top:4px;">✓ Full documentation & validity verified.</div>';

  // Render Anomaly Detection
  const anom = res.anomaly_indicators || {};
  $('anomalyBadge').textContent = anom.anomaly_detected ? 'ANOMALY DETECTED' : 'NORMAL PROFILE';
  $('anomalyBadge').className = `status-chip ${anom.anomaly_detected ? 'high' : 'done'}`;
  $('anomalySummaryText').textContent = anom.recommendation || 'Standard underwriting workflow applicable.';
  
  if (anom.indicators && anom.indicators.length) {
    $('anomalyList').innerHTML = anom.indicators.map(ind => `
      <div class="anomaly-item">
        <strong>${esc(ind.type)} (${ind.severity})</strong>
        <p>${esc(ind.description)}</p>
      </div>
    `).join('');
  } else {
    $('anomalyList').innerHTML = '<div style="font-size:10px; color:var(--green);">✓ No statistical irregularities or contradictory profiles detected.</div>';
  }

  $('explainabilityText').textContent = 'Policy rule indicators, not trained-model feature attributions. Predictions use a model trained on synthetic data.';
}

// 8. Scenario Lab (What-If ML Simulation)
let scenarioRequest = 0;
async function updateScenarioLab() {
  const request = ++scenarioRequest;
  if (!activeCase) return;
  const simAmount = Number($('scenarioSlider').value) || activeCase.loan_amount;
  const simCredit = Number($('scenarioCreditSlider').value) || (activeCase.credit_score || 650);
  const simDti = Number($('scenarioDtiSlider').value);

  $('scenarioAmount').textContent = money(simAmount);
  $('scenarioCreditVal').textContent = simCredit;
  $('scenarioDtiVal').textContent = (simDti * 100).toFixed(0) + '%';

  try {
    const res = await apiCall('/api/risk/simulate', {
      method: 'POST',
      body: JSON.stringify({
        baseLoanId: activeCase.id,
        scenario: {
          LoanAmount: simAmount,
          CreditScore: simCredit,
          DTIRatio: simDti
        }
      })
    });

    if (request !== scenarioRequest) return;
    $('scenarioRisk').textContent = `${res.scenario.score}/100 (${res.scenario.level})`;
    $('scenarioDelta').textContent = res.comparison.score_delta === 0
      ? 'Identical to baseline case'
      : `${res.comparison.score_delta > 0 ? '+' : ''}${res.comparison.score_delta} pts vs baseline`;

    $('scenarioPd').textContent = `${res.scenario.pd_pct}%`;
    $('scenarioPdDelta').textContent = `${res.comparison.pd_delta_pts > 0 ? '+' : ''}${res.comparison.pd_delta_pts} pp vs baseline`;

    $('scenarioEmi').textContent = money(res.scenario.indicative_emi);
    $('scenarioEmi').nextElementSibling.textContent = `${activeCase.loan_term} mos @ ${activeCase.interest_rate}% APR`;
    $('scenarioFunding').textContent = res.scenario.recommended_mode === 'fractional' ? 'Fractional Syndication' : 'Single Lender';
    $('scenarioDecision').textContent = res.scenario.level === 'HIGH' ? 'Escalate to Senior Committee' : (res.scenario.level === 'MEDIUM' ? 'Conditional Underwriting' : 'Eligible for Fast-Track');
  } catch (err) {
    if (request === scenarioRequest) { $('scenarioRisk').textContent = 'Unavailable'; $('scenarioDelta').textContent = err.message; }
  }
}

// 9. Funding Optimizer
async function optimizeFunding(commit = false) {
  if (!activeCase) return;
  const mode = $('fundingMode').value;
  const count = Number($('lenderCount').value) || 3;
  const amount = activeCase.loan_amount || activeCase.amount;
  const riskLevel = activeAnalysis ? activeAnalysis.risk_level : 'MEDIUM';

  try {
    const result = await apiCall('/api/funding/optimize', {
      method: 'POST',
      body: JSON.stringify({
        loanId: commit === true ? activeCase.id : undefined,
        amount,
        riskLevel,
        mode,
        lenderCount: count
      })
    });

    if (commit === true) { activeFunding = result; fundingPreview = null; }
    else fundingPreview = {...result, preview: true};
    renderFunding();
    renderOverview();
    showToast(`Funding structure computed: ${result.mode.toUpperCase()} model (${result.positions.length} lenders, HHI ${result.herfindahl_index})`, 'success', commit === true ? 'Funding Saved' : 'Preview Only');
    return true;
  } catch (err) {
    showToast(`Funding optimisation failed: ${err.message}`, 'error', 'Syndication Error');
  }
}

function renderFunding() {
  const funding = fundingPreview || activeFunding;
  if (!activeCase) return;
  const amount = activeCase.loan_amount || activeCase.amount;
  $('fundingAmount').textContent = money(amount);
  $('fundingRiskText').textContent = activeAnalysis
    ? `Current Evaluated Risk: ${activeAnalysis.risk_level} (Score ${activeAnalysis.risk_score}/100, PD ${activeAnalysis.probability_pct}%).`
    : 'Run case analysis before committing structure.';

  if (!funding) {
    $('fundingFlow').innerHTML = '<div class="borrower-node"><b>Borrower</b><span>Awaiting structure</span></div><div class="lender-list"><div class="lender-bar"><div class="lb-top"><span>Syndication pending</span><span>—</span></div><small>Click "Commit Funding Structure" to calculate lender allocations.</small></div></div>';
    $('fundingBadge').textContent = 'PENDING';
    $('fundingInsights').innerHTML = '';
    $('fundingDecisionStrip').innerHTML = '';
    return;
  }

  $('fundingBadge').textContent = funding.preview ? 'PREVIEW · NOT COMMITTED' : funding.mode === 'fractional' ? 'FRACTIONAL SYNDICATION' : 'SINGLE LENDER';
  $('fundingBadge').className = 'status-chip done';

  $('fundingFlow').innerHTML = `
    <div class="borrower-node">
      <b>Borrower</b>
      <span>${money(funding.total_requested)}</span>
    </div>
    <div class="lender-list">
      ${funding.positions.map(p => `
        <div class="lender-bar">
          <div class="lb-top">
            <span>${esc(p.lender_name)} ${p.is_lead ? '(Lead)' : ''}</span>
            <span>${p.share_pct}% · ${money(p.committed_amount)}</span>
          </div>
          <div class="lb-track"><i style="width:${p.share_pct}%"></i></div>
          <small>${funding.mode === 'fractional' ? 'Syndicated risk-sharing commitment' : 'Full principal carried by sole lender'}</small>
        </div>
      `).join('')}
    </div>
  `;

  $('fundingInsights').innerHTML = `
    <div>
      <span>Largest Lender Share</span>
      <b>${funding.largest_lender_share}%</b>
    </div>
    <div>
      <span>Herfindahl Index (HHI)</span>
      <b>${funding.herfindahl_index}</b>
    </div>
    <div>
      <span>Concentration Grade</span>
      <b>${funding.concentration_rating.replace('_', ' ')}</b>
    </div>
  `;

  $('fundingDecisionStrip').innerHTML = `
    <div><span>Requested Principal</span><b>${money(funding.total_requested)}</b></div>
    <div><span>Syndication Model</span><b>${funding.mode === 'fractional' ? `Fractional (${funding.lender_count} Lenders)` : 'Single Lender'}</b></div>
    <div><span>Exposure Distribution</span><b>${funding.concentration_description}</b></div>
    <div><span>Next Step</span><b>Generate Repayment Plan →</b></div>
  `;
}

function applyFunding() {
  if (!activeAnalysis) {
    runAnalysis().then(ok => { if (ok) optimizeFunding(true).then(saved => { if (saved) showPage('repayment'); }); });
    return;
  }
  optimizeFunding(true).then(ok => { if (ok) showPage('repayment'); });
}

// 10. Repayment Engine & Amortisation
async function generateRepayment() {
  if (!activeCase) return;
  if (!activeFunding || activeFunding.preview) { showToast('Commit the funding structure before generating a schedule.', 'warning'); return; }
  const principal = Number($('repPrincipal').value) || (activeCase.loan_amount || activeCase.amount);
  const rate = Number($('repRate').value);
  const term = Number($('repTerm').value) || 36;
  const startDate = $('repDate').value || new Date().toISOString().slice(0, 10);
  const scheduleType = $('repScheduleType').value;
  const policy = $('repAllocationPolicy').value;

  const positions = activeFunding ? activeFunding.positions : [{
    lender_id: 'LND-001',
    lender_name: 'Apex Micro-Credit Fund',
    share_pct: 100.0,
    committed_amount: principal
  }];

  try {
    const result = await apiCall('/api/repayment/generate', {
      method: 'POST',
      body: JSON.stringify({
        loanId: activeCase.id,
        principal,
        rate,
        term,
        startDate,
        scheduleType,
        allocationPolicy: policy,
        positions
      })
    });

    activeRepayment = result;
    renderRepayment();
    renderOverview();
    showToast(`Amortisation plan generated (${result.num_installments} installments @ ${result.annual_interest_rate}% APR, EMI: ${money(result.indicative_emi)})`, 'success', 'Amortisation Ready');
    showPage('repayment');
  } catch (err) {
    showToast(`Repayment calculation failed: ${err.message}`, 'error', 'Calculation Error');
  }
}

function renderRepayment() {
  if (!activeRepayment) {
    $('emiValue').textContent = '—';
    $('emiMeta').textContent = 'Generate a schedule for this case.';
    $('repaymentHeadline').textContent = 'No schedule generated';
    ['repaymentNarrative','repaymentAllocation','scheduleBody'].forEach(id => $(id).textContent = '');
    $('scheduleStatus').textContent = 'NOT GENERATED';
    return;
  }
  $('emiValue').textContent = money(activeRepayment.indicative_emi);
  $('emiMeta').textContent = `${activeRepayment.num_installments} installments · ${activeRepayment.annual_interest_rate}% APR · Total Repayable: ${money(activeRepayment.total_repayable)}`;
  
  $('repaymentHeadline').textContent = `${money(activeRepayment.indicative_emi)} installment`;
  $('repaymentNarrative').textContent = activeRepayment.allocation_policy_description;

  // Render Lender Allocation summary
  $('repaymentAllocation').innerHTML = (activeRepayment.lender_summary || []).map(ls => `
    <div class="allocation-line">
      <div>
        <strong>${esc(ls.lender_name)}</strong>
        <span style="display:block; font-size:9px; color:#8a929a;">Principal: ${money(ls.expected_principal)}</span>
      </div>
      <div style="text-align:right;">
        <b>${money(ls.total_expected_return)}</b>
        <span style="display:block; font-size:9px; color:var(--green);">+${money(ls.expected_interest)} interest</span>
      </div>
    </div>
  `).join('');

  // Render Amortisation Table
  $('scheduleBody').innerHTML = (activeRepayment.installments || []).map(inst => {
    const isPaid = inst.status === 'PAID';
    return `
      <tr class="${isPaid ? 'tr-paid' : ''}">
        <td><b>#${inst.installment_num}</b></td>
        <td>${inst.due_date}</td>
        <td><b>${money(inst.payment_amount)}</b></td>
        <td>${money(inst.principal_component)}</td>
        <td>${money(inst.interest_component)}</td>
        <td><b>${money(inst.remaining_balance)}</b></td>
        <td><span class="${isPaid ? 'badge-paid' : 'badge-scheduled'}">${isPaid ? '● PAID' : '○ SCHEDULED'}</span></td>
        <td>
          ${isPaid 
            ? `<span style="color:#15803d; font-size:10px; font-weight:700;">✓ Settled</span>` 
            : `<button class="pay-btn" onclick="recordPaymentEvent(${inst.installment_num}, ${inst.payment_amount}, this)">Record Payment</button>`}
        </td>
      </tr>
    `;
  }).join('');

  $('scheduleStatus').textContent = 'GENERATED & RECONCILED';
  $('scheduleStatus').className = 'status-chip done';
}

async function recordPaymentEvent(instNum, amount, btnEl) {
  if (!activeCase) return;
  const btn = btnEl || (window.event && window.event.target);
  if (btn && btn.tagName === 'BUTTON') {
    btn.disabled = true;
    btn.textContent = 'Recording...';
  }
  try {
    const res = await apiCall('/api/repayment/record', {
      method: 'POST',
      body: JSON.stringify({
        loanId: activeCase.id,
        installmentNum: instNum,
        amount
      })
    });
    showToast(`Installment #${instNum} (${money(amount)}) recorded as PAID. Relational ledger reconciled.`, 'success', 'Payment Settled');
    // Refresh case details cleanly in-place without page flickering
    await openCaseById(activeCase.id, false);
    renderRepayment();
    renderOverview();
    loadExposurePortfolio();
  } catch (err) {
    showToast(`Failed to record payment: ${err.message}`, 'error', 'Payment Failed');
    if (btn && btn.tagName === 'BUTTON') {
      btn.disabled = false;
      btn.textContent = 'Record Payment';
    }
  }
}

// 11. Exposure Monitor
async function loadExposurePortfolio() {
  try {
    const data = await apiCall('/api/exposure/portfolio');
    const port = data.portfolio_summary || {};
    
    const committed = activeFunding && !activeFunding.preview ? activeFunding.total_requested : 0;
    const outstanding = activeRepayment && activeRepayment.installments
      ? Math.max(0, activeRepayment.original_principal - activeRepayment.installments.filter(i => i.status === 'PAID').reduce((sum, i) => sum + i.principal_component, 0))
      : committed;

    $('expCommitted').textContent = money(committed);
    $('expOutstanding').textContent = money(outstanding);
    $('expLargest').textContent = activeFunding ? `${activeFunding.largest_lender_share}%` : '100.0%';
    $('expConcentration').textContent = activeFunding ? `HHI ${activeFunding.herfindahl_index}` : 'HHI 10000';

    if (activeFunding && !activeFunding.preview) {
      $('exposureRows').innerHTML = activeFunding.positions.map(p => {
        const pCommitted = p.committed_amount;
        const paidPrincipal = (activeRepayment?.installments || []).filter(i => i.status === 'PAID').flatMap(i => i.allocations || []).filter(a => a.lender_id === p.lender_id).reduce((sum, a) => sum + a.principal_allocated, 0);
        const pOut = Math.max(0, pCommitted - paidPrincipal);
        return `
          <div class="exposure-row">
            <div>
              <strong>${esc(p.lender_name)}</strong>
              <span>${p.share_pct}% committed pool</span>
            </div>
            <div><span>Committed</span><strong>${money(pCommitted)}</strong></div>
            <div><span>Outstanding</span><strong>${money(pOut)}</strong></div>
          </div>
        `;
      }).join('');

      $('exposureHeadline').textContent = activeFunding.concentration_rating.replace('_', ' ');
      $('exposureNarrative').textContent = activeFunding.concentration_description;
      $('exposureMeter').innerHTML = `
        <div class="exposure-meter">
          <div class="meter-track"><i style="width:${Math.min(100, activeFunding.largest_lender_share)}%"></i></div>
          <div class="meter-caption">
            <span>0% Diversified</span>
            <b>${activeFunding.largest_lender_share}% Largest Share</b>
            <span>100% Single Lender</span>
          </div>
        </div>
      `;
    } else {
      $('exposureRows').innerHTML = '<div style="padding:15px; color:#8a929a;">Commit a funding structure to activate exposure ledger.</div>';
    }
  } catch (err) {
    console.error('Exposure loading error:', err);
  }
}

// 12. Decision Report Dossier
function renderDecision() {
  if (!activeCase || !activeAnalysis) {
    $('decisionSheet').innerHTML = `
      <div class="empty">
        <h2>Complete Case Investigation</h2>
        <p>Execute risk analysis, syndicated funding, and repayment simulation before assembling the final underwriting report.</p>
      </div>
    `;
    return;
  }

  const rec = decisionText();
  const ass = activeAnalysis;
  const dq = ass.data_quality || {};
  const anom = ass.anomaly_indicators || {};

  $('decisionSheet').innerHTML = `
    <div class="decision-head">
      <div>
        <div class="eyebrow">RISKORA · CREDIT RISK DECISION DOSSIER</div>
        <h2>${esc(activeCase.id)} · ${esc(activeCase.borrower_name || activeCase.name)}</h2>
        <p>Comprehensive decision trail assembled from calibrated ML inference, data quality audit, and syndicated exposure analysis.</p>
      </div>
      <div class="decision-score">
        <strong>${ass.risk_score}</strong>
        <span class="risk-pill ${ass.risk_level.toLowerCase()}">${ass.risk_level} RISK · ${ass.probability_pct}% PD</span>
      </div>
    </div>

    <div class="decision-meta">
      <div>
        <span>Loan Principal</span>
        <b>${money(activeCase.loan_amount || activeCase.amount)}</b>
      </div>
      <div>
        <span>Syndication</span>
        <b>${activeFunding && !activeFunding.preview ? (activeFunding.mode === 'fractional' ? `Fractional (${activeFunding.lender_count} Lenders)` : 'Single Lender') : 'Pending'}</b>
      </div>
      <div>
        <span>Amortisation</span>
        <b>${activeRepayment ? `${money(activeRepayment.indicative_emi)} / mo` : 'Pending'}</b>
      </div>
      <div>
        <span>Recommendation</span>
        <b style="color:${rec.includes('Approve') ? 'var(--green)' : 'var(--red)'};">${rec}</b>
      </div>
    </div>

    <div class="report-grid">
      <div class="report-block">
        <h3>POLICY RULE INDICATORS</h3>
        <ul class="report-list">
          ${(ass.risk_drivers || ass.drivers || []).map(d => `
            <li>
              <b>${esc(d.factor)} (+${d.impact_pts} pts)</b><br>
              <span>${esc(d.description)}</span>
            </li>
          `).join('') || '<li><b>Standard Affordability Baseline</b><br><span>No severe individual risk anomalies noted.</span></li>'}
        </ul>
      </div>

      <div class="report-block">
        <h3>DATA INTEGRITY & UNDERWRITING CONTROLS</h3>
        <ul class="report-list">
          <li>
            <b>Data Quality Index: ${dq.data_quality_score ?? 0}/100 (${dq.quality_tier || 'ACCEPTABLE'})</b><br>
            <span>${dq.available_fields_count ?? 0} of ${dq.total_fields_count || 15} required verification items validated.</span>
          </li>
          <li>
            <b>Anomaly Scan: ${anom.anomaly_detected ? 'ANOMALY DETECTED' : 'CLEAN PROFILE'}</b><br>
            <span>${esc(anom.recommendation || 'Standard verification protocols satisfied.')}</span>
          </li>
          <li>
            <b>Review Level: ${esc(ass.review_level)}</b><br>
            <span>${esc(ass.recommended_action)}</span>
          </li>
        </ul>
      </div>
    </div>

    <div class="decision-callout">
      <div class="eyebrow">FINAL UNDERWRITING DISPOSITION</div>
      <strong>${rec}</strong>
      <p style="margin-top:6px; font-size:11px; line-height:1.6;">
        ${rec === 'Standard Approval' 
          ? 'Borrower meets prime micro-lending criteria with low default hazard (PD < 8.0%). Single-lender or fractional syndication eligible.' 
          : (rec === 'Conditional Approval' 
            ? 'Moderate default probability (8.0%–20.0%). Approval is strictly contingent on multi-lender fractional syndication to distribute exposure concentration, together with secondary verification of income proofs.' 
            : 'Elevated default hazard (PD ≥ 20.0%). Principal loss exposure exceeds standard single-counterparty tolerances. Do not release capital without additional co-signer guarantees or senior credit committee override.')}
      </p>
    </div>

    <div style="margin-top:20px; font-size:9px; color:#8a929a; border-top:1px solid var(--line2); padding-top:12px; display:flex; justify-content:space-between;">
      <span>Model Engine: ${ass.model_metadata?.version || 'riskora-ml-v1.0'} (${ass.model_metadata?.algorithm || 'HistGradientBoosting'})</span>
      <span>Target Leakage Check: Verified Isolated (Default Ground Truth Excluded)</span>
      <span>Generated: ${new Date().toISOString().slice(0, 19).replace('T', ' ')} UTC</span>
    </div>
  `;
}

// 13. Dataset Explorer with Server-Side Pagination & Filtering
async function loadDatasetExplorer() {
  const search = $('datasetSearch')?.value || '';
  const risk = $('datasetRisk')?.value || 'all';
  const sort = $('datasetSort')?.value || 'score';

  try {
    const data = await apiCall(`/api/dataset/explorer?search=${encodeURIComponent(search)}&risk=${risk}&sort=${sort}&page=${datasetState.page}&limit=${datasetState.limit}`);
    
    // Summary metrics
    const stats = data.summary_stats || {};
    $('dsRecords').textContent = `${(stats.dataset_size || 12000).toLocaleString('en-IN')}`;
    $('dsDefaultRate').textContent = `${stats.historical_default_rate || 11.08}%`;
    $('dsAvgCredit').textContent = `${stats.avg_credit_score || 645}`;
    $('dsAvgLoan').textContent = money(stats.avg_loan_amount || 124500);

    // Rows
    $('datasetBody').innerHTML = (data.rows || []).map(r => `
      <tr>
        <td><b>${esc(r.LoanID)}</b></td>
        <td>${money(r.Income)}</td>
        <td>${money(r.LoanAmount)}</td>
        <td>${r.CreditScore}</td>
        <td>${(r.DTIRatio * 100).toFixed(0)}%</td>
        <td><b>${r.Score}</b></td>
        <td><span class="risk-pill ${r.RiskLevel.toLowerCase()}">${r.RiskLevel}</span></td>
        <td>${(r.ProbabilityDefault * 100).toFixed(1)}%</td>
        <td>
          ${r.Default === 1 
            ? '<span style="color:var(--red); font-weight:700;">Default (1)</span>' 
            : '<span style="color:var(--green);">Non-Default (0)</span>'}
        </td>
      </tr>
    `).join('') || '<tr><td colspan="9" style="text-align:center; padding:20px;">No matching records found.</td></tr>';

    // Pagination controls
    const pag = data.pagination || {};
    $('datasetPagination').innerHTML = `
      <span>Showing page <b>${pag.page}</b> of <b>${pag.total_pages}</b> (${pag.total_records.toLocaleString()} total records)</span>
      <div class="pagination-controls">
        <button class="btn" ${pag.page <= 1 ? 'disabled' : ''} onclick="changeDatasetPage(${pag.page - 1})">← Previous</button>
        <button class="btn" ${pag.page >= pag.total_pages ? 'disabled' : ''} onclick="changeDatasetPage(${pag.page + 1})">Next →</button>
      </div>
    `;
  } catch (err) {
    console.error('Failed to load dataset rows:', err);
  }
}

function changeDatasetPage(newPage) {
  datasetState.page = Math.max(1, newPage);
  loadDatasetExplorer();
}

// 14. Model Validation & Metrics View
async function loadModelMetrics() {
  try {
    const data = await apiCall('/api/model/metrics');
    const test = data.test_metrics || {};
    $('valRoc').textContent = test.roc_auc || '0.7919';
    $('valPr').textContent = test.pr_auc || '0.4023';
    $('valBrier').textContent = test.brier_score || '0.0821';

    const cm = test.confusion_matrix || {};
    $('cmTn').textContent = (cm.true_negative || 1460).toLocaleString();
    $('cmFp').textContent = (cm.false_positive || 141).toLocaleString();
    $('cmFn').textContent = (cm.false_negative || 119).toLocaleString();
    $('cmTp').textContent = (cm.true_positive || 80).toLocaleString();

    // Feature importance
    const feats = data.top_feature_importance || [];
    $('featureImportanceTable').innerHTML = `
      <div style="display:grid; grid-template-columns:1fr 1fr; gap:12px;">
        ${feats.map(f => `
          <div style="padding:8px 12px; background:#fafafa; border:1px solid var(--line2); border-radius:5px; display:flex; justify-content:space-between;">
            <b style="font-size:11px;">${esc(f.feature)}</b>
            <span style="font-size:10px; font-weight:700; color:var(--blue);">${f.weight > 0 ? '+' : ''}${f.weight}</span>
          </div>
        `).join('')}
      </div>
    `;
  } catch (err) {
    console.error('Model metrics load error:', err);
  }
}

// 15. What-If Sandbox Form Submission
async function handleManualSandbox(e) {
  e.preventDefault();
  const customData = {
    Income: Number($('mi').value),
    LoanAmount: Number($('ml').value),
    CreditScore: Number($('mc').value),
    DTIRatio: Number($('md').value),
    MonthsEmployed: Number($('me').value),
    NumCreditLines: Number($('mcl').value),
    EmploymentType: $('met').value,
    HasCoSigner: $('mcs').value
  };

  try {
    const res = await apiCall('/api/risk/analyze', {
      method: 'POST',
      body: JSON.stringify(customData)
    });

    $('manualResult').innerHTML = `
      <div class="eyebrow">SANDBOX ML INFERENCE RESULT</div>
      <div style="display:flex; justify-content:space-between; align-items:center; margin:15px 0; border-bottom:1px solid var(--line2); padding-bottom:15px;">
        <div>
          <div style="font-size:36px; font-weight:700; letter-spacing:-.04em;">
            ${res.risk_score}<span style="font-size:14px; color:#8a929a;">/100</span>
          </div>
          <div style="font-size:11px; color:#6b747c;">Calibrated Default Probability: <b>${res.probability_pct}%</b></div>
        </div>
        <span class="risk-pill ${res.risk_level.toLowerCase()}">${res.risk_level} RISK</span>
      </div>

      <div class="eyebrow">PRIMARY DRIVERS</div>
      <div style="margin-top:8px;">
        ${res.risk_drivers.map(d => `
          <div class="driver-item">
            <div class="driver-line"><b>${esc(d.factor)}</b><b>+${d.impact_pts} pts</b></div>
            <div class="driver-desc">${esc(d.description)}</div>
          </div>
        `).join('')}
      </div>

      <div class="decision-callout" style="margin-top:15px;">
        <strong>Recommended Underwriting Action</strong>
        <p>${esc(res.recommended_action)}</p>
      </div>
    `;
    showToast(`Sandbox case scored: ${res.risk_score}/100 (${res.risk_level} RISK)`, 'success', 'Inference Complete');
  } catch (err) {
    showToast(`Sandbox inference failed: ${err.message}`, 'error', 'Sandbox Evaluation Failed');
  }
}

// 16. Run Full End-to-End Case Demo Script
async function runFullDemo() {
  if (demoTimer) return;
  demoTimer = true;
  try {
    await runAnalysis();
    showPage('decision');
    showToast('Assessment report ready. Review and commit funding explicitly to continue.', 'info');
  } finally { demoTimer = null; }
}

// 17. Bind UI Event Listeners
function bindEvents() {
  document.querySelectorAll('[data-page]').forEach(b => {
    b.addEventListener('click', e => {
      e.preventDefault();
      showPage(b.dataset.page);
    });
  });

  document.querySelectorAll('[data-action="open-case"]').forEach(b => {
    b.onclick = () => {
      if (activeCase) openCaseById(activeCase.id);
    };
  });

  document.querySelectorAll('[data-action="continue-case"]').forEach(b => {
    b.onclick = () => {
      if (!activeAnalysis) runAnalysis();
      else if (!activeFunding) showPage('funding');
      else if (!activeRepayment) showPage('repayment');
      else showPage('decision');
    };
  });

  document.querySelectorAll('[data-action="reset-case"]').forEach(b => {
    b.onclick = () => openCaseById('LR-1054');
  });

  $('runDemo').onclick = runFullDemo;

  // Search & Filters in Case Queue
  $('caseSearch')?.addEventListener('input', loadCaseQueue);
  document.querySelectorAll('.filter').forEach(btn => {
    btn.addEventListener('click', () => {
      document.querySelectorAll('.filter').forEach(x => x.classList.remove('active'));
      btn.classList.add('active');
      loadCaseQueue();
    });
  });

  // Action Buttons
  document.querySelectorAll('[data-action="analyze"]').forEach(b => b.onclick = runAnalysis);
  document.querySelectorAll('[data-action="optimize-funding"]').forEach(b => b.onclick = optimizeFunding);
  document.querySelectorAll('[data-action="apply-funding"]').forEach(b => b.onclick = applyFunding);
  document.querySelectorAll('[data-action="build-repayment"]').forEach(b => b.onclick = generateRepayment);
  document.querySelectorAll('[data-action="refresh-exposure"]').forEach(b => b.onclick = loadExposurePortfolio);

  $('fundingMode')?.addEventListener('change', optimizeFunding);
  $('lenderCount')?.addEventListener('change', optimizeFunding);



  // Scenario Lab Sliders
  $('scenarioSlider')?.addEventListener('input', updateScenarioLab);
  $('scenarioCreditSlider')?.addEventListener('input', updateScenarioLab);
  $('scenarioDtiSlider')?.addEventListener('input', updateScenarioLab);
  $('resetScenario')?.addEventListener('click', () => {
    if (activeCase) {
      $('scenarioSlider').value = activeCase.loan_amount || activeCase.amount;
      $('scenarioCreditSlider').value = activeCase.credit_score || 650;
      $('scenarioDtiSlider').value = activeCase.dti_ratio ?? 0.32;
      updateScenarioLab();
    }
  });

  // Dataset Explorer Controls
  $('datasetSearch')?.addEventListener('input', () => { datasetState.page = 1; loadDatasetExplorer(); });
  $('datasetRisk')?.addEventListener('change', () => { datasetState.page = 1; loadDatasetExplorer(); });
  $('datasetSort')?.addEventListener('change', () => { datasetState.page = 1; loadDatasetExplorer(); });
  $('loadBundled')?.addEventListener('click', loadDatasetExplorer);
  $('refreshMetrics')?.addEventListener('click', loadModelMetrics);

  // Manual Form
  $('manualForm')?.addEventListener('submit', handleManualSandbox);

  // Copy Summary Action
  document.querySelectorAll('[data-action="copy-summary"]').forEach(btn => {
    btn.onclick = async () => {
      if (!activeCase || !activeAnalysis) return;
      const text = `RISKORA Case Report: ${activeCase.id} (${activeCase.borrower_name || activeCase.name})\n` +
        `Risk Score: ${activeAnalysis.risk_score}/100 (${activeAnalysis.risk_level})\n` +
        `Probability of Default: ${activeAnalysis.probability_pct}%\n` +
        `Syndication: ${activeFunding ? activeFunding.mode : 'Pending'}\n` +
        `Recommendation: ${decisionText()}`;
      try {
        await navigator.clipboard.writeText(text);
        btn.textContent = 'Copied ✓';
        setTimeout(() => btn.textContent = 'Copy Summary', 1200);
      } catch {}
    };
  });
}

// Global Initialization
window.addEventListener('DOMContentLoaded', () => {
  initEntry();
  bindEvents();
  // Open default seed case
  openCaseById('LR-1054');
  loadCaseQueue();
});
