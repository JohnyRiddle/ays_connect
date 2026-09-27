import { test, expect } from '@playwright/test';
import { readFileSync } from 'node:fs';

const fixture = JSON.parse(readFileSync('/private/projects-fixture.json', 'utf8'));

test('Cards seasons and iiko shell remain available without external integration calls', async ({ page }) => {
  const unexpectedExternal: string[] = [];
  page.on('request', request => {
    const url = new URL(request.url());
    if (!['proxy', 'localhost'].includes(url.hostname)) unexpectedExternal.push(url.hostname);
  });

  const manager = fixture.actors.manager;
  await page.goto('/');
  await page.getByLabel('Электронная почта').fill(manager.email);
  await page.getByLabel('Пароль', { exact: true }).fill(manager.password);
  await page.getByRole('button', { name: 'Войти', exact: true }).click();

  await expect(page.getByRole('link', { name: 'Карты', exact: true })).toBeVisible();
  await page.goto('/cards-dashboard');
  await expect(page.getByRole('heading', { name: 'Карты iiko: оформление и использование' })).toBeVisible();
  await expect(page.getByRole('tab', { name: 'Сезон 2027' })).toHaveAttribute('aria-selected', 'true');
  await page.getByRole('tab', { name: 'Сезон 25-26' }).click();
  await expect(page.getByRole('tab', { name: 'Сезон 25-26' })).toHaveAttribute('aria-selected', 'true');
  await expect(page.getByRole('heading', { name: 'Карты персонала и бонусные программы' })).toBeVisible();

  await expect(page.getByRole('link', { name: 'Оформление iikoCard' })).toBeVisible();
  await page.goto('/iiko-cards');
  await expect(page.getByRole('heading', { name: 'Карты сотрудников' })).toBeVisible();
  await expect(page.getByRole('tab', { name: 'Создание карты' })).toBeVisible();
  await expect(page.getByRole('tab', { name: 'Проверка карты' })).toBeVisible();
  await expect(page.getByText(/Загрузить справочники|Загружаем справочники/)).toBeVisible();
  expect(unexpectedExternal).toEqual([]);
});
