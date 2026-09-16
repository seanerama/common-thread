#!/usr/bin/env node
// Documentation-stage hygiene only. Add application gates when the stack lands.
const assert = require('node:assert/strict');
const fs = require('node:fs');
const path = require('node:path');

const documents = ['README.md', 'CODING_AGENT_HANDOFF.md', 'STATUS.md',
  'docs/product-brief.md', 'docs/architecture.md'];
const required = [...documents, 'LICENSE', '.gitignore',
  '.github/workflows/ci.yml', '.github/ISSUE_TEMPLATE/bug_report.yml',
  '.verity/identity.json', '.verity/config.json', '.verity/gates.json',
  '.verity/run-gates.cjs'];
for (const file of required) {
  assert(fs.statSync(file).isFile(), `Required file missing: ${file}`);
  assert(fs.readFileSync(file, 'utf8').trim(), `Required file empty: ${file}`);
}

const identity = JSON.parse(fs.readFileSync('.verity/identity.json', 'utf8'));
assert.equal(identity.version, '1.0');
assert.equal(identity.name, 'Common Thread');
assert.equal(identity.slug, 'common-thread');
assert.equal(identity.owner, 'seanerama');
assert.equal(identity.image_prefix, 'ghcr.io/seanerama/common-thread');
assert(Number.isFinite(Date.parse(identity.locked_at)), 'Missing valid lock date');
for (const file of ['.verity/config.json', '.verity/gates.json']) {
  JSON.parse(fs.readFileSync(file, 'utf8'));
}

for (const document of documents) {
  const body = fs.readFileSync(document, 'utf8');
  for (const match of body.matchAll(/\[[^\]]+\]\(([^)]+)\)/g)) {
    const target = match[1];
    if (/^(?:[a-z]+:|#)/i.test(target)) continue;
    const file = path.resolve(path.dirname(document), target.split('#')[0]);
    assert(fs.existsSync(file), `${document}: broken link ${target}`);
  }
}
console.log('Repository hygiene passed: identity, required files, and documentation links.');
