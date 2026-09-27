import type { Reporter, TestCase, TestResult, FullResult } from '@playwright/test/reporter';
// Do not emit Playwright call logs: a failed password fill could contain a secret.
export default class SafeReporter implements Reporter {
  onTestEnd(test: TestCase, result: TestResult) {
    const sourceLine = result.error?.stack?.match(/people-acceptance\.spec\.ts:(\d+):\d+/)?.[1];
    console.log(JSON.stringify({test: test.title, status: result.status, sourceLine,
      httpFailures: test.annotations.filter(x=>['safe_http_failure','safe_console_class'].includes(x.type)).map(x=>x.description)}));
  }
  onEnd(result: FullResult) { console.log(JSON.stringify({browser_gate: result.status})); }
}
