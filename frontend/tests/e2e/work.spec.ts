import { APIRequestContext, expect, Page, test } from "@playwright/test";

async function login(page: Page) {
  const email = process.env.AYS_E2E_EMAIL;
  const password = process.env.AYS_E2E_PASSWORD;
  test.skip(!email || !password, "AYS_E2E_EMAIL and AYS_E2E_PASSWORD are required");
  await page.getByLabel("Электронная почта").fill(email!);
  await page.getByLabel("Пароль").fill(password!);
  await page.getByRole("button", { name: "Войти" }).click();
}

async function adminAccess(request: APIRequestContext) {
  const email = process.env.AYS_E2E_EMAIL;
  const password = process.env.AYS_E2E_PASSWORD;
  test.skip(!email || !password, "Pilot administrator credentials are required");
  const response = await request.post("/api/v1/auth/login/", { data: { email, password } });
  expect(response.status()).toBe(200);
  return (await response.json()).access as string;
}

function runtimeIdentity(prefix: string) {
  const marker = `${Date.now()}-${Math.floor(Math.random() * 100000)}`;
  return { email: `${prefix}-${marker}@example.test`, number: `${prefix}-${marker}`, password: `Z!9q-${crypto.randomUUID()}-Lm#` };
}

for (const route of [
  "/tasks",
  "/tasks/new",
  "/requests",
  "/requests/new",
  "/notifications/settings",
  "/register",
  "/activate/safe-invalid-token",
  "/people/employees",
  "/people/employees/00000000-0000-0000-0000-000000000000",
  "/people/registrations",
]) {
  test(`SPA fallback serves ${route}`, async ({ page }) => {
    const response = await page.goto(route);
    expect(response?.status()).toBe(200);
    if (route === "/register") await expect(page.getByRole("heading", { name: "Заявка на доступ" })).toBeVisible();
    else if (route.startsWith("/activate/")) await expect(page.getByRole("heading", { name: "Ссылка недоступна" })).toBeVisible();
    else await expect(page.getByRole("heading", { name: "Вход в систему" })).toBeVisible();
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

test("invitation activates a scoped employee and blocked account cannot login", async ({ page, request }) => {
  const identity = runtimeIdentity("invite"); const access = await adminAccess(request); const headers = { Authorization: `Bearer ${access}` };
  const created = await request.post("/api/internal/v1/employees/", { headers, data: { first_name: "Browser", last_name: "Invite", employee_number: identity.number, is_active: true, status: "active" } });
  expect(created.status()).toBe(201); const employee = await created.json();
  const roles = await (await request.get("/api/internal/v1/roles/", { headers })).json(); const workRole = roles.results.find((x:any) => x.code === "gate-16c-work"); expect(workRole).toBeTruthy();
  expect((await request.post(`/api/internal/v1/employees/${employee.id}/roles/`, { headers, data: { role: workRole.id } })).status()).toBe(201);
  const issued = await request.post(`/api/internal/v1/people/employees/${employee.id}/invite/`, { headers, data: { email: identity.email } });
  expect(issued.status()).toBe(201); const invitation = await issued.json();
  await page.goto(new URL(invitation.activation_url).pathname);
  await page.getByLabel("Пароль", { exact: true }).fill(identity.password);
  await page.getByLabel("Повторите пароль").fill(identity.password);
  await page.getByRole("button", { name: "Активировать аккаунт" }).click();
  await expect(page.getByRole("heading", { name: "Аккаунт активирован" })).toBeVisible();
  await page.getByRole("link", { name: "Войти в AYS Connect" }).click();
  await page.getByLabel("Электронная почта").fill(identity.email); await page.getByLabel("Пароль").fill(identity.password); await page.getByRole("button", { name: "Войти" }).click();
  await page.getByRole("link", { name: "Задачи", exact: true }).click(); await expect(page.getByRole("heading", { name: "Задачи", exact: true })).toBeVisible();
  const blocked = await request.post(`/api/internal/v1/people/employees/${employee.id}/account/block/`, { headers }); expect(blocked.status()).toBe(200);
  await page.evaluate(() => sessionStorage.clear()); await page.goto("/");
  await page.getByLabel("Электронная почта").fill(identity.email); await page.getByLabel("Пароль").fill(identity.password); await page.getByRole("button", { name: "Войти" }).click();
  await expect(page.getByText("Не удалось войти. Проверьте почту и пароль.")).toBeVisible();
  expect((await request.post(`/api/internal/v1/people/employees/${employee.id}/account/unblock/`, { headers })).status()).toBe(200);
});

test("controlled registration stays pending until admin approval", async ({ page, request }) => {
  const identity = runtimeIdentity("register");
  await page.goto("/register"); await page.getByLabel("ФИО").fill("Browser Registration"); await page.getByLabel("Рабочая электронная почта").fill(identity.email); await page.getByRole("button", { name: "Отправить заявку" }).click();
  await expect(page.getByText(/Заявка принята/)).toBeVisible();
  const access = await adminAccess(request); const headers = { Authorization: `Bearer ${access}` };
  const registrations = await (await request.get("/api/internal/v1/people/registrations/", { headers })).json(); const registration = registrations.results.find((x: any) => x.email === identity.email); expect(registration.status).toBe("pending");
  const employee = await (await request.post("/api/internal/v1/employees/", { headers, data: { first_name: "Browser", last_name: "Registration", employee_number: identity.number, is_active: true, status: "active" } })).json();
  const approved = await request.post(`/api/internal/v1/people/registrations/${registration.id}/approve/`, { headers, data: { employee_id: employee.id } }); expect(approved.status()).toBe(200);
  const result = await approved.json(); await page.goto(new URL(result.activation_url).pathname); await page.getByLabel("Пароль", { exact: true }).fill(identity.password); await page.getByLabel("Повторите пароль").fill(identity.password); await page.getByRole("button", { name: "Активировать аккаунт" }).click();
  await expect(page.getByRole("heading", { name: "Аккаунт активирован" })).toBeVisible();
});

test.describe("responsive onboarding", () => {
  test.use({ viewport: { width: 390, height: 844 } });
  test("register activation directory and employee detail remain usable", async ({ page, request }) => {
    await page.goto("/register"); await expect(page.getByRole("heading", { name: "Заявка на доступ" })).toBeVisible();
    await page.goto("/activate/safe-invalid-mobile-token"); await expect(page.getByRole("heading", { name: "Ссылка недоступна" })).toBeVisible();
    await page.goto("/people/employees"); await login(page); await expect(page.getByRole("heading", { name: "Сотрудники" })).toBeVisible();
    const access = await adminAccess(request); const list = await (await request.get("/api/internal/v1/people/employees/", { headers: { Authorization: `Bearer ${access}` } })).json();
    await page.goto(`/people/employees/${list.results[0].id}`); await expect(page.getByRole("heading", { name: list.results[0].display_name })).toBeVisible();
  });
});
