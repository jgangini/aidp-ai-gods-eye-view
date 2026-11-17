import test from 'node:test';
import assert from 'node:assert/strict';
import { mountControls } from '../native/controls.js';

class Element extends EventTarget {
  constructor(tag) { super(); this.tag = tag; this.children = []; this.attributes = {}; }
  setAttribute(name, value) { this.attributes[name] = value; }
  removeAttribute(name) { delete this.attributes[name]; if (name === 'src') delete this.src; }
  append(...children) { this.children.push(...children); }
  showModal() { this.open = true; }
  close() { this.open = false; this.dispatchEvent(new Event('close')); }
  focus() { this.focused = true; }
  remove() { this.removed = true; }
}

function dom(t) {
  const before = { document: globalThis.document, window: globalThis.window };
  const host = new Element('div'), body = new Element('body');
  globalThis.document = { body, createElement: tag => new Element(tag), querySelector: () => host };
  globalThis.window = new EventTarget();
  t.after(() => Object.assign(globalThis, before));
  return { host, body, signal: new AbortController() };
}

test('reader cannot mount administration controls', async t => {
  const { host, body, signal } = dom(t);
  await mountControls({ request: async () => { throw new Error('forbidden'); }, signal: signal.signal });
  assert.equal(host.children.length, 0); assert.equal(body.children.length, 0);
});

test('verified admin opens integrated controls and closes with focus restored', async t => {
  const { host, body, signal } = dom(t);
  const calls = [];
  await mountControls({ request: async path => { calls.push(path); }, signal: signal.signal });
  assert.deepEqual(calls, ['/api/admin/session']);
  const button = host.children[0], dialog = body.children[0], frame = dialog.children[1];
  button.dispatchEvent(new Event('click'));
  assert.equal(frame.src, '/controls/'); assert.equal(dialog.open, true);
  dialog.children[0].children[1].dispatchEvent(new Event('click'));
  assert.equal(dialog.open, false); assert.equal(frame.src, '/controls/'); assert.equal(button.focused, true);
  const event = new Event('gev-open-controls'); event.detail = 'parameters';
  window.dispatchEvent(event);
  assert.equal(frame.src, '/controls/#parameters');
  signal.abort();
  assert.equal(dialog.removed, true); assert.equal(button.removed, true);
});
