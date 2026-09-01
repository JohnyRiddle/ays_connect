import { expect, Page, test } from "@playwright/test";

async function login(page: Page) {
  const email = process.env.AYS_E2E_EMAIL;
  const password = process.env.AYS_E2E_PASSWORD;
  test.skip(!email || !password, "AYS_E2E_EMAIL and AYS_E2E_PASSWORD are required");
  await page.getByLabel("Электронная почта").fill(email!);
  await page.getByLabel("Пароль").fill(password!);
  await page.getByRole("button", { name: "Войти" }).click();
}

for (const route of [
  "/tasks",
  "/tasks/new",
  "/requests",
  "/requests/new",
  "/notifications/settings",
]) {
  test(`SPA fallback serves ${route}`, async ({ page }) => {
    const response = await page.goto(route);
    expect(response?.status()).toBe(200);
    await expect(page.getByRole("heading", { name: "Вход в систему" })).toBeVisible();
  });
}

test("authorized user opens production task list", async ({ page }) => {
  await page.goto("/tasks");
  await login(page);
  await expect(page.getByRole("heading", { name: "Задачи", exact: true })).toBeVisible();
  await expect(page.getByRole("button", { name: "Создать задачу" })).toBeVisible();
});

test("authorized user opens production request list", async ({ page }) => {
  await page.goto("/requests");
  await login(page);
  await expect(page.getByRole("heading", { name: "Заявки", exact: true })).toBeVisible();
  await expect(page.getByRole("button", { name: "Создать заявку" })).toBeVisible();
});
