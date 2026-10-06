'use strict';
const test = require('node:test');
const assert = require('node:assert/strict');
const fs = require('node:fs');
const path = require('node:path');
const vm = require('node:vm');

const html = fs.readFileSync(path.join(__dirname, '..', 'reviewer-admin.html'), 'utf8');

function sourceBetween(start, end) {
  const a = html.indexOf(start);
  const b = html.indexOf(end, a + start.length);
  assert.ok(a >= 0 && b > a, 'Admin render function missing: ' + start);
  return html.slice(a, b);
}

function panel() {
  const createContainer = () => ({
    children: [],
    innerHTML: '',
    textContent: '',
    appendChild(item) { this.children.push(item); },
    replaceChildren() { this.children = []; },
    querySelector(selector) { return this.children.find(item => item.className === selector.replace('.', '')) || null; }
  });
  const worldCandidateList = createContainer();
  const list = createContainer();
  const pendingCount = { textContent: '' };
  const worldCandidateCount = { textContent: '' };
  const document = {
    createElement() {
      return {
        className: '',
        innerHTML: '',
        querySelector() {
          return { disabled: false, addEventListener() {} };
        }
      };
    }
  };
  const esc = value => String(value ?? '').replace(/[&<>"']/g,
    char => ({'&':'&amp;','<':'&lt;','>':'&gt;','"':'&quot;',"'":'&#39;'})[char]);
  const code = sourceBetween('      function render(applications){', '      function renderReviews(reviews){')
    + '\n' + sourceBetween('      function renderWorldCandidates(candidates,decisions,aiDecisions){',
      '      async function loadCandidateAiDecisions(){');
  const sandbox = { document, list, pendingCount, worldCandidateList, worldCandidateCount,
    esc, fmt: value => String(value || ''), alert() {}, confirm() { return false; }, console };
  vm.createContext(sandbox);
  vm.runInContext(code + '\nthis.renderApplications = render;\nthis.renderCandidates = renderWorldCandidates;', sandbox);
  return sandbox;
}

test('Gemini results and unclassified worlds render without ReferenceError', () => {
  const admin = panel();
  admin.renderCandidates([
    {id:'wrld_aaaaaaaa-aaaa-aaaa-aaaa-aaaaaaaaaaaa',name:'Nightclub A',
     confidenceScore:80,confidence:'medium',sourceCategories:['vrcmap_music'],reasons:['+club']},
    {id:'wrld_bbbbbbbb-bbbb-bbbb-bbbb-bbbbbbbbbbbb',name:'Club B',
     confidenceScore:65,confidence:'medium',sourceCategories:['vrcmap_cafe'],reasons:[]}
  ], [], [
    {id:'wrld_aaaaaaaa-aaaa-aaaa-aaaa-aaaaaaaaaaaa',status:'needs_review',
     classification:{verdict:'not_club',confidence:0.92,reasonJa:'根拠不足'}}
  ]);
  assert.equal(admin.worldCandidateCount.textContent, 2);
  assert.equal(admin.worldCandidateList.children.length, 2);
  assert.match(admin.worldCandidateList.children[0].innerHTML, /Geminiはクラブ以外と判定/);
  assert.match(admin.worldCandidateList.children[0].innerHTML, /92%/);
  assert.match(admin.worldCandidateList.children[1].innerHTML, /Gemini未判定/);
});

test('legacy applicant rendering does not access candidate AI data', () => {
  const admin = panel();
  admin.renderApplications([{
    vrchat_name:'Reviewer Alpha',created_at:'2026-10-06',experience:['Club reviewer'],
    contact:'-',availability:'-',background:'-',affiliations:''
  }]);
  assert.equal(admin.list.children.length, 1);
  assert.match(admin.list.children[0].innerHTML, /Reviewer Alpha/);
});

test('Gemini supplied reason is HTML-escaped', () => {
  const admin = panel();
  admin.renderCandidates([{
    id:'wrld_aaaaaaaa-aaaa-aaaa-aaaa-aaaaaaaaaaaa',name:'Nightclub',
    confidenceScore:85,sourceCategories:[],reasons:[]
  }], [], [{
    id:'wrld_aaaaaaaa-aaaa-aaaa-aaaa-aaaaaaaaaaaa',status:'needs_review',
    classification:{verdict:'uncertain',confidence:0.7,reasonJa:'<script>alert(1)</script>'}
  }]);
  assert.doesNotMatch(admin.worldCandidateList.children[0].innerHTML, /<script>/);
  assert.match(admin.worldCandidateList.children[0].innerHTML, /&lt;script&gt;/);
});
