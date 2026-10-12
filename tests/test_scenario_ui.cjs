const assert = require('node:assert/strict');
const fs = require('node:fs');
const path = require('node:path');
const vm = require('node:vm');
const { test } = require('node:test');

const root = path.resolve(__dirname, '..');
const html = fs.readFileSync(path.join(root, 'index.html'), 'utf8');
const script = fs.readFileSync(path.join(root, 'app.js'), 'utf8');

function workstation(fetch) {
  const elements = {};
  const context = vm.createContext({
    document: { getElementById: id => elements[id] ??= {
      value: '', textContent: 'Previous result', nextElementSibling: { textContent: 'Previous terms' }
    } },
    window: { addEventListener() {} },
    console: { error() {} },
    AbortSignal, fetch,
  });
  vm.runInContext(script, context);
  for (const id of ['scenarioRisk', 'scenarioDelta', 'scenarioPd', 'scenarioPdDelta',
    'scenarioEmi', 'scenarioFunding', 'scenarioDecision']) context.document.getElementById(id);
  vm.runInContext(`activeCase = {id: 'test-loan', loan_amount: 40000, credit_score: 782,
    dti_ratio: 0.16, loan_term: 12, interest_rate: 9.5};
    $('scenarioCreditSlider').value = '782';
    $('scenarioDtiSlider').value = '0.16';`, context);
  return {
    elements,
    update(amount) {
      context.document.getElementById('scenarioSlider').value = String(amount);
      return vm.runInContext('updateScenarioLab()', context);
    },
  };
}

function response(score = 42) {
  return { ok: true, json: async () => ({
    scenario: { score, level: 'MEDIUM', pd_pct: 12, indicative_emi: 125000,
      recommended_mode: 'fractional' },
    comparison: { score_delta: 10, pd_delta_pts: 4 },
  }) };
}

test('fractional slider amounts are sent at monetary precision and match the display', async () => {
  let payload;
  const ui = workstation(async (url, options) => {
    assert.equal(url, '/api/risk/simulate');
    payload = JSON.parse(options.body);
    return response();
  });
  await ui.update(1448324.389739);
  assert.equal(payload.scenario.LoanAmount, 1448324.39);
  assert.equal(ui.elements.scenarioAmount.textContent, '₹14,48,324.39');
  assert.equal(ui.elements.scenarioRisk.textContent, '42/100 (MEDIUM)');
});

test('amount slider permits cents and stays within the API amount limits', () => {
  const input = html.match(/<input\b[^>]*id="scenarioSlider"[^>]*>/)[0];
  const attributes = Object.fromEntries([...input.matchAll(/(\w+)="([^"]*)"/g)].map(m => [m[1], m[2]]));
  assert.equal(Number(attributes.min), 0.01);
  assert.equal(Number(attributes.max), 5000000);
  assert.equal(Number(attributes.step), 0.01);
});

test('pending and failed requests clear all previous simulation outputs', async () => {
  let reject;
  const ui = workstation(() => new Promise((resolve, fail) => { reject = fail; }));
  const pending = ui.update(1448324.39);
  assert.equal(ui.elements.scenarioRisk.textContent, 'Calculating…');
  for (const id of ['scenarioPd', 'scenarioPdDelta', 'scenarioEmi', 'scenarioFunding', 'scenarioDecision']) {
    assert.equal(ui.elements[id].textContent, '—', id);
  }
  reject(new Error('Simulation service unavailable'));
  await pending;
  assert.equal(ui.elements.scenarioRisk.textContent, 'Unavailable');
  assert.equal(ui.elements.scenarioDelta.textContent, 'Simulation service unavailable');
  assert.equal(ui.elements.scenarioEmi.nextElementSibling.textContent, '—');
  for (const id of ['scenarioPd', 'scenarioPdDelta', 'scenarioEmi', 'scenarioFunding', 'scenarioDecision']) {
    assert.equal(ui.elements[id].textContent, '—', id);
  }
});

test('a late failure from an older slider request cannot replace the latest result', async () => {
  let rejectOld;
  let calls = 0;
  const ui = workstation(() => ++calls === 1
    ? new Promise((resolve, reject) => { rejectOld = reject; })
    : Promise.resolve(response(50)));
  const old = ui.update(50000);
  await ui.update(60000);
  rejectOld(new Error('Old request failed'));
  await old;
  assert.equal(ui.elements.scenarioRisk.textContent, '50/100 (MEDIUM)');
  assert.equal(ui.elements.scenarioPd.textContent, '12%');
});
