import {test, expect} from '@playwright/test';
import {readFileSync} from 'node:fs';

const fixturePath = process.env.AYS_TASK_PATCH_FIXTURE;
const fixture = fixturePath ? JSON.parse(readFileSync(fixturePath, 'utf8')) : null;
const api = 'http://127.0.0.1:8017';
let cachedAuth: any;

test.beforeEach(async ({page, request}) => {
  test.skip(!fixture, 'An isolated synthetic task_patch_ui fixture is required');
  if (!cachedAuth) {
    const response = await request.post(api + '/api/v1/auth/login/', {data: {email: fixture.admin_email, password: 'Synthetic-Only-2026!'}});
    expect(response.status()).toBe(200); cachedAuth = await response.json();
  }
  const auth = cachedAuth;
  await page.addInitScript(({access, refresh}) => { sessionStorage.setItem('access', access); sessionStorage.setItem('refresh', refresh); }, auth);
});

for (const width of [1280, 390]) {
  test(`department head, five priorities and creation at ${width}px`, async ({page}) => {
    await page.setViewportSize({width, height: 900});
    await page.goto('/tasks/new');
    await page.getByLabel('Название *', {exact: true}).fill(`Synthetic UI create ${width}`);
    await page.getByLabel('Ответственное подразделение *').selectOption(fixture.department_id);
    await expect(page.getByText(`Ответственный: ${fixture.head_name}`, {exact: true})).toBeVisible();
    const priority = page.getByRole('combobox', {name: /^Приоритет/});
    await expect(priority.locator('option')).toHaveCount(5);
    await priority.selectOption('critical');
    await expect(page.getByLabel('Срок рассчитывается по приоритету')).toBeDisabled();
    const created = page.waitForResponse(r => r.url().endsWith('/api/internal/v1/tasks/') && r.request().method() === 'POST');
    await page.getByRole('button', {name: 'Создать задачу', exact: true}).click();
    const response = await created; expect(response.status()).toBe(201);
    const task = await response.json();
    expect(task.executor_employee).toBeNull();
    expect(new Date(task.due_at).getTime() - new Date(task.created_at).getTime()).toBe(3 * 3600000);
    await expect(page).toHaveURL(new RegExp(`/tasks/${task.id}$`));
    await expect(page.getByRole('heading', {name: `Synthetic UI create ${width}`, exact: true})).toBeVisible();
    expect(await page.evaluate(() => document.documentElement.scrollWidth <= innerWidth)).toBeTruthy();
    await page.screenshot({path: `${process.env.AYS_TASK_PATCH_OUTPUT}/task-${width}.png`, fullPage: true});
  });

  test(`multiple watchers and stored mentions at ${width}px`, async ({page}) => {
    await page.setViewportSize({width, height: 900});
    await page.goto(`/tasks/${fixture.task_id}`);
    const watchers = page.locator('section.work-card').filter({has: page.getByRole('heading', {name: 'Наблюдатели', exact: true})});
    await watchers.getByLabel('Добавить наблюдателей').fill('Synthetic');
    await watchers.getByRole('checkbox', {name: /Synthetic member/}).check();
    await watchers.getByRole('checkbox', {name: /Synthetic head/}).check();
    await watchers.getByRole('button', {name: 'Добавить выбранных'}).click();
    await expect(watchers.locator('.person-row').filter({hasText: 'Synthetic member'})).toBeVisible();
    const comments = page.locator('section.work-card').filter({has: page.getByRole('heading', {name: 'Комментарии', exact: true})});
    const message = `Synthetic mention ${width} ${Date.now()}`;
    await comments.getByLabel('Новый комментарий').fill(message);
    await comments.getByLabel('@Упоминания').fill('Synthetic member');
    await comments.getByRole('checkbox', {name: /Synthetic member/}).check();
    const sent = page.waitForResponse(r => r.url().includes('/comments/') && r.request().method() === 'POST');
    await comments.getByRole('button', {name: 'Отправить', exact: true}).click();
    const response = await sent; expect(response.status()).toBe(201);
    expect((await response.json()).mentions).toContain(fixture.member_id);
    await expect(comments.getByText(message, {exact: true})).toBeVisible();
    expect(await page.evaluate(() => document.documentElement.scrollWidth <= innerWidth)).toBeTruthy();
  });

  test(`requests creation is closed and project tasks hide priority at ${width}px`, async ({page}) => {
    await page.setViewportSize({width, height: 900});
    await page.goto('/requests/new');
    await expect(page.getByRole('heading', {name: 'Новые обращения оформляются задачами'})).toBeVisible();
    await page.goto(`/projects/${fixture.project_id}`);
    await page.getByRole('button', {name: '+ Добавить задачу', exact: true}).first().click();
    await expect(page.getByLabel('Ответственное подразделение *')).toBeVisible();
    await expect(page.getByRole('combobox', {name: /^Приоритет/})).toHaveCount(0);
  });
}
