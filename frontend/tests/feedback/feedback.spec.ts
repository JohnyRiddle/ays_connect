import { test, expect, Page } from "@playwright/test";

async function setup(page: Page, owner = false) {
  await page.addInitScript(() => sessionStorage.setItem("access", "synthetic-ui-only"));
  await page.route("**/api/**", async route => {
    const path = new URL(route.request().url()).pathname;
    let body: unknown = { results: [], count: 0 };
    if (path.endsWith("/auth/me/")) body = { id: 1, full_name: "Тестовый сотрудник", email: "synthetic@example.test", roles: [], employee: { id: "synthetic", position: "Сотрудник" }, is_demo: false };
    else if (path.endsWith("/employees/dashboard/")) return route.fulfill({ status: 403, json: {} });
    else if (path.endsWith("/feedback/capabilities/")) body = { can_read: owner };
    else if (path.endsWith("/feedback/")) body = { count: 1, next: null, results: [{ id: "synthetic-feedback", kind: "bug", text: "Закрытое синтетическое обращение", author_name: "Тестовый автор", created_at: "2026-10-21T10:00:00Z", delivery_status: "unknown" }] };
    await route.fulfill({ json: body });
  });
  await page.goto("/#notifications");
  await page.getByRole("button", { name: "Обратная связь", exact: true }).click();
  await expect(page.getByRole("dialog")).toBeVisible();
}

for (const width of [1280, 390]) {
  test(`form validation, cancel, close and visual layout ${width}`, async ({ page }) => {
    await page.setViewportSize({ width, height: 844 }); await setup(page);
    const dialog = page.getByRole("dialog");
    await expect(dialog.getByText(/полным текстом в его личный Telegram/)).toBeVisible();
    await expect(dialog.getByRole("button", { name: "Закрытая история обращений" })).toHaveCount(0);
    await dialog.getByRole("button", { name: "Отправить Ивану" }).click();
    await expect(dialog.getByRole("alert")).toHaveText("Введите текст обращения.");
    await dialog.getByLabel("Тип обращения").selectOption("bug");
    await dialog.getByLabel("Текст обращения").fill("Синтетическая проверка формы. Никаких реальных данных.");
    await page.screenshot({ path: `test-results/feedback-${width}.png` });
    expect(await dialog.evaluate(el => el.scrollWidth <= el.clientWidth)).toBe(true);
    expect(await page.evaluate(() => document.documentElement.scrollWidth <= innerWidth)).toBe(true);
    await page.keyboard.press("Escape");
    await expect(dialog).not.toBeVisible();
    await expect(page.getByRole("button", { name: "Обратная связь", exact: true })).toBeFocused();
    await page.getByRole("button", { name: "Обратная связь", exact: true }).click();
    await expect(dialog.getByLabel("Текст обращения")).not.toHaveValue("");
    await dialog.getByRole("button", { name: "Отмена", exact: true }).click();
    await page.getByRole("button", { name: "Обратная связь", exact: true }).click();
    await expect(dialog.getByLabel("Текст обращения")).toHaveValue("");
    await page.getByRole("button", { name: "Закрыть обратную связь" }).click();
    await expect(dialog).not.toBeVisible();
  });

  test(`lost response retry uses same payload and closing pending is safe ${width}`, async ({ page }) => {
    await page.setViewportSize({ width, height: 844 }); await setup(page);
    const requests: any[] = [];
    await page.route("**/feedback/submit/", async route => {
      requests.push(route.request().postDataJSON());
      if (requests.length === 1) return route.abort();
      if (requests.length === 2) return route.fulfill({ status: 429, json: { detail: "Повторите позже" } });
      await route.fulfill({ json: { id: "saved", saved: true } });
    });
    const dialog = page.getByRole("dialog");
    await dialog.getByLabel("Текст обращения").fill("Синтетический текст");
    await dialog.getByRole("button", { name: "Отправить Ивану" }).dblclick();
    await expect(dialog.getByRole("alert")).toBeVisible();
    await expect(dialog.getByLabel("Текст обращения")).toBeDisabled();
    expect(requests.length).toBe(1);
    await page.keyboard.press("Escape");
    await page.getByRole("button", { name: "Обратная связь", exact: true }).click();
    await dialog.getByRole("button", { name: "Повторить отправку" }).click();
    await expect(dialog.getByRole("alert")).toBeVisible();
    await expect(dialog.getByLabel("Текст обращения")).toBeDisabled();
    await dialog.getByRole("button", { name: "Повторить отправку" }).click();
    await expect(dialog.getByText("Обращение сохранено", { exact: true })).toBeVisible();
    expect(requests[0]).toEqual(requests[1]);
    expect(requests[0]).toEqual(requests[2]);
    expect(Object.keys(requests[0]).sort()).toEqual(["command_id", "kind", "text"]);
    await dialog.getByRole("button", { name: "Готово" }).click();
  });

  test(`owner history, retry confirmation and dark theme ${width}`, async ({ page }) => {
    await page.setViewportSize({ width, height: 844 }); await setup(page, true);
    await page.getByRole("button", { name: "Закрытая история обращений" }).click();
    await expect(page.getByText("Закрытое синтетическое обращение")).toBeVisible();
    let retries = 0;
    await page.route("**/feedback/*/retry/", route => { retries++; return route.fulfill({ json: { status: "pending" } }); });
    page.once("dialog", dialog => dialog.dismiss());
    await page.getByRole("button", { name: "Проверил Telegram — повторить доставку" }).click();
    expect(retries).toBe(0);
    page.once("dialog", dialog => dialog.accept());
    await page.getByRole("button", { name: "Проверил Telegram — повторить доставку" }).click();
    await expect(page.getByText("Ожидает Telegram")).toBeVisible();
    expect(retries).toBe(1);
    await page.evaluate(() => document.documentElement.setAttribute("data-theme", "dark"));
    await page.screenshot({ path: `test-results/feedback-owner-dark-${width}.png` });
  });

  test(`closing loading history does not lock submission ${width}`, async ({ page }) => {
    await page.setViewportSize({ width, height: 844 }); await setup(page, true);
    let finish: (() => void) | undefined;
    const pending = new Promise<void>(resolve => { finish = resolve; });
    await page.route("**/feedback/?page=1", async route => { await pending; await route.fulfill({ json: { results: [], next: null } }); });
    await page.getByRole("button", { name: "Закрытая история обращений" }).click();
    await expect(page.getByText("Загрузка…", { exact: true })).toBeVisible();
    await page.getByRole("button", { name: "Написать обращение" }).click();
    await expect(page.getByLabel("Текст обращения")).toBeEnabled();
    await expect(page.getByRole("button", { name: "Отправить Ивану" })).toBeEnabled();
    finish!();
  });
}
