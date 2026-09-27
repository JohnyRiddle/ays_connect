import { test, expect } from '@playwright/test';
import { readFileSync } from 'node:fs';

const fixture = JSON.parse(readFileSync('/private/projects-fixture.json','utf8'));

test('manager creates project, stage, Work task, links existing task and completes acceptance', async ({page,request}) => {
  const errors:string[]=[];
  page.on('pageerror', () => errors.push('page_error'));
  page.on('request', request => { if (/fonts\.(googleapis|gstatic)\.com/.test(request.url())) errors.push('external_font'); });
  const manager=fixture.actors.manager,executor=fixture.actors.executor;
  const login=await request.post('/api/v1/auth/login/',{data:{email:manager.email,password:manager.password}});
  expect(login.status()).toBe(200);
  const headers={Authorization:`Bearer ${(await login.json()).access}`};
  const existingTitle=`Synthetic existing Work task ${Date.now()}`;
  const existingResponse=await request.post('/api/internal/v1/tasks/',{headers,data:{title:existingTitle,
    responsible_target:fixture.executor_target,executor_target:fixture.executor_target,acceptance_policy:'author'}});
  expect(existingResponse.status()).toBe(201);
  const existingTask=await existingResponse.json();
  await page.goto('/');
  await page.getByLabel('Электронная почта').fill(manager.email);
  await page.getByLabel('Пароль',{exact:true}).fill(manager.password);
  await page.getByRole('button',{name:'Войти',exact:true}).click();
  await expect(page.getByRole('link',{name:'Проекты'})).toBeVisible();
  await page.getByRole('link',{name:'Проекты'}).click();
  await expect(page.getByRole('heading',{name:'Проекты'})).toBeVisible();
  await page.getByLabel('Название нового проекта').fill('Synthetic browser project');
  await page.getByLabel('Руководитель проекта').selectOption(manager.employee);
  await page.getByRole('button',{name:'Создать проект'}).click();
  await expect(page.getByRole('heading',{name:'Synthetic browser project'})).toBeVisible();
  const projectPath=new URL(page.url()).pathname;
  await page.getByLabel('Название этапа').fill('Synthetic browser stage');
  await page.getByRole('button',{name:'Добавить'}).first().click();
  await expect(page.locator('.project-row').filter({hasText:'Synthetic browser stage'}).first()).toBeVisible();
  await page.getByLabel('Название проектной задачи').fill('Synthetic browser Work task');
  await page.getByLabel('Этап новой задачи').selectOption({label:'Synthetic browser stage'});
  await page.getByLabel('Ответственный новой задачи').selectOption(fixture.executor_target);
  await page.getByLabel('Исполнитель новой задачи').selectOption(fixture.executor_target);
  await page.getByLabel('Приёмка новой задачи').selectOption('author');
  await page.getByRole('button',{name:'Создать задачу'}).click();
  await expect(page.getByText('Synthetic browser Work task').first()).toBeVisible();
  await page.getByLabel('Поиск задачи для привязки').fill(existingTitle);
  await expect(page.getByLabel('Выбранная задача').locator('option')).toHaveCount(2);
  await page.getByLabel('Выбранная задача').selectOption(existingTask.id);
  await page.getByRole('button',{name:'Привязать'}).click();
  await expect(page.getByText(existingTitle).first()).toBeVisible();
  await page.getByRole('button',{name:'Доска'}).click();
  await page.locator('.project-board .project-task').filter({hasText:'Synthetic browser Work task'}).dragTo(
    page.locator('.project-board > div').filter({has:page.getByRole('heading',{name:'Открыта'})}).getByRole('heading',{name:'Открыта'}));
  await expect(page.locator('.project-board > div').filter({has:page.getByRole('heading',{name:'Открыта'})})
    .getByText('Synthetic browser Work task')).toBeVisible();
  await page.getByRole('button',{name:'Начать',exact:true}).first().click();
  const taskPage=await request.get(`/api/internal/v1${projectPath}/tasks/`,{headers});
  expect(taskPage.status()).toBe(200);
  const taskRows=(await taskPage.json()).results;
  const ids=['Synthetic browser Work task',existingTitle].map(title=>taskRows.find((x:any)=>x.title===title)?.id);
  expect(ids.every(Boolean)).toBe(true);
  for(const title of ['Synthetic browser Work task',existingTitle]) {
    await page.locator('.project-task').filter({hasText:title}).first().locator('strong').click();
    await expect(page.getByRole('button',{name:/Проект PRJ-/})).toBeVisible();
    if(title===existingTitle) await page.locator('.work-actions').getByRole('button',{name:'Опубликовать',exact:true}).click();
    await expect(page.locator('.work-detail-head .work-status')).toHaveText('Открыта');
    await page.getByRole('button',{name:/Проект PRJ-/}).click();
  }
  await page.getByRole('button',{name:'Выйти'}).click();
  await page.getByLabel('Электронная почта').fill(executor.email);
  await page.getByLabel('Пароль',{exact:true}).fill(executor.password);
  await page.getByRole('button',{name:'Войти',exact:true}).click();
  await expect(page.getByRole('link',{name:'Задачи'})).toBeVisible();
  for(const id of ids) {
    await page.goto(`/tasks/${id}`);
    await page.locator('.work-actions').getByRole('button',{name:'Начать',exact:true}).click();
    await page.locator('.work-actions').getByRole('button',{name:'Завершить',exact:true}).click();
    await expect(page.locator('.work-detail-head .work-status')).toHaveText('На проверке');
  }
  await page.getByRole('button',{name:'Выйти'}).click();
  await page.getByLabel('Электронная почта').fill(manager.email);
  await page.getByLabel('Пароль',{exact:true}).fill(manager.password);
  await page.getByRole('button',{name:'Войти',exact:true}).click();
  await expect(page.getByRole('link',{name:'Проекты'})).toBeVisible();
  for(const id of ids) {
    await page.goto(`/tasks/${id}`);
    await page.locator('.work-actions').getByRole('button',{name:'Принять',exact:true}).click();
    await expect(page.locator('.work-detail-head .work-status')).toHaveText('Завершена');
  }
  await page.goto(projectPath);
  await expect(page.getByText('100%').first()).toBeVisible();
  await page.getByRole('button',{name:'Завершить',exact:true}).first().click();
  await expect(page.getByText(/Завершён/).first()).toBeVisible();
  expect(errors).toEqual([]);
});

test('employee without project access sees no project data', async ({page}) => {
  const outsider=fixture.actors.outsider;
  await page.goto('/');
  await page.getByLabel('Электронная почта').fill(outsider.email);
  await page.getByLabel('Пароль',{exact:true}).fill(outsider.password);
  await page.getByRole('button',{name:'Войти',exact:true}).click();
  await expect(page.getByRole('link',{name:'Проекты'})).toBeVisible();
  await page.goto('/projects');
  await expect(page.getByText('Доступных проектов пока нет.')).toBeVisible();
  await expect(page.getByText('Synthetic browser project')).toHaveCount(0);
});
