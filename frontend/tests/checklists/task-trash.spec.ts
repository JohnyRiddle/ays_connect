import {test,expect,Page} from '@playwright/test';

for (const width of [1280, 390]) for (const theme of ['light', 'dark']) {
  test(`secondary trash filter: keyboard, label and pagination at ${width} ${theme}`, async ({page}) => {
    await setup(page);
    await page.setViewportSize({width, height: 950});
    await page.addInitScript(theme => localStorage.setItem('ays-connect-theme', theme), theme);
    const queries: URLSearchParams[] = [];
    await page.route('**/api/internal/v1/tasks/?*', route => {
      const query = new URL(route.request().url()).searchParams;
      queries.push(query);
      return route.fulfill({json: {count: 21, next: 'next', previous: query.get('page') === '2' ? 'previous' : null,
        results: [{id, number: 'TASK-99', title: query.has('deleted') ? 'Удалённая тестовая задача' : 'Активная тестовая задача', status: 'in_progress', priority: 'normal'}]}});
    });
    await page.goto('/tasks');
    await expect(page.getByText('Активная тестовая задача', {exact: true})).toBeVisible();
    const checkbox = page.getByRole('checkbox', {name: 'Удалённые задачи', exact: true});
    await expect(checkbox).not.toBeChecked();
    await page.getByRole('button', {name: 'Далее', exact: true}).click();
    await expect.poll(() => queries.at(-1)?.get('page')).toBe('2');
    await page.getByLabel('Сортировка', {exact: true}).focus();
    await page.keyboard.press('Tab');
    await expect(checkbox).toBeFocused();
    await expect(checkbox).toHaveCSS('outline-style', 'solid');
    await expect(checkbox).toHaveCSS('outline-width', '2px');
    await page.keyboard.press('Space');
    await expect(checkbox).toBeChecked();
    await expect(page.getByText('Удалённая тестовая задача', {exact: true})).toBeVisible();
    expect(queries.at(-1)?.get('deleted')).toBe('true');
    expect(queries.at(-1)?.get('page')).toBe('1');
    const box = (await checkbox.boundingBox())!;
    expect(box.width).toBeLessThanOrEqual(20);
    expect(box.height).toBeLessThanOrEqual(20);
    const label = page.locator('label').filter({has: checkbox});
    expect((await label.boundingBox())!.height).toBeGreaterThanOrEqual(44);
    expect(await page.evaluate(() => document.documentElement.scrollWidth <= innerWidth)).toBeTruthy();
    await page.screenshot({path: `test-results/checklists/trash-filter-${width}-${theme}.png`, fullPage: true});
    await label.click();
    await expect(checkbox).not.toBeChecked();
    await expect(page.getByText('Активная тестовая задача', {exact: true})).toBeVisible();
    expect(queries.at(-1)?.has('deleted')).toBe(false);
  });
}

const id='00000000-0000-4000-8000-000000000099';
async function setup(page:Page, allowed=true, status='in_progress', project=false) {
  const writes:string[]=[];
  let task:any={id,number:'TASK-99',title:'Синтетическая удаляемая задача',status,priority:'normal',version:1,deleted_at:null,available_actions:allowed?['trash']:[],checklist_progress:{total:0,completed:0}};
  if(project)task.project={id:'project-1',number:'PRJ-1',stage_id:'stage-1',version:4,planned_end_at:'2026-11-01T12:00:00Z'};
  await page.addInitScript(()=>sessionStorage.setItem('access','synthetic-trash'));
  await page.route('**/api/**',async route=>{
    const req=route.request(),p=new URL(req.url()).pathname;
    let data:any={count:0,results:[]};
    if(p.endsWith('/auth/me/')) data={id:1,full_name:'Synthetic',roles:[],employee:null};
    else if(p.endsWith(`/tasks/${id}/trash/`)||p.endsWith(`/tasks/${id}/restore/`)) {
      writes.push(p);expect(req.postDataJSON().version).toBe(task.version);
      if(project){expect(req.postDataJSON().project_version).toBe(task.project.version);task.project={...task.project,version:task.project.version+1};}
      const deleted=p.endsWith('/trash/');task={...task,version:task.version+1,deleted_at:deleted?'2026-10-19T00:00:00Z':null,available_actions:[deleted?'restore':'trash']};data=task;
    } else if(p.endsWith(`/tasks/${id}/`))data=task;
    else if(['/comments/','/attachments/','/checklists/','/watchers/','/approvals/'].some(x=>p.endsWith(x))) data=[];
    await route.fulfill({json:data});
  });return writes;
}
for(const width of [1280,390])test(`confirm, cancel, trash and restore at ${width}`,async({page})=>{
  const writes=await setup(page);await page.setViewportSize({width,height:950});await page.goto(`/tasks/${id}`);
  await page.getByRole('button',{name:'Действия',exact:false}).click();await page.getByRole('menuitem',{name:'Удалить задачу'}).click();
  await expect(page.getByText('Обсуждения, вложения и история сохранятся.',{exact:false})).toBeVisible();
  await expect(page.getByText('Сроки не сдвигаются',{exact:false})).toBeVisible();
  await page.screenshot({path:`test-results/checklists/active-trash-confirm-${width}.png`,fullPage:true});
  await page.getByRole('button',{name:'Отмена',exact:true}).click();expect(writes).toHaveLength(0);
  await page.getByRole('button',{name:'Действия',exact:false}).click();await page.getByRole('menuitem',{name:'Удалить задачу'}).click();await page.getByRole('button',{name:'Подтвердить',exact:true}).click();
  await expect(page.getByText('Задача удалена.',{exact:false})).toBeVisible();expect(writes).toHaveLength(1);
  await page.getByRole('button',{name:'Действия',exact:false}).click();await page.getByRole('menuitem',{name:'Восстановить задачу'}).click();await page.getByRole('button',{name:'Подтвердить',exact:true}).click();
  await expect(page.getByText('Задача удалена.',{exact:false})).toHaveCount(0);expect(writes).toHaveLength(2);
  expect(await page.evaluate(()=>document.documentElement.scrollWidth<=innerWidth)).toBeTruthy();
});
for(const width of [1280,390])test(`project links and current deadline restore confirmation at ${width}`,async({page})=>{
  const writes=await setup(page,true,'in_progress',true);await page.setViewportSize({width,height:950});await page.goto(`/tasks/${id}`);
  await page.getByRole('button',{name:'Действия',exact:false}).click();await page.getByRole('menuitem',{name:'Удалить задачу'}).click();await page.getByRole('button',{name:'Подтвердить',exact:true}).click();
  await expect(page.getByText('Задача удалена.',{exact:false})).toBeVisible();
  await page.getByRole('button',{name:'Действия',exact:false}).click();await page.getByRole('menuitem',{name:'Восстановить задачу'}).click();
  await expect(page.getByText('Наследуемый срок будет взят из текущего проекта:',{exact:false})).toBeVisible();
  await page.getByRole('button',{name:'Подтвердить',exact:true}).click();await expect(page.getByText('Задача удалена.',{exact:false})).toHaveCount(0);expect(writes).toHaveLength(2);
});
test('viewer has no delete action',async({page})=>{await setup(page,false);await page.goto(`/tasks/${id}`);await expect(page.getByRole('heading',{name:'Синтетическая удаляемая задача'})).toBeVisible();await expect(page.getByRole('button',{name:'Действия',exact:false})).toHaveCount(0)});
for(const status of ['draft','open','waiting','review'])test(`active ${status} task can enter trash`,async({page})=>{
  const writes=await setup(page,true,status);await page.goto(`/tasks/${id}`);
  await page.getByRole('button',{name:'Действия',exact:false}).click();await page.getByRole('menuitem',{name:'Удалить задачу'}).click();
  await page.getByRole('button',{name:'Подтвердить',exact:true}).click();
  await expect(page.getByText('Задача удалена.',{exact:false})).toBeVisible();expect(writes).toHaveLength(1);
});
