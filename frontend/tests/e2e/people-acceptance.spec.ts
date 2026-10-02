import { test, expect } from '@playwright/test';
import { readFileSync } from 'node:fs';
import { randomBytes } from 'node:crypto';
const run = process.env.PEOPLE_RUN || 'gate01';
if (!/^[a-z0-9]{1,12}$/.test(run)) throw new Error('Invalid synthetic run');
const fixture = JSON.parse(readFileSync(`/private/${run}.json`, 'utf8'));

test.beforeEach(async ({page}) => {
  page.on('request', request => {
    if (/fonts\.(googleapis|gstatic)\.com/.test(request.url()))
      throw new Error('External font request is forbidden in isolated acceptance');
  });
});

test('A-B desktop invitation activation login profile and refresh', async ({page, request}) => {
  const errors: string[] = [];
  page.on('pageerror', () => errors.push('browser_error'));
  const hr = fixture.actors.hr, employee = fixture.actors.employee;
  const logged = await request.post('/api/v1/auth/login/', {data: {email: hr.email, password: hr.password}});
  expect(logged.status()).toBe(200);
  const headers = {Authorization: `Bearer ${(await logged.json()).access}`};
  const invite = await request.post('/api/internal/v1/people/invitations/', {headers, data: {employee: employee.employee}});
  expect(invite.status()).toBe(201);
  const raw = (await invite.json()).activation_token;
  // Fragment never reaches the HTTP server; traces/screenshots are disabled.
  await page.goto(`/activate/continue#token=${encodeURIComponent(raw)}`);
  await page.getByLabel('Пароль', {exact: true}).fill(employee.password);
  await page.getByLabel('Повторите пароль').fill(employee.password);
  await page.getByRole('button', {name: 'Активировать аккаунт'}).click();
  await expect(page.getByRole('heading', {name:'Аккаунт активирован'})).toBeVisible();
  await page.getByRole('link', {name:'Войти в AYS Connect'}).click();
  await page.getByLabel('Электронная почта').fill(employee.email);
  await page.getByLabel('Пароль', {exact:true}).fill(employee.password);
  await page.getByRole('button', {name:'Войти', exact:true}).click();
  await expect(page.getByRole('link', {name:'Мой онбординг', exact:true})).toBeVisible();
  await page.goto('/people/me');
  await expect(page.getByRole('heading', {name:'Мой профиль', exact:true})).toBeVisible();
  await expect(page.locator('input, textarea, select')).toHaveCount(0);
  await page.goto('/people/me/edit');
  await expect(page.getByRole('heading', {name:'Редактировать профиль', exact:true})).toBeVisible();
  await page.locator('[name=preferred_name]').fill('Synthetic Browser');
  await page.locator('[name=bio]').fill('Synthetic profile acceptance');
  await page.getByRole('button', {name:/Сохранить/}).click();
  await page.reload();
  await expect(page.getByText('Synthetic Browser', {exact:true}).first()).toBeVisible();
  expect(errors.length).toBe(0);
});

test('B desktop and mobile first-login and onboarding views', async ({page}) => {
  const employee = fixture.actors.employee;
  await page.goto('/');
  await page.getByLabel('Электронная почта').fill(employee.email);
  await page.getByLabel('Пароль', {exact:true}).fill(employee.password);
  await page.getByRole('button', {name:'Войти', exact:true}).click();
  await expect(page.getByRole('link', {name:'Мой онбординг', exact:true})).toBeVisible();
  for (const width of [1440, 390]) {
    await page.setViewportSize({width, height:900});
    await page.goto('/people/first-login');
    await expect(page.getByRole('heading',{name:'Настройка рабочего профиля'})).toBeVisible();
    await page.goto('/people/me/onboarding');
    await expect(page.getByRole('heading',{name:'Мой онбординг'})).toBeVisible();
    expect(await page.evaluate(() => document.documentElement.scrollWidth <= innerWidth + 1)).toBe(true);
  }
});

test('D-E real frontend first-login onboarding steps and accepted Work task', async ({page, request}, testInfo) => {
  const errors: string[] = [];
  page.on('pageerror', () => errors.push('page_error'));
  page.on('console', message => { if(message.type()==='error') {
    errors.push('console_error');
    const text=message.text();
    const category=text.match(/ERR_[A-Z_]+|Minified React error #\d+|Content Security Policy|unique.*key/)?.[0] || 'resource_error';
    const url=message.location().url;
    testInfo.annotations.push({type:'safe_console_class',description:category+' '+(url?new URL(url).hostname:'no-host')});
  }});
  page.on('response', response => {
    if(response.status()>=400) {
      const path=new URL(response.url()).pathname.replace(/[0-9a-f]{8}-[0-9a-f-]{27,}/gi,'{id}');
      if(/^\/api\/(internal\/)?v1\/[a-z0-9/{}-]+$/i.test(path))
        testInfo.annotations.push({type:'safe_http_failure',description:`${response.status()} ${path}`});
    }
  });
  const employee=fixture.actors.employee, coordinator=fixture.actors.coordinator;
  const login=await request.post('/api/v1/auth/login/',{data:{email:coordinator.email,password:coordinator.password}});
  expect(login.status()).toBe(200);
  const headers={Authorization:`Bearer ${(await login.json()).access}`};
  const assigned=await request.post('/api/internal/v1/people/onboarding/',{headers,data:{employee:employee.employee}});
  expect(assigned.status()).toBe(201);
  const instance=await assigned.json();
  await page.goto('/');
  await page.getByLabel('Электронная почта').fill(employee.email);
  await page.getByLabel('Пароль',{exact:true}).fill(employee.password);
  await page.getByRole('button',{name:'Войти',exact:true}).click();
  await expect(page.getByRole('link',{name:'Мой онбординг',exact:true})).toBeVisible();
  await page.goto('/people/first-login');
  for(const title of ['Проверьте профиль','Подтвердите часовой пояс','Настройте видимость']) {
    const row=page.locator('article').filter({hasText:title});
    await row.getByRole('button',{name:'Выполнить'}).click();
    await expect(row.getByText('Завершено',{exact:true})).toBeVisible();
  }
  await page.reload();
  await page.getByRole('button',{name:'Перейти к онбордингу'}).click();
  for(const title of ['Профиль сотрудника','Первый рабочий шаг']) {
    const row=page.locator('article').filter({hasText:title});
    await row.getByRole('button',{name:'Начать',exact:true}).click();
    await row.getByRole('button',{name:'Завершить',exact:true}).click();
    await expect(row.getByText('completed',{exact:true})).toBeVisible();
  }
  const step=instance.steps.find((x:any)=>x.title_snapshot==='Рабочая задача');
  const created=await request.post(`/api/internal/v1/people/onboarding/${instance.id}/steps/${step.id}/create-task/`,{headers,data:{}});
  expect(created.status()).toBe(200);
  const taskId=(await created.json()).task_id;
  const taskPath=`/api/internal/v1/tasks/${taskId}/`;
  const task=await (await request.get(taskPath,{headers})).json();
  expect((await request.post(taskPath+'publish/',{headers,data:{version:task.version}})).status()).toBe(200);
  await page.reload();
  await page.getByRole('link',{name:'Открыть задачу'}).click();
  await expect(page).toHaveURL(new RegExp(`/tasks/${taskId}$`));
  for(const action of ['Начать','Завершить','Принять']) {
    await page.locator('.work-actions').getByRole('button',{name:action,exact:true}).click();
  }
  await expect(page.locator('.work-detail-head .work-status')).toHaveText('Завершена');
  await page.setViewportSize({width:390,height:900});
  await page.reload();
  expect(await page.evaluate(()=>document.documentElement.scrollWidth<=innerWidth+1)).toBe(true);
  await page.goto('/people/me/onboarding');
  // Reconciliation runs in bounded worker batches with a 3-second cycle.
  // Allow several cycles while retaining the exact completed-state assertion.
  await expect.poll(async()=>{
    await page.reload();
    return page.locator('article').filter({hasText:'Рабочая задача'}).locator('.badge').innerText();
  }, {timeout: 15_000}).toBe('completed');
  expect(errors).toEqual([]);
});

test('A registration frontend and controlled API error UI', async ({page}) => {
  await page.goto('/register');
  await page.getByLabel('ФИО').fill('Synthetic Browser Applicant');
  await page.getByLabel('Рабочая электронная почта').fill(`applicant-${run}@example.test`);
  await page.route('**/api/public/v1/register/',route=>route.fulfill({status:503,contentType:'application/json',body:JSON.stringify({detail:'Synthetic unavailable'})}));
  await page.getByRole('button',{name:'Отправить заявку'}).click();
  await expect(page.getByText('Synthetic unavailable')).toBeVisible();
  await page.unroute('**/api/public/v1/register/');
  await page.getByRole('button',{name:'Отправить заявку'}).click();
  await expect(page.locator('.success-box')).toBeVisible();
});

test('H-I browser rehire preserves identity and never revives old JWT', async ({page, request}) => {
  test.setTimeout(180_000);
  // Keep the real 5/min login throttle. Respect Retry-After; never replace a
  // password/token rejection assertion with acceptance of a throttled response.
  const loginRequest=async (data:{email:string,password:string}) => {
    let response=await request.post('/api/v1/auth/login/',{data});
    if(response.status()===429) {
      const delay=Number(response.headers()['retry-after'] || '60');
      if(!Number.isFinite(delay) || delay<0 || delay>60) throw new Error('Unexpected login retry interval');
      await new Promise(resolve=>setTimeout(resolve,delay*1000+500));
      response=await request.post('/api/v1/auth/login/',{data});
    }
    return response;
  };
  const employee=fixture.actors.employee, hr=fixture.actors.hr;
  const login=await loginRequest({email:hr.email,password:hr.password});
  expect(login.status()).toBe(200);
  const headers={Authorization:`Bearer ${(await login.json()).access}`};
  const oldLogin=await loginRequest({email:employee.email,password:employee.password});
  expect(oldLogin.status()).toBe(200);
  const old=await oldLogin.json();
  const path=`/api/internal/v1/people/employees/${employee.employee}/`;
  const before=await (await request.get(path,{headers})).json();
  expect((await request.post(path+'terminate/',{headers,data:{}})).status()).toBe(200);
  expect((await request.post(path+'reactivate/',{headers,data:{}})).status()).toBe(200);
  const invite=await request.post('/api/internal/v1/people/invitations/',{headers,data:{employee:employee.employee}});
  expect(invite.status()).toBe(201);
  const raw=(await invite.json()).activation_token;
  const password=randomBytes(30).toString('base64url');
  await page.goto(`/activate/continue#token=${encodeURIComponent(raw)}`);
  await page.getByLabel('Пароль',{exact:true}).fill(password);
  await page.getByLabel('Повторите пароль').fill(password);
  await page.getByRole('button',{name:'Активировать аккаунт'}).click();
  await expect(page.getByRole('heading',{name:'Аккаунт активирован'})).toBeVisible();
  expect((await request.get('/api/v1/auth/me/',{headers:{Authorization:`Bearer ${old.access}`}})).status()).toBe(401);
  expect((await request.post('/api/v1/auth/refresh/',{data:{refresh:old.refresh}})).status()).toBe(401);
  expect((await loginRequest({email:employee.email,password:employee.password})).status()).toBe(401);
  await page.getByRole('link',{name:'Войти в AYS Connect'}).click();
  await page.getByLabel('Электронная почта').fill(employee.email);
  await page.getByLabel('Пароль',{exact:true}).fill(password);
  const submitLogin=async () => {
    const response=page.waitForResponse(r=>new URL(r.url()).pathname==='/api/v1/auth/login/' && r.request().method()==='POST');
    await page.getByRole('button',{name:'Войти',exact:true}).click();
    return await response;
  };
  let response=await submitLogin();
  if(response.status()===429) {
    const delay=Number(response.headers()['retry-after'] || '60');
    if(!Number.isFinite(delay) || delay<0 || delay>60) throw new Error('Unexpected login retry interval');
    await new Promise(resolve=>setTimeout(resolve,delay*1000+500));
    response=await submitLogin();
  }
  expect(response.status()).toBe(200);
  const after=await (await request.get(path,{headers})).json();
  expect(after.id).toBe(before.id);
  expect(after.employee_number).toBe(before.employee_number);
  expect(after.roles).toEqual([]);
});
