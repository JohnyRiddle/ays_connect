// Run with: node --test tests/auth/work-api.test.cjs
const { test } = require('node:test');
const assert = require('node:assert/strict');
const fs = require('node:fs');
const vm = require('node:vm');
const { stripTypeScriptTypes } = require('node:module');
const source = fs.readFileSync('src/workApi.ts', 'utf8').replaceAll('import.meta.env.VITE_API_URL', 'undefined');
const compiled = stripTypeScriptTypes(source, { mode: 'transform' }).replace(/^export /gm, '') + '\nexports.workRequest = workRequest; exports.workDownload = workDownload;';
const ok = (body) => new Response(JSON.stringify(body), { status: 200 });
const unauthorized = () => new Response('{}', { status: 401 });
const deferred = () => { let resolve; const promise = new Promise(r => { resolve = r; }); return { promise, resolve }; };
const settle = async () => { for (let i = 0; i < 20; i++) await Promise.resolve(); };
function setup(fetch) {
  const values = new Map([['access', 'old'], ['refresh', 'refresh-old'], ['unrelated', 'keep']]);
  const timers = new Set();
  const context = { exports: {}, FormData, AbortController, fetch, sessionStorage: {
    getItem: key => values.get(key) ?? null,
    setItem: (key, value) => values.set(key, value),
    removeItem: key => values.delete(key),
    clear: () => values.clear(),
  }, setTimeout: fn => { timers.add(fn); return fn; }, clearTimeout: fn => timers.delete(fn) };
  vm.runInNewContext(compiled, context);
  return { api: context.exports, values, timers };
}
test('concurrent 401s share one rotated refresh and retry', async () => {
  const refresh = deferred(); let refreshes = 0;
  const { api, values } = setup(async (url, opts) => {
    if (url.endsWith('/auth/refresh/')) { refreshes++; return refresh.promise; }
    return opts.headers.Authorization === 'Bearer old' ? unauthorized() : ok(['updated']);
  });
  const a = api.workRequest('/a/'), b = api.workRequest('/b/');
  await settle(); assert.equal(refreshes, 1);
  refresh.resolve(ok({ access: 'new', refresh: 'refresh-new' }));
  assert.deepEqual(JSON.parse(JSON.stringify(await Promise.all([a, b]))), [['updated'], ['updated']]);
  assert.equal(values.get('refresh'), 'refresh-new');
});
test('aborting one waiter does not abort shared refresh or another waiter', async () => {
  const refresh = deferred(); let sharedSignal;
  const { api } = setup(async (url, opts) => {
    if (url.endsWith('/auth/refresh/')) { sharedSignal = opts.signal; return refresh.promise; }
    return opts.headers.Authorization === 'Bearer old' ? unauthorized() : ok([]);
  });
  const controller = new AbortController();
  const a = api.workRequest('/a/', { signal: controller.signal }), b = api.workRequest('/b/');
  const rejected = assert.rejects(a, /Запрос отменён/);
  await settle(); controller.abort(); await rejected;
  assert.equal(sharedSignal.aborted, false);
  refresh.resolve(ok({ access: 'new', refresh: 'refresh-new' }));
  await b;
});
test('bounded hung refresh releases flight, preserves session, permits recovery', async () => {
  let refreshes = 0, sharedSignal;
  const { api, values, timers } = setup(async (url, opts) => {
    if (url.endsWith('/auth/refresh/')) {
      refreshes++; sharedSignal = opts.signal;
      return refreshes === 1 ? new Promise(() => {}) : ok({ access: 'new' });
    }
    return opts.headers.Authorization === 'Bearer old' ? unauthorized() : ok([]);
  });
  const a = api.workRequest('/a/'); const rejected = assert.rejects(a, error => error.kind === 'network');
  await settle(); [...timers][0](); await rejected;
  assert.equal(sharedSignal.aborted, true); assert.equal(values.get('access'), 'old');
  await api.workRequest('/a/'); assert.equal(refreshes, 2);
});
test('late 401 uses token already refreshed by another request', async () => {
  const late = deferred(); let refreshes = 0;
  const { api } = setup(async (url, opts) => {
    if (url.endsWith('/auth/refresh/')) { refreshes++; return ok({ access: 'new', refresh: 'refresh-new' }); }
    if (url.endsWith('/late/') && opts.headers.Authorization === 'Bearer old') return late.promise;
    return opts.headers.Authorization === 'Bearer old' ? unauthorized() : ok([]);
  });
  const b = api.workRequest('/late/'); await api.workRequest('/a/');
  late.resolve(unauthorized()); await b; assert.equal(refreshes, 1);
});
test('temporary refresh failure retains tokens for next poll', async () => {
  const { api, values } = setup(async url => url.endsWith('/auth/refresh/') ? new Response('{}', { status: 503 }) : unauthorized());
  await assert.rejects(api.workRequest('/a/'), error => error.kind === 'network');
  assert.equal(values.get('access'), 'old'); assert.equal(values.get('refresh'), 'refresh-old');
});
test('rejected refresh clears only auth tokens, not unrelated state', async () => {
  const { api, values } = setup(async () => unauthorized());
  await assert.rejects(api.workRequest('/a/'), error => error.status === 401);
  assert.equal(values.has('access'), false); assert.equal(values.has('refresh'), false);
  assert.equal(values.get('unrelated'), 'keep');
});
test('logout during refresh cannot resurrect session', async () => {
  const refresh = deferred();
  const { api, values } = setup(async url => url.endsWith('/auth/refresh/') ? refresh.promise : unauthorized());
  const request = api.workRequest('/a/'); const rejected = assert.rejects(request, error => error.status === 401);
  await settle(); values.delete('access'); values.delete('refresh');
  refresh.resolve(ok({ access: 'new', refresh: 'refresh-new' })); await rejected;
  assert.equal(values.has('access'), false); assert.equal(values.has('refresh'), false);
});
test('new login does not join or get erased by the old session refresh', async () => {
  const oldFlight = deferred(), newFlight = deferred(); let refreshes = 0;
  const { api, values } = setup(async (url, opts) => {
    if (url.endsWith('/auth/refresh/')) {
      refreshes++;
      return JSON.parse(opts.body).refresh === 'refresh-old' ? oldFlight.promise : newFlight.promise;
    }
    return opts.headers.Authorization === 'Bearer new-rotated' ? ok([]) : unauthorized();
  });
  const old = api.workRequest('/old-session/');
  const oldRejected = assert.rejects(old, error => error.status === 401);
  await settle(); values.set('access', 'new-login'); values.set('refresh', 'refresh-new-login');
  const newer = api.workRequest('/new-session/'); await settle(); assert.equal(refreshes, 2);
  oldFlight.resolve(ok({ access: 'old-rotated', refresh: 'old-rotated-refresh' })); await oldRejected;
  assert.equal(values.get('access'), 'new-login'); assert.equal(values.get('refresh'), 'refresh-new-login');
  // Old cleanup must not clear the newer flight, either.
  const third = api.workRequest('/new-session-second-request/'); await settle(); assert.equal(refreshes, 2);
  newFlight.resolve(ok({ access: 'new-rotated', refresh: 'new-rotated-refresh' }));
  await Promise.all([newer, third]); assert.equal(values.get('access'), 'new-rotated');
});
