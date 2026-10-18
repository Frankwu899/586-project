'use strict';
const test = require('node:test');
const assert = require('node:assert/strict');
const { createSession, isLocalAddress, isApplicationUrl, backendCommand, privateEnvironment } = require('../session.cjs');
test('session tokens are unpredictable and scoped to exact loopback origins', () => {
  assert.equal(createSession().length, 64);
  assert.notEqual(createSession(), createSession());
  assert.equal(isLocalAddress('http://127.0.0.1:1234'), true);
  for (const candidate of ['https://example.com:1234', 'http://127.0.0.1.example.com:1234', 'file:///secret', 'http://user:secret@127.0.0.1:1234']) assert.equal(isLocalAddress(candidate), false);
  assert.equal(isApplicationUrl('http://127.0.0.1:1234/api/tasks', 'http://127.0.0.1:1234'), true);
  assert.equal(isApplicationUrl('http://127.0.0.1:1235/api/tasks', 'http://127.0.0.1:1234'), false);
});
test('packaged builds use only the bundled backend and media tools', () => {
  assert.deepEqual(backendCommand({ packaged: true, resourcesPath: '/app/Resources', root: '/source' }), { command: '/app/Resources/runtime/video-anatomy-backend/video-anatomy-backend', args: [], cwd: '/app/Resources', mediaBin: '/app/Resources/runtime/media-bin' });
});
test('API credentials are removed from the inherited child environment', () => {
  const previous = process.env.OPENAI_API_KEY;
  process.env.OPENAI_API_KEY = 'fake-test-key';
  const environment = privateEnvironment('/bundled/media');
  assert.equal(environment.OPENAI_API_KEY, undefined);
  assert.equal(environment.PATH.startsWith('/bundled/media'), true);
  if (previous === undefined) delete process.env.OPENAI_API_KEY; else process.env.OPENAI_API_KEY = previous;
});
