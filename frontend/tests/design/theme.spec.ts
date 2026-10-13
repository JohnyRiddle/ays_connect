import { test, expect, Page } from "@playwright/test";

const taskId = "00000000-0000-4000-8000-000000000003";
const task = {
  id: taskId, number: "TASK-000003", title: "Провести аудит локальной сети",
  description: "Проверить оборудование и подготовить отчёт.", status: "in_progress", priority: "normal",
  due_at: "2026-10-13T14:39:00+07:00", version: 4, acceptance_policy: "author",
  responsible_employee_display: "Демо Алексей", responsible_target_display: "Демо Алексей",
  executor_employee_display: "Демо Мария", executor_target_display: "Демо Мария",
  available_actions: ["complete", "wait_external", "watch"], checklist_progress: { completed: 0, total: 0 },
};
async function fixture(page: Page) {
  await page.addInitScript(() => {
    if (!localStorage.getItem("ays-connect-theme")) localStorage.setItem("ays-connect-theme", "light");
    sessionStorage.setItem("access", "isolated-ui-fixture");
  });
  await page.route("**/api/**", async route => {
    const p = new URL(route.request().url()).pathname;
    let data: unknown = { count: 0, results: [] };
    if (p.endsWith("/auth/me/")) data = { id: 1, full_name: "Демо Алексей", email: "demo@example.invalid", roles: [], employee: null, is_demo: false };
    else if (p.endsWith(`/tasks/${taskId}/`)) data = task;
    else if (p.endsWith("/comments/") || p.endsWith("/attachments/") || p.endsWith("/watchers/") || p.endsWith("/checklists/")) data = [];
    else if (p.endsWith("/activity/")) data = { results: [{ id: "activity-1", title: "Задача принята в работу", created_at: "2026-10-12T10:00:00Z" }] };
    else if (p.endsWith("/employees/dashboard/")) { await route.fulfill({ status: 503, json: {} }); return; }
    else if (p.endsWith("/people/me/")) data = { full_name: "Демо Алексей", profile: {} };
    await route.fulfill({ status: 200, json: data });
  });
}
test.beforeEach(async ({ page }) => fixture(page));

test("theme switches and persists; logo lettering follows the selected theme", async ({ page }) => {
  await page.goto(`/tasks/${taskId}`);
  await expect(page.getByRole("heading", { name: task.title, exact: true })).toBeVisible();
  await expect(page.locator("html")).toHaveAttribute("data-theme", "light");
  await expect(page.locator(".brand-logo")).toHaveCSS("color", "rgb(56, 56, 56)");
  await page.getByLabel("Включить тёмную тему").click();
  await expect(page.locator("html")).toHaveAttribute("data-theme", "dark");
  await expect(page.locator(".brand-logo")).toHaveCSS("color", "rgb(255, 255, 255)");
  expect(await page.evaluate(() => localStorage.getItem("ays-connect-theme"))).toBe("dark");
  await page.reload();
  await expect(page.getByRole("heading", { name: task.title, exact: true })).toBeVisible();
  await expect(page.locator("html")).toHaveAttribute("data-theme", "dark");
  await page.getByRole("button", { name: "← К задачам", exact: true }).click();
  await expect(page.locator("html")).toHaveAttribute("data-theme", "dark");
});

test("task history, technical assignments and permission-derived action dialog remain accessible", async ({ page }) => {
  await page.goto(`/tasks/${taskId}`);
  await page.getByRole("button", { name: "История изменений", exact: true }).click();
  await expect(page.getByText("Задача принята в работу", { exact: true })).toBeVisible();
  await expect(page.getByLabel("Новый комментарий")).toBeHidden();
  await page.getByText("Сведения о назначении", { exact: true }).click();
  await expect(page.getByText("Версия задачи", { exact: true })).toBeVisible();
  await page.getByRole("button", { name: "Выполнить", exact: true }).click();
  await expect(page.getByLabel("Результат выполнения")).toBeVisible();
  await expect(page.getByText(/приёмк/).first()).toBeVisible();
});

test("task detail reflows on mobile without losing its actions", async ({ page }) => {
  await page.setViewportSize({ width: 390, height: 844 });
  await page.goto(`/tasks/${taskId}`);
  await expect(page.getByRole("heading", { name: task.title, exact: true })).toBeVisible();
  await expect(page.getByRole("button", { name: "Выполнить", exact: true })).toBeVisible();
  expect(await page.evaluate(() => document.documentElement.scrollWidth <= innerWidth)).toBe(true);
  await page.getByLabel("Открыть основное меню").click();
  await expect(page.locator(".sidebar")).toHaveClass(/open/);
});
