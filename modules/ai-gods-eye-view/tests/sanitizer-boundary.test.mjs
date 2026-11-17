import test from 'node:test';
import assert from 'node:assert/strict';
import DOMPurify from '../.upstream/node_modules/dompurify/dist/purify.es.mjs';
import Credit from '../.upstream/node_modules/@cesium/engine/Source/Core/Credit.js';

test('native Cesium credits sanitize string input without DOM-returning or template modes', t => {
  const previous = { sanitize: DOMPurify.sanitize, document: globalThis.document };
  const calls = [];
  DOMPurify.sanitize = (...args) => { calls.push(args); return 'sanitized credit'; };
  globalThis.document = { createElement: () => ({ style: {}, querySelectorAll: () => [] }) };
  t.after(() => { DOMPurify.sanitize = previous.sanitize; globalThis.document = previous.document; });
  const credit = new Credit('<img src=x onerror=alert(1)>');
  assert.equal(credit.element.innerHTML, 'sanitized credit');
  assert.deepEqual(calls, [['<img src=x onerror=alert(1)>']]);
  assert.throws(() => new Credit({ nodeType: 1, shadowRoot: {} }), /string/);
});
