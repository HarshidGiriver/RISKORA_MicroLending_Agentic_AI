// OraAgent-inspired borrower intake and evidence review on the shared RISKORA API.
let reviewer = null;
let editingLoan = null;
let paymentContext = null;

function lockWorkspace() {
  reviewer = null;
  $('accessGate').style.display = '';
  $('appShell').style.visibility = 'hidden';
  $('appShell').style.display = 'none';
  $('appShell').inert = true;
  $('appShell').setAttribute('aria-hidden', 'true');
  document.querySelectorAll('dialog[open]').forEach(d => d.close());
}

async function enterWorkspace(user) {
  reviewer = user;
  $('reviewerLabel').textContent = `${user.role} · ${user.username}`;
  $('manageAccounts').hidden = user.role !== 'ADMIN';
  $('accessGate').style.display = 'none';
  $('appShell').style.display = '';
  $('appShell').inert = false;
  $('appShell').style.visibility = 'visible';
  $('appShell').setAttribute('aria-hidden', 'false');
  $('reviewerPassword').value = '';
  await loadCaseQueue();
  await openCaseById(sessionStorage.getItem('riskora_case') || 'LR-1054', false);
  showPage('overview');
}

async function initializeAccess() {
  lockWorkspace();
  let setupRequired = false;
  const checkSetup = async () => {
    const info = await apiCall('/api/auth/setup');
    setupRequired = info.setup_required;
    $('accessSubmit').textContent = setupRequired ? 'CREATE ADMIN ACCOUNT →' : 'SIGN IN →';
    $('accessMessage').textContent = setupRequired
      ? 'First use: choose your administrator username and a password of at least 12 characters. No default credentials are installed.'
      : 'Sign in with your reviewer account. Sessions expire after 8 hours.';
    $('reviewerPassword').autocomplete = setupRequired ? 'new-password' : 'current-password';
  };
  $('accessForm').addEventListener('submit', async event => {
    event.preventDefault();
    $('accessSubmit').disabled = true;
    const body = JSON.stringify({username:$('reviewerName').value, password:$('reviewerPassword').value});
    try {
      if (setupRequired) {
        await apiCall('/api/auth/setup', {method:'POST',body});
        setupRequired = false;
      }
      const result = await apiCall('/api/auth/login', {method:'POST',body});
      await enterWorkspace(result.user);
    } catch (error) { $('accessMessage').textContent = error.message; }
    finally { $('accessSubmit').disabled = false; }
  });
  try {
    await checkSetup();
    if (!setupRequired) {
      const response = await fetch('/api/auth/me');
      if (response.ok) await enterWorkspace((await response.json()).user);
    }
  } catch (error) { $('accessMessage').textContent = `Cannot connect to RISKORA: ${error.message}. Restart the server and reload.`; }
}

const profileNames = {Age:'age',Income:'income',LoanAmount:'loan_amount',CreditScore:'credit_score',MonthsEmployed:'months_employed',NumCreditLines:'num_credit_lines',InterestRate:'interest_rate',LoanTerm:'loan_term',DTIRatio:'dti_ratio',Education:'education',EmploymentType:'employment_type',MaritalStatus:'marital_status',HasMortgage:'has_mortgage',HasDependents:'has_dependents',LoanPurpose:'loan_purpose',HasCoSigner:'has_cosigner'};
const fieldLabels = {Income:'Annual income (₹)',LoanAmount:'Loan amount (₹)',InterestRate:'Annual interest rate (%)',LoanTerm:'Loan term (months)',DTIRatio:'Debt-to-income ratio (0–1.5)',MonthsEmployed:'Months employed',NumCreditLines:'Number of credit lines',CreditScore:'Credit score'};

async function openLoanForm(edit = false) {
  try {
    if (edit && !activeCase) return;
    if (edit && activeFunding) throw new Error('A funded loan cannot be edited.');
    const schema = await apiCall('/api/schema');
    editingLoan = edit ? activeCase.id : null;
    $('loanFormTitle').textContent = edit ? 'Edit borrower and loan' : 'Create loan';
    $('loanError').textContent = '';
    $('loanFields').innerHTML = '<label>Borrower name<input name="name" required maxlength="200"></label>';
    for (const [field,[min,max,integer]] of Object.entries(schema.numeric)) {
      const label = fieldLabels[field] || field;
      $('loanFields').insertAdjacentHTML('beforeend', `<label>${esc(label)}${schema.required.includes(field)?' *':''}<input type="number" name="${field}" min="${min}" max="${max}" step="${integer?'1':'any'}" ${schema.required.includes(field)?'required':''}></label>`);
    }
    for (const [field,values] of Object.entries(schema.categories)) {
      const label = field.replace(/([a-z])([A-Z])/g,'$1 $2');
      $('loanFields').insertAdjacentHTML('beforeend', `<label>${esc(label)}<select name="${field}"><option value="">Not provided</option>${values.map(v=>`<option>${esc(v)}</option>`).join('')}</select></label>`);
    }
    if (edit) {
      $('loanForm').elements.name.value = activeCase.borrower_name;
      for (const [field,key] of Object.entries(profileNames)) $('loanForm').elements[field].value = activeCase[key] ?? '';
    }
    $('loanDialog').showModal();
  } catch(error) { showToast(error.message,'error'); }
}

function renderReview() {
  const panel = $('reviewPanel');
  if (!panel) return;
  if (!activeCase || !activeAnalysis) { panel.innerHTML = '<h2>Human review</h2><p>Save borrower details and assess the case to prepare the ORA review brief.</p>'; return; }
  const ora = activeCase.ora;
  const decision = activeCase.review_decision;
  const reviewable = ['RISK_ASSESSED','NEEDS_VERIFICATION'].includes(activeCase.status) && reviewer?.role !== 'VIEWER';
  panel.innerHTML = `<div class="eyebrow">ORA · REVIEW ASSISTANT</div><h2>Evidence and human decision</h2><p>Stage: <b>${esc(activeCase.status.replaceAll('_',' '))}</b></p>${activeCase.ledger?.warning ? `<p role="alert">${esc(activeCase.ledger.warning)}</p>` : ''}
    ${ora ? `<p>${esc(ora.verdict)}</p><p>${esc(ora.source)} · Model ${esc(ora.model_version)}</p><div class="integration-grid">${ora.evidence.map(e=>`<div class="evidence-item"><b>${esc(e.factor)}</b><p>${esc(e.value ?? 'Missing')}</p><small>${esc(e.source)}</small></div>`).join('')}</div><p>Missing fields: ${esc(ora.missing_fields.join(', ') || 'None reported')}</p><p>${esc(ora.warnings.join(' ') || 'No input rule warnings. Documents still require reviewer verification.')}</p><small>${esc(ora.disclosure)}</small><details><summary>Assessment snapshot</summary><p>Assessment ${ora.assessment_id}</p><code class="digest">${esc(ora.input_digest)}</code></details>` : ''}
    ${decision ? `<p>Last decision: ${esc(decision.decision)} by ${esc(decision.username)}. ${esc(decision.note)}</p>` : ''}
    ${reviewable ? `<form id="reviewForm"><label>Review decision<select id="reviewChoice"><option value="NEEDS_VERIFICATION">Needs verification</option><option value="APPROVED">Approve funding</option><option value="REJECTED">Reject</option></select></label><label>Review note<textarea id="reviewNote" required minlength="5" maxlength="2000" placeholder="Record the checks performed and the reason for your decision."></textarea></label><button class="btn dark" type="submit">Save review decision</button></form>` : '<p>Review decisions are available after assessment, before funding.</p>'}
    <button class="btn" id="auditButton" type="button">Show review history</button><div id="auditHistory"></div>`;
  $('reviewForm')?.addEventListener('submit', async event => {
    event.preventDefault();
    const button = event.submitter; button.disabled = true;
    try {
      await apiCall(`/api/loans/${activeCase.id}/review`, {method:'POST',body:JSON.stringify({decision:$('reviewChoice').value,note:$('reviewNote').value,assessment_id:activeAnalysis.id})});
      await openCaseById(activeCase.id,false);
      renderDecision(); renderReview(); await loadCaseQueue();
      showToast('Review decision saved.','success');
    } catch(error) { showToast(error.message,'error'); button.disabled = false; }
  });
  $('auditButton').onclick = async () => {
    try {
      const data = await apiCall(`/api/loans/${activeCase.id}/audit`);
      $('auditHistory').innerHTML = data.decisions.map(d=>`<p>${esc(d.created_at)} · ${esc(d.username)} · ${esc(d.decision)}<br>${esc(d.note)}</p>`).join('') || '<p>No review decisions yet.</p>';
    } catch(error) { showToast(error.message,'error'); }
  };
}

function openPaymentDialog(installment, remaining) {
  if (activeCase.ledger?.requires_reconciliation) { showToast(activeCase.ledger.warning, 'warning'); return; }
  paymentContext = {loanId:activeCase.id, installmentNum:installment, scheduleId:activeRepayment.id};
  $('paymentDue').textContent = `Installment #${installment} · Remaining ${money(remaining)}. Partial payments are supported.`;
  $('paymentAmount').value = remaining.toFixed(2);
  $('paymentAmount').max = remaining;
  $('paymentReference').value = crypto.randomUUID();
  $('paymentError').textContent = '';
  $('paymentDialog').showModal();
}

window.addEventListener('DOMContentLoaded', () => {
  $('newLoan').onclick = () => openLoanForm();
  $('editLoan').onclick = () => openLoanForm(true);
  $('manageAccounts').onclick = () => $('accountDialog').showModal();
  $('logoutButton').onclick = async () => {
    try { await apiCall('/api/auth/logout',{method:'POST',body:'{}'}); lockWorkspace(); }
    catch(error) { showToast(error.message,'error'); }
  };
  document.querySelectorAll('[data-close]').forEach(button=>button.onclick=() => $(button.dataset.close).close());
  $('loanForm').onsubmit = async event => {
    event.preventDefault(); event.submitter.disabled = true;
    const data = Object.fromEntries(new FormData(event.target));
    try {
      const result = await apiCall(editingLoan ? `/api/loans/${editingLoan}/edit` : '/api/loans', {method:'POST',body:JSON.stringify(data)});
      $('loanDialog').close();
      await openCaseById(result.id || result.loan_id);
      await loadCaseQueue();
      showToast('Loan saved. Assess the current profile before review.','success');
    } catch(error) { $('loanError').textContent = error.message; }
    finally { event.submitter.disabled = false; }
  };
  $('paymentForm').onsubmit = async event => {
    event.preventDefault(); event.submitter.disabled = true;
    try {
      const result = await apiCall('/api/repayment/record', {method:'POST',body:JSON.stringify({...paymentContext,amount:$('paymentAmount').value,idempotencyKey:$('paymentReference').value})});
      $('paymentDialog').close();
      await openCaseById(paymentContext.loanId,false);
      await loadExposurePortfolio(); renderDecision(); renderReview();
      showToast(result.duplicate ? 'This payment was already recorded; no duplicate was created.' : 'Payment recorded and lender balances updated.','success');
    } catch(error) { $('paymentError').textContent = error.message; }
    finally { event.submitter.disabled = false; }
  };
  $('accountForm').onsubmit = async event => {
    event.preventDefault(); event.submitter.disabled = true;
    try {
      await apiCall('/api/auth/accounts', {method:'POST',body:JSON.stringify(Object.fromEntries(new FormData(event.target)))});
      event.target.reset(); $('accountDialog').close(); showToast('Account created.','success');
    } catch(error) { $('accountError').textContent = error.message; }
    finally { event.submitter.disabled = false; }
  };
});
