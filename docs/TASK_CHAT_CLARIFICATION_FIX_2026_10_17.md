# Chat and clarification fixes, 17 October 2026

## Scope and diagnosis

Source inspected: main `a34d743bce46cd1755685f4806138685e90a60b4`.
The production task chat already polls ordinary comments every five seconds.
Approval records, however, were loaded only on mount or a local command, leaving
another participant's clarification/status changes stale until reload.

The shared Work API client also refreshed independently for concurrent 401s,
although backend settings enable refresh-token rotation and blacklisting.
Its unbounded refresh could hold an otherwise timed-out comment poll pending.
These code paths are established and covered by isolated tests; the user's exact
two-laptop production incident has **not** been reproduced.

## Changes

- A visible circled `!` accompanies «Нужно уточнение» in the collapsed message
  chip and expanded approval card. The existing text remains accessible; the
  decorative symbol is hidden from screen readers. It disappears when the
  approval is no longer `CLARIFICATION_REQUESTED`.
- Approvals now use the existing scoped HTTP API every five seconds while the
  page is visible, plus focus, visibility and online recovery. Reads are serialized,
  bounded and cancelled on task change. A command refresh waits for an older GET
  before obtaining fresh state. Network failures retain existing content and retry;
  access denial clears it. Task status/version/lifecycle remain untouched.
- An open approval decision is pinned to its original version. A remote round
  change disables confirmation until explicit reselection, while retaining the draft.
- Work API authentication shares a bounded refresh between concurrent requests,
  reuses already-rotated tokens, and supports independent caller cancellation.
  Transient refresh failures do not clear the session; late refresh does not
  restore a logged-out session.

No backend, schema, permissions, Telegram, notifications or production data edits.
No SSE/WebSocket infrastructure is introduced for this narrow change.

## Verification

- `npm ci --ignore-scripts --cache /tmp/ays-npm-cache`: PASS.
- `npm run build`: PASS, including TypeScript and Vite; existing large-bundle warning.
- `node --test tests/auth/work-api.test.cjs tests/chat-live/polling.test.cjs tests/chat-live/approval-marker.test.mjs`:
  **20/20 PASS** on Node 24.19.0. These test files require Node >=22.13 because
  they use the built-in TypeScript stripping API. They do not change app runtime requirements.
- Hook tests use deterministic simulated lifecycle/timers, not a real browser.
  They cover independent consumers, queued reads, stale task responses, hidden
  tabs, transient failures and access revocation. Auth tests cover rotation,
  concurrent requests, abort, timeout, recovery, logout and a new login during an
  old refresh. Four actual component server-render tests cover the marker in each
  approval status; these are not visual browser tests.
- `git diff --check`: PASS.
- Browser regression suite prepared: `AYS_CHROMIUM_EXECUTABLE=/usr/bin/chromium
  npx playwright test --config playwright.chat-live.config.ts`. Two independent
  contexts run the actual task UI against shared synthetic API state, at 1280 and
  390 pixels, checking new comments, clarification, resubmission, unchanged task
  status, preserved draft and no navigation. Recovery and remote-round-change
  while a decision form is open are included.
  **NOT EXECUTED successfully:** Chromium fails before any test body with
  `socket() failed: Operation not permitted`; supported elevated execution fails
  during environment setup. Cloud browser cannot reach this isolated workspace's
  localhost server (`ERR_CONNECTION_REFUSED`). This is not a passing UI gate.
- Original card image assets were fetched through raw GitHub and checked against
  their source blob hashes after connector binary reads proved unavailable.
  No substitute assets or dependency/lockfile changes are included.
- No dedicated lint command exists. Backend/PostgreSQL/full existing acceptance
  suites were not run; backend code is unchanged. Live two-account production
  verification and visual/accessibility review remain outstanding.

## Release status

Prepared for an isolated branch and draft review. **Not merged or deployed.**
Do not treat the passing focused tests as production acceptance. Run the browser
suite in an environment that supports Chromium, and perform the authorized
release checks before any deployment. No real messages or notifications were sent.
