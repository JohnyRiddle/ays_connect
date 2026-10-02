import { test, expect } from '@playwright/test';
import { readFileSync } from 'node:fs';
const fixture=JSON.parse(readFileSync('/private/projects-fixture.json','utf8'));
async function auth(request:any, actor:any){const response=await request.post('/api/v1/auth/login/',{data:{email:actor.email,password:actor.password}});expect(response.status()).toBe(200);return response.json();}
async function session(page:any,tokens:any){await page.addInitScript((value:any)=>{sessionStorage.setItem('access',value.access);sessionStorage.setItem('refresh',value.refresh)},tokens);}

test('Work task header follows lifecycle, permissions and accessible actions menu',async({page,request})=>{
  const manager=fixture.actors.manager, executor=fixture.actors.executor;
  const managerAuth=await auth(request,manager); const mh={Authorization:`Bearer ${managerAuth.access}`};
  const blockedCreated=await request.post('/api/internal/v1/tasks/',{headers:mh,data:{title:'Синтетическая задача без ответственного'}});
  expect(blockedCreated.status()).toBe(201); const blockedTask=await blockedCreated.json();
  await session(page,managerAuth); await page.goto(`/tasks/${blockedTask.id}`);
  await expect(page.getByRole('button',{name:'Опубликовать',exact:true})).toBeDisabled();
  await expect(page.getByText('Для публикации укажите ответственного.')).toBeVisible();
  const created=await request.post('/api/internal/v1/tasks/',{headers:mh,data:{title:'Синтетическая проверка действий Work',description:'Только изолированный staging',responsible_target:fixture.executor_target,executor_target:fixture.executor_target,acceptance_policy:'author'}});
  expect(created.status()).toBe(201); let task=await created.json();
  await session(page,managerAuth); await page.goto(`/tasks/${task.id}`); await page.setViewportSize({width:1440,height:900});
  await expect(page.getByRole('button',{name:'Опубликовать',exact:true})).toBeVisible();
  await expect(page.getByRole('button',{name:'Действия',exact:false})).toBeVisible();
  await page.getByRole('button',{name:'Действия',exact:false}).focus(); await page.keyboard.press('Enter');
  await expect(page.getByRole('menuitem',{name:'Отменить'})).toBeVisible();
  await expect(page.getByRole('menuitem',{name:'Опубликовать'})).toHaveCount(0);
  await page.screenshot({path:'/artifacts/work-actions-draft-menu.png',fullPage:true});
  await page.keyboard.press('Escape'); await expect(page.getByRole('button',{name:'Действия',exact:false})).toBeFocused();
  await page.keyboard.press('Space'); await expect(page.getByRole('menu')).toBeVisible(); await page.keyboard.press('Escape');
  await page.setViewportSize({width:390,height:844}); await page.getByRole('button',{name:'Действия',exact:false}).click(); await expect(page.getByRole('menu')).toBeVisible();
  await page.locator('.work-card').first().click(); await expect(page.getByRole('menu')).toHaveCount(0); await expect(page.getByRole('button',{name:'Действия',exact:false})).toBeFocused();
  await page.setViewportSize({width:1440,height:900});
  await page.screenshot({path:'/artifacts/work-actions-draft.png',fullPage:true});
  await page.getByRole('button',{name:'Опубликовать',exact:true}).click();
  const executorAuth=await auth(request,executor); await page.evaluate(()=>sessionStorage.clear()); await session(page,executorAuth); await page.reload();
  await page.getByRole('button',{name:'Начать работу',exact:true}).click();
  await expect(page.locator('.work-status')).toHaveText('В работе');
  await expect(page.getByRole('button',{name:'Выполнить',exact:true})).toBeVisible();
  await page.screenshot({path:'/artifacts/work-actions-in-progress.png',fullPage:true});
  await page.getByRole('button',{name:'Выполнить',exact:true}).click();
  const dialog=page.getByRole('dialog'); await expect(dialog.getByText(/обязательную приёмку/)).toBeVisible();
  await dialog.getByLabel('Результат выполнения').fill('Синтетический результат');
  await page.route('**/api/internal/v1/tasks/*/complete/',route=>route.fulfill({status:500,contentType:'application/json',body:JSON.stringify({detail:'Синтетическая ошибка'})}),{times:1});
  await dialog.getByRole('button',{name:'Подтвердить'}).click(); await expect(dialog.getByLabel('Результат выполнения')).toHaveValue('Синтетический результат');
  await dialog.getByRole('button',{name:'Подтвердить'}).click(); await expect(page.locator('.work-status')).toHaveText('На приёмке');
  await page.evaluate(()=>sessionStorage.clear()); await session(page,managerAuth); await page.reload();
  await expect(page.getByRole('button',{name:'Принять',exact:true})).toBeVisible();
  await expect(page.getByRole('button',{name:'Выполнить',exact:true})).toHaveCount(0);
  await page.screenshot({path:'/artifacts/work-actions-review.png',fullPage:true});
  const outsiderAuth=await auth(request,fixture.actors.outsider); await page.evaluate(()=>sessionStorage.clear()); await session(page,outsiderAuth); await page.reload();
  await expect(page.getByText(/Недостаточно прав|недоступен|не найден/)).toBeVisible();
});
