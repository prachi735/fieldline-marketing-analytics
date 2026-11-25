const assert = require('node:assert/strict');
const fs = require('node:fs');
const vm = require('node:vm');

const html = fs.readFileSync('01-dashboard/index.html', 'utf8');
const elements = new Map();
const context = {
  assert,
  Option: class {},
  document: {
    getElementById(id) {
      if (!elements.has(id)) {
        elements.set(id, {value: '', add() {}, addEventListener(type, fn) { this[type] = fn; }});
      }
      return elements.get(id);
    }
  }
};
const script = html.match(/<script>([\s\S]*?)<\/script>/)[1];
vm.runInNewContext(script + `
  assert.equal(rows.length, 480);
  assert.equal(sum(rows).spend, 2000000);
  for (const c of ['', ...clients]) for (const q of ['', '1', '2', '3', '4'])
    for (const h of ['', ...channels]) {
      element('client').value = c;
      element('quarter').value = q;
      element('channel').value = h;
      element('client').change();
      assert.equal(selected().length, (c ? 1 : 5) * (q ? 3 : 12) * (h ? 2 : 8));
      assert.equal((element('dashboard').innerHTML.match(/class="target"/g) || []).length, q ? 3 : 12);
      assert.doesNotMatch(element('dashboard').innerHTML, /NaN|1 campaigns flagged/);
    }
`, context);
console.log('Dashboard: 150 filter combinations verified.');
