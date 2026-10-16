import {test,expect,Page} from '@playwright/test';
const taskId='00000000-0000-4000-8000-000000000003';
const item={id:'item-1',text:'Температура',position:1,required:true,section:'Кухня',help_text:'Измерьте температуру',answer_type:'number',options:[],min_value:0,max_value:10,answer:null,is_completed:false,version:1};
async function fixture(page:Page,manage=true,attached=false,watcherMode=false){
  let templates:any[]=[{id:'template-1',name:'Открытие кухни',description:'Ежедневная проверка',version:1,is_active:true,items:[{...item,answer_type:'checkbox',section:'',help_text:''}]}];
  let checklists:any[]=attached?[{id:'attached-1',name:'Проверка перед открытием',description:'Ежедневная проверка',items:[
    {...item,id:'saved',text:'Рабочее место подготовлено',answer_type:'checkbox',is_completed:true,answer:true,comment:'Всё готово',completed_at:'2026-10-14T09:00:00Z'},
    {...item,id:'boolean',text:'Оборудование исправно?',answer_type:'boolean'},
    {...item,id:'text',text:'Результат осмотра помещения и оборудования',answer_type:'text'},
    {...item},
    {...item,id:'single',text:'Состояние зала',answer_type:'single',options:['Готов','Требует уборки']},
    {...item,id:'multiple',text:'Проверенные зоны',answer_type:'multiple',options:['Кухня','Зал','Склад']},
  ]}]:[];
  let watchers:any[]=[{id:'watch-1',employee:'ivan',employee_display:'Ливеринов Иван'}];
  const candidates=[{id:'aks',name:'Аксёнов Александр',has_access:true},{id:'bez',name:'Бежаев Сергей',has_access:false},{id:'ivan',name:'Ливеринов Иван',has_access:true}];
  const task={id:taskId,number:'TASK-3',title:'Открытие объекта',description:'Проверка',status:'in_progress',version:1,priority:'normal',responsible_department_display:'Техническая служба',responsible_employee_display:'Аксёнов Александр',executor_employee_display:'Аксёнов Александр',available_actions:watcherMode?['watcher_manage']:manage?['checklist_manage','checklist_complete']:[],checklist_progress:{completed:0,total:0}};
  await page.addInitScript(()=>sessionStorage.setItem('access','synthetic-checklist-test'));
  await page.route('**/api/**',async route=>{
    const req=route.request(),p=new URL(req.url()).pathname;let data:any={count:0,results:[]};
    if(p.endsWith('/auth/me/'))data={id:1,full_name:'Тестовый сотрудник',email:'test@example.invalid',roles:[],employee:null};
    else if(p.endsWith('/employees/dashboard/')){await route.fulfill({status:503,json:{}});return;}
    else if(p.endsWith('/checklist-templates/capabilities/'))data={can_manage:manage,can_view:true};
    else if(p.endsWith('/checklist-templates/')){if(req.method()==='POST'){data={...req.postDataJSON(),id:'new-template',version:1};templates.push(data);}else data=templates;}
    else if(p.includes('/checklist-templates/')&&req.method()==='PATCH'){data={...req.postDataJSON(),id:p.split('/').at(-2),version:req.postDataJSON().version+1};templates=templates.map(t=>t.id===data.id?data:t);}
    else if(p.endsWith(`/tasks/${taskId}/`))data=task;
    else if(p.endsWith('/checklists/from-template/')){data={id:'attached-1',name:templates[0].name,description:templates[0].description,source_template_version:1,items:[{...item,answer_type:'checkbox',section:'',help_text:''}]};checklists.push(data);}
    else if(p.endsWith('/checklists/'))data=checklists;
    else if(p.endsWith('/items/item-1/complete/')){const body=req.postDataJSON();checklists[0].items[0]={...checklists[0].items[0],answer:body.answer,is_completed:true,version:2,completed_at:'2026-10-14T09:00:00Z'};task.checklist_progress={completed:1,total:1};data=checklists[0].items[0];}
    else if(p.endsWith('/items/item-1/uncomplete/')){checklists[0].items[0]={...checklists[0].items[0],answer:null,is_completed:false,version:3};data=checklists[0].items[0];}
    else if(p.endsWith('/participant-options/'))data={results:candidates.filter(c=>c.name.toLowerCase().includes((new URL(req.url()).searchParams.get('search')||'').toLowerCase()))};
    else if(p.endsWith('/watchers/')){if(req.method()==='POST'){const c=candidates.find(c=>c.id===req.postDataJSON().employee)!;watchers.push({id:'watch-'+c.id,employee:c.id,employee_display:c.name});}data=watcherMode?watchers:[];}
    else if(p.includes('/watchers/')&&req.method()==='DELETE'){watchers=watchers.filter(w=>!p.endsWith('/'+w.employee+'/'));data={};}
    else if(p.endsWith('/comments/')||p.endsWith('/attachments/'))data=[];
    else if(p.endsWith('/activity/'))data={results:[]};
    await route.fulfill({status:200,json:data});
  });
}
for(const width of [1280,390])test(`constructor, preview and saved template at ${width}px`,async({page})=>{
  await fixture(page);await page.setViewportSize({width,height:900});await page.goto('/checklists');
  await page.getByRole('button',{name:'Создать шаблон',exact:true}).click();
  await page.getByLabel('Название',{exact:true}).fill('Проверка зала');
  await expect(page.getByLabel('Тип ответа',{exact:true})).toHaveCount(0);
  await page.getByLabel('Название пункта 1',{exact:true}).fill('Оборудование исправно');
  await page.getByRole('button',{name:'Описание чек-листа',exact:true}).click();
  await page.getByLabel('Описание',{exact:true}).fill('Проверка перед открытием');
  await page.keyboard.press('Escape');
  await expect(page.getByLabel('Описание',{exact:true})).not.toBeVisible();
  await page.getByRole('button',{name:'Добавить пункт',exact:true}).click();
  await page.getByLabel('Название пункта 2',{exact:true}).fill('Зал подготовлен');
  await page.getByRole('button',{name:'Предпросмотр',exact:true}).click();
  await expect(page.getByRole('heading',{name:'Проверка зала',exact:true})).toBeVisible();
  await page.getByRole('checkbox',{name:'Оборудование исправно',exact:true}).check();
  await expect(page.getByText('Проверка перед открытием',{exact:true})).not.toBeVisible();
  await page.getByRole('button',{name:'Описание чек-листа',exact:true}).click();
  await expect(page.getByText('Проверка перед открытием',{exact:true})).toBeVisible();
  await page.keyboard.press('Escape');
  await page.getByRole('button',{name:'Редактор',exact:true}).click();
  const posted=page.waitForRequest(r=>r.url().endsWith('/checklist-templates/')&&r.method()==='POST');
  await page.getByRole('button',{name:'Сохранить шаблон',exact:true}).click();
  expect((await posted).postDataJSON().items).toHaveLength(2);
  await expect(page.getByRole('status')).toContainText('Шаблон сохранён');
  expect(await page.evaluate(()=>document.documentElement.scrollWidth<=innerWidth)).toBeTruthy();
  await page.screenshot({path:`${process.env.AYS_CHECKLIST_OUTPUT||'test-results/checklists'}/builder-${width}.png`,fullPage:true});
});
test('checkbox attaches and saves immediately with item version',async({page})=>{
  await fixture(page);await page.goto(`/tasks/${taskId}`);
  await page.locator('.cb-attach summary').click();
  await page.getByLabel('Шаблон',{exact:true}).selectOption('template-1');await page.getByRole('button',{name:'Прикрепить чек-лист',exact:true}).click();
  await expect(page.getByRole('heading',{name:'Кухня',exact:true})).toHaveCount(0);
  const posted=page.waitForRequest(r=>r.url().endsWith('/items/item-1/complete/'));
  await page.getByRole('checkbox',{name:'Температура',exact:true}).check();
  expect((await posted).postDataJSON()).toMatchObject({answer:true,version:1});
  await expect(page.getByRole('checkbox',{name:'Температура',exact:true})).toBeChecked();
  await expect(page.getByRole('button',{name:'Сохранить ответ',exact:true})).toHaveCount(0);
  const undone=page.waitForRequest(r=>r.url().endsWith('/items/item-1/uncomplete/'));
  await page.getByRole('checkbox',{name:'Температура',exact:true}).uncheck();
  expect((await undone).postDataJSON()).toMatchObject({version:2});
  await expect(page.getByRole('checkbox',{name:'Температура',exact:true})).not.toBeChecked();
});
test('viewer can preview but cannot edit or create templates',async({page})=>{
  await fixture(page,false);await page.goto('/checklists');
  await page.getByRole('button',{name:'Посмотреть',exact:true}).click();
  await expect(page.getByRole('heading',{name:'Открытие кухни',exact:true})).toBeVisible();
  await expect(page.getByRole('button',{name:'Сохранить шаблон',exact:true})).toHaveCount(0);
  await expect(page.getByRole('button',{name:'Создать шаблон',exact:true})).toHaveCount(0);
});

for(const width of [1280,390])test(`task checklist layout and comments at ${width}px`,async({page})=>{
  await fixture(page,true,true);await page.setViewportSize({width,height:1000});await page.goto(`/tasks/${taskId}`);
  const panel=page.locator('.cb-task-panel');
  await expect(panel.getByRole('heading',{name:'Чек-листы',exact:true})).toBeVisible();
  await expect(panel.getByRole('checkbox',{name:'Рабочее место подготовлено'})).toBeChecked();
  await expect(panel.getByText('Обязательный',{exact:true})).toHaveCount(0);
  await expect(panel.getByText('Измерьте температуру',{exact:true})).toHaveCount(0);
  await expect(panel.getByLabel('Комментарий',{exact:true})).toHaveCount(0);
  await expect(panel.getByText('Ежедневная проверка',{exact:true})).not.toBeVisible();
  await panel.getByRole('button',{name:'Описание чек-листа',exact:true}).click();
  await expect(panel.getByText('Ежедневная проверка',{exact:true})).toBeVisible();
  await page.keyboard.press('Escape');
  await expect(panel.getByText('Ежедневная проверка',{exact:true})).not.toBeVisible();
  // Previously saved typed answers remain usable, without conversion or data loss.
  await panel.getByLabel('Ответ: Температура',{exact:true}).fill('0');
  expect(await page.evaluate(()=>document.documentElement.scrollWidth<=innerWidth)).toBeTruthy();
  for(const theme of ['light','dark']){
    await page.evaluate(value=>document.documentElement.setAttribute('data-theme',value),theme);
    expect(await page.evaluate(()=>document.documentElement.scrollWidth<=innerWidth)).toBeTruthy();
    await panel.screenshot({path:`test-results/checklists/task-layout-${width}-${theme}.png`});
  }
});

for(const width of [1280,390])test(`watcher search, sequential selection and safe removal at ${width}px`,async({page})=>{
  await fixture(page,true,false,true);await page.setViewportSize({width,height:1000});await page.goto(`/tasks/${taskId}`);
  const panel=page.locator('.task-watchers');const search=panel.getByRole('combobox',{name:'Добавить наблюдателя'});
  await expect(panel.getByRole('listbox')).toHaveCount(0);
  await search.fill('Ак');await expect(panel.getByRole('option',{name:'Аксёнов Александр',exact:true})).toBeVisible();
  await expect(panel.getByRole('option')).toHaveCount(1);
  await search.press('Escape');await expect(panel.getByRole('listbox')).toHaveCount(0);
  await search.press('ArrowDown');await search.press('Enter');
  await expect(panel.locator('.person-row').filter({hasText:'Аксёнов Александр'})).toBeVisible();
  await expect(search).toHaveValue('');
  await search.fill('Беж');await panel.getByRole('option',{name:'Бежаев Сергей'}).click();
  await expect(panel.locator('.person-row')).toHaveCount(3);
  await search.fill('Ак');await expect(panel.getByRole('option')).toHaveAttribute('aria-disabled','true');await expect(panel.getByText('Уже наблюдает')).toBeVisible();await search.press('ArrowDown');await search.press('Enter');await expect(panel.locator('.person-row')).toHaveCount(3);
  await search.fill('Несуществующий');await expect(panel.getByRole('status')).toHaveText('Сотрудники не найдены');
  await search.fill('');const row=panel.locator('.person-row').filter({hasText:'Ливеринов Иван'});
  let deleted=0;page.on('request',r=>{if(r.method()==='DELETE')deleted++;});
  await row.getByRole('button',{name:'Удалить',exact:true}).click();expect(deleted).toBe(0);
  await row.getByRole('button',{name:'Отмена',exact:true}).click();expect(deleted).toBe(0);
  await row.getByRole('button',{name:'Удалить',exact:true}).click();await row.getByRole('button',{name:'Да, удалить',exact:true}).click();
  await expect(panel.locator('.person-row')).toHaveCount(2);expect(deleted).toBe(1);
  await search.fill('Лив');await expect(panel.getByRole('option',{name:'Ливеринов Иван'})).toBeVisible();
  expect(await page.evaluate(()=>document.documentElement.scrollWidth<=innerWidth)).toBeTruthy();
  await page.locator('.task-sidebar').screenshot({path:`test-results/checklists/task-sidebar-${width}.png`});
});

for(const width of [1280,390])test(`empty checklist and chat mentions at ${width}px`,async({page})=>{
  await fixture(page,true,false,true);await page.setViewportSize({width,height:900});await page.goto(`/tasks/${taskId}`);
  await expect(page.getByRole('heading',{name:/Чек-листы/})).toHaveCount(0);
  await expect(page.getByText('@Упоминания',{exact:true})).toHaveCount(0);
  const chat=page.getByRole('textbox',{name:'Новый комментарий'});
  await chat.fill('Проверьте @Ак');
  await page.locator('.task-chat-mentions').getByRole('option',{name:'Аксёнов Александр'}).click();
  await expect(chat).toHaveValue('Проверьте @Аксёнов Александр ');
  const posted=page.waitForRequest(r=>r.url().endsWith('/comments/')&&r.method()==='POST');
  await page.getByRole('button',{name:'Отправить',exact:true}).click();
  expect((await posted).postDataJSON()).toMatchObject({mentions:['aks'],body:'Проверьте @Аксёнов Александр '});
  await chat.fill('@Лив');await page.locator('.task-chat-mentions').getByRole('option',{name:'Ливеринов Иван'}).waitFor();await page.screenshot({path:`test-results/checklists/task-chat-${width}.png`,fullPage:true});
});

test('raster attachment opens inside browser and can be downloaded separately',async({page})=>{
  await fixture(page,true,false,true);
  await page.route('**/tasks/*/attachments/',r=>r.fulfill({json:[{id:'photo',original_filename:'Проверка.png',content_type:'image/png',size:100}]}));
  await page.route('**/attachments/photo/download/',r=>r.fulfill({contentType:'image/png',body:Buffer.from('iVBORw0KGgoAAAANSUhEUgAAAAEAAAABCAQAAAC1HAwCAAAAC0lEQVR42mP8/x8AAwMCAO+jRZkAAAAASUVORK5CYII=','base64')}));
  await page.goto(`/tasks/${taskId}`);let downloads=0;page.on('download',()=>downloads++);
  await page.getByRole('button',{name:'Проверка.png',exact:true}).click();
  const modal=page.getByRole('dialog',{name:'Проверка.png'});await expect(modal).toBeVisible();
  await expect(modal.getByRole('img')).toBeVisible();expect(downloads).toBe(0);
  await modal.getByRole('button',{name:'Закрыть',exact:true}).press('Escape');await expect(modal).toHaveCount(0);
  const download=page.waitForEvent('download');await page.getByRole('button',{name:'Скачать',exact:true}).click();expect((await download).suggestedFilename()).toBe('Проверка.png');
});

test('nonblocking deadline preview uses server configuration, blocking remains explicit',async({page})=>{
  await fixture(page);
  await page.route('**/tasks/assignment-options/',r=>r.fulfill({json:{departments:[],priority_hours:{blocking:null,critical:2,high:24,normal:72,low:168}}}));
  await page.clock.setFixedTime(new Date('2026-10-15T08:00:00Z'));
  await page.goto('/tasks/new');const priority=page.getByRole('combobox',{name:'Приоритет',exact:true});
  for(const [key,hours] of [['critical',2],['high',24],['normal',72],['low',168]] as const){
    await priority.selectOption(key);const due=page.getByLabel('Срок рассчитывается по приоритету');await expect(due).toBeDisabled();
    const value=await due.inputValue();expect(new Date(value).getTime()).toBe(new Date('2026-10-15T08:00:00Z').getTime()+hours*3600000);
  }
  await priority.selectOption('blocking');await expect(page.getByLabel('Явный дедлайн *')).toBeEnabled();await expect(page.getByLabel('Явный дедлайн *')).toHaveValue('');
});

for(const width of [1280,390])test(`new mention popup without backlog or duplicate at ${width}px`,async({page})=>{
 await fixture(page,true,true);await page.setViewportSize({width,height:1000});
 let notifications:any[]=[{id:'old',title:'Старое упоминание',message:'Старое сообщение',is_mention:true,action_url:`/tasks/${taskId}`}];let calls=0;let reads=0;
 await page.route('**/api/v1/notifications/**',async route=>{if(route.request().method()==='POST'){reads++;await route.fulfill({json:{}});return;}calls++;await route.fulfill({json:{results:notifications}})});
 await page.goto(`/tasks/${taskId}`);await expect(page.getByRole('heading',{name:'Чат задачи',exact:true})).toBeVisible();await expect.poll(()=>calls).toBeGreaterThan(0);await expect(page.locator('.mention-toast')).toHaveCount(0);
 notifications=[{id:'new',title:'Новая задача',message:'Вас упомянули в обсуждении',is_mention:true,action_url:`/tasks/${taskId}`},...notifications];
 await page.evaluate(()=>window.dispatchEvent(new Event('focus')));const toast=page.locator('.mention-toast');await expect(toast).toHaveCount(1,{timeout:15000});await expect(toast.getByText('Вас упомянули в чате',{exact:true})).toBeVisible();
 expect(await page.evaluate(()=>document.documentElement.scrollWidth<=innerWidth)).toBeTruthy();await page.evaluate(()=>document.documentElement.setAttribute('data-theme','dark'));await toast.screenshot({path:`test-results/checklists/mention-toast-${width}.png`});
 await toast.getByRole('button',{name:'Закрыть уведомление об упоминании'}).click();expect(reads).toBe(0);await page.evaluate(()=>window.dispatchEvent(new Event('focus')));await expect(toast).toHaveCount(0);
 notifications=[{id:'newer',title:'Ещё одна задача',message:'Новое упоминание',is_mention:true,action_url:`/tasks/${taskId}`},...notifications];await page.evaluate(()=>window.dispatchEvent(new Event('focus')));await expect(toast).toHaveCount(1,{timeout:15000});await toast.getByRole('button',{name:'Открыть задачу'}).click();await expect.poll(()=>reads).toBe(1);
});

for(const width of [1280,390])test(`chat feed scroll and composer below messages at ${width}px`,async({page})=>{
 await fixture(page);await page.setViewportSize({width,height:1000});
 const messages=Array.from({length:40},(_,i)=>({id:`msg-${i}`,author:'employee',author_display:'Тестовый сотрудник',body:`Сообщение ${i+1}. Обсуждение рабочего вопроса.`,created_at:new Date(2026,9,16,10,i).toISOString(),mentions:[]}));
 await page.route(`**/tasks/${taskId}/comments/`,async route=>{if(route.request().method()==='POST'){const item={...messages[0],id:'own-new',body:route.request().postDataJSON().body};messages.push(item);await route.fulfill({json:item})}else await route.fulfill({json:messages})});
 await page.goto(`/tasks/${taskId}`);const feed=page.getByRole('log',{name:'Сообщения задачи'});await expect(feed.locator('article.comment')).toHaveCount(40);
 await expect(page.locator('.task-chat')).toHaveCSS('border-top-width','3px');await expect(page.locator('.task-files')).toHaveCSS('border-top-width','3px');
 await expect.poll(()=>feed.evaluate(e=>e.scrollHeight-e.clientHeight-e.scrollTop)).toBeLessThan(2);
 const input=page.getByRole('textbox',{name:'Новый комментарий'});const box=await feed.boundingBox();const composer=await input.boundingBox();expect(box&&composer&&composer.y>=box.y+box.height).toBeTruthy();
 await feed.evaluate(e=>{e.scrollTop=0;e.dispatchEvent(new Event('scroll',{bubbles:true}))});await input.fill('Новое сообщение исполнителя');await expect.poll(()=>feed.evaluate(e=>e.scrollTop)).toBe(0);
 await page.getByRole('button',{name:'Отправить',exact:true}).click();await expect(feed.locator('article.comment')).toHaveCount(41);await expect.poll(()=>feed.evaluate(e=>e.scrollHeight-e.clientHeight-e.scrollTop)).toBeLessThan(2);await expect(input).toHaveValue('');
 await page.setViewportSize({width,height:700});await expect.poll(()=>feed.evaluate(e=>e.scrollHeight-e.clientHeight-e.scrollTop)).toBeLessThan(2);
 expect(await page.evaluate(()=>document.documentElement.scrollWidth<=innerWidth)).toBeTruthy();await page.evaluate(()=>document.documentElement.setAttribute('data-theme','dark'));await page.locator('.task-chat').screenshot({path:`test-results/checklists/chat-feed-${width}.png`});
});


for(const width of [1280,390])test(`chat automatically refreshes without losing draft or scroll at ${width}px`,async({page})=>{
 await fixture(page);await page.setViewportSize({width,height:900});await page.clock.install();
 let messages=Array.from({length:40},(_,i)=>({id:`live-${i}`,author:'employee',author_display:'Коллега',body:`Переписка ${i}`,created_at:'2026-10-16T10:00:00Z',mentions:[]}));let fail=false,calls=0;
 await page.route(`**/tasks/${taskId}/comments/`,route=>{calls++;return fail?route.fulfill({status:503,json:{detail:'Unavailable'}}):route.fulfill({json:messages})});
 await page.goto(`/tasks/${taskId}`);const feed=page.getByRole('log',{name:'Сообщения задачи'});await expect(feed.locator('article.comment')).toHaveCount(40);
 const input=page.getByRole('textbox',{name:'Новый комментарий'});await input.fill('Мой несохранённый ответ');
 messages.push({...messages[0],id:'incoming',body:'Новое сообщение коллеги'});await page.clock.runFor(5100);await expect(feed.getByText('Новое сообщение коллеги',{exact:true})).toBeVisible();await expect(input).toHaveValue('Мой несохранённый ответ');await expect.poll(()=>feed.evaluate(e=>e.scrollHeight-e.clientHeight-e.scrollTop)).toBeLessThan(2);
 await feed.evaluate(e=>{e.scrollTop=0;e.dispatchEvent(new Event('scroll',{bubbles:true}))});messages.push({...messages[0],id:'incoming-2',body:'Следующее сообщение'});await page.clock.runFor(5100);await expect(feed.locator('article.comment')).toHaveCount(42);await expect.poll(()=>feed.evaluate(e=>e.scrollTop)).toBe(0);
 fail=true;await page.clock.runFor(5100);await expect(page.getByRole('status').filter({hasText:'Повторим автоматически'})).toBeVisible();await expect(feed.locator('article.comment')).toHaveCount(42);await expect(input).toHaveValue('Мой несохранённый ответ');
 fail=false;messages=messages.filter(m=>m.id!=='incoming-2').map(m=>m.id==='incoming'?{...m,body:'Отредактированное сообщение'}:m);await page.clock.runFor(5100);await expect(feed.locator('article.comment')).toHaveCount(41);await expect(feed.getByText('Отредактированное сообщение',{exact:true})).toHaveCount(1);await expect(page.getByRole('status').filter({hasText:'Повторим автоматически'})).toHaveCount(0);
 await page.evaluate(()=>{Object.defineProperty(document,'visibilityState',{configurable:true,value:'hidden'});document.dispatchEvent(new Event('visibilitychange'))});const before=calls;await page.clock.runFor(11000);expect(calls).toBe(before);
 messages.push({...messages[0],id:'return',body:'Сообщение при возврате'});await page.evaluate(()=>{Object.defineProperty(document,'visibilityState',{configurable:true,value:'visible'});document.dispatchEvent(new Event('visibilitychange'))});await expect(feed.getByText('Сообщение при возврате',{exact:true})).toHaveCount(1);await expect(input).toHaveValue('Мой несохранённый ответ');
});

test('slow chat poll cannot overwrite own send and focus does not overlap reads',async({page})=>{
 await fixture(page);await page.clock.install();let messages:any[]=[{id:'initial-race',author:'employee',author_display:'Коллега',body:'Исходное сообщение',created_at:'2026-10-16T10:00:00Z',mentions:[]}];let hold=false,release:()=>void=()=>{};let active=0,maxActive=0,reads=0;
 await page.route(`**/tasks/${taskId}/comments/`,async route=>{
  if(route.request().method()==='POST'){const item={id:'own-live',author:'employee',author_display:'Я',body:route.request().postDataJSON().body,created_at:'2026-10-16T10:00:00Z',mentions:[]};messages.push(item);await route.fulfill({json:item});return}
  reads++;active++;maxActive=Math.max(active,maxActive);const snapshot=[...messages];if(hold){hold=false;await new Promise<void>(resolve=>release=resolve)}active--;await route.fulfill({json:snapshot});
 });
 await page.goto(`/tasks/${taskId}`);await expect(page.getByRole('heading',{name:'Чат задачи',exact:true})).toBeVisible();await expect(page.getByRole('log').getByText('Исходное сообщение',{exact:true})).toHaveCount(1);const baseline=reads;maxActive=0;
 hold=true;await page.evaluate(()=>window.dispatchEvent(new Event('focus')));await expect.poll(()=>reads).toBe(baseline+1);await page.evaluate(()=>{window.dispatchEvent(new Event('focus'));window.dispatchEvent(new Event('focus'))});expect(reads).toBe(baseline+1);
 await page.getByRole('textbox',{name:'Новый комментарий'}).fill('Отправка во время обновления');await page.getByRole('button',{name:'Отправить',exact:true}).click();await expect.poll(()=>messages.length).toBe(2);release();await expect(page.getByRole('log').getByText('Отправка во время обновления',{exact:true})).toHaveCount(1);expect(maxActive).toBe(1);await expect(page.getByRole('textbox',{name:'Новый комментарий'})).toHaveValue('');
});


for(const width of [1280,390])test(`compact messenger bubbles and approval chips at ${width}px`,async({page})=>{
 await fixture(page);await page.setViewportSize({width,height:1000});
 await page.route('**/auth/me/',r=>r.fulfill({json:{id:1,full_name:'Иван',email:'test@example.invalid',roles:[],employee:{id:'me',position:'Руководитель'}}}));
 await page.route(`**/tasks/${taskId}/comments/`,r=>r.fulfill({json:[
  {id:'incoming',author:'colleague',author_display:'Юлия',body:'Проверьте, пожалуйста, решение.',created_at:'2026-10-15T10:00:00Z',mentions:[]},
  {id:'own',author:'me',author_display:'Иван',body:'Принял, проверю сегодня.',created_at:'2026-10-16T10:00:00Z',mentions:[],is_internal:true,can_request_approval:true},
  {id:'long',author:'colleague',author_display:'Юлия',body:'Подробности\n'+('Длинное сообщение без потери переносов. '.repeat(8)),created_at:'2026-10-16T10:01:00Z',mentions:[]}
 ]}));
 await page.route(`**/tasks/${taskId}/approvals/`,r=>r.fulfill({json:[{id:'a1',comment:'own',approver:'other',approver_display:'Екатерина',requester_display:'Иван',status:'PENDING',round_number:1,version:1,source_body:'Принял, проверю сегодня.',history:[],available_actions:['approve']}]}));
 await page.goto(`/tasks/${taskId}`);const feed=page.getByRole('log');await expect(feed.locator('article.comment')).toHaveCount(3);await expect(feed.locator('.task-chat-day')).toHaveCount(2);
 const mine=feed.locator('.is-own');await expect(mine.locator('.task-chat-message-line b')).toHaveText('Иван:');await expect(mine.locator('time')).toHaveAttribute('datetime','2026-10-16T10:00:00Z');await expect(mine.getByText('Внутреннее',{exact:true})).toBeVisible();
 const other=feed.locator('article').first();const a=await mine.boundingBox(),b=await other.boundingBox();expect(a&&b&&a.x>b.x).toBeTruthy();
 const chip=mine.locator('.chat-approval-chip>summary');await expect(chip).toContainText('Ожидает согласования');await expect(chip).toContainText('Екатерина');await expect(mine.getByRole('region',{name:'Согласование: Екатерина'})).toBeHidden();await chip.click();await mine.getByRole('button',{name:'Согласовано',exact:true}).click();await expect(mine.getByRole('button',{name:'Подтвердить',exact:true})).toBeDisabled();await chip.click();
 await expect(page.getByRole('textbox',{name:'Новый комментарий'})).toHaveCSS('height','48px');expect(await page.evaluate(()=>document.documentElement.scrollWidth<=innerWidth)).toBeTruthy();
 for(const theme of ['light','dark']){await page.evaluate(t=>document.documentElement.setAttribute('data-theme',t),theme);await page.locator('.task-chat').screenshot({path:`test-results/checklists/messenger-${width}-${theme}.png`})}
});


for(const width of [1280,390])test(`Enter sends, Shift Enter adds line and mentions select first at ${width}px`,async({page})=>{
 await fixture(page);await page.setViewportSize({width,height:1000});const messages:any[]=[];const sent:any[]=[];
 await page.route(`**/tasks/${taskId}/comments/`,async route=>{if(route.request().method()==='POST'){const body=route.request().postDataJSON();sent.push(body);const c={id:'keyboard-'+sent.length,author:'me',author_display:'Я',body:body.body,created_at:'2026-10-16T10:00:00Z',mentions:body.mentions};messages.push(c);await route.fulfill({json:c})}else await route.fulfill({json:messages})});
 await page.goto(`/tasks/${taskId}`);const input=page.getByRole('textbox',{name:'Новый комментарий'});await input.press('Enter');expect(sent).toHaveLength(0);
 await input.fill('Первая строка');await input.press('Shift+Enter');await input.pressSequentially('Вторая строка');await expect(input).toHaveValue('Первая строка\nВторая строка');expect(sent).toHaveLength(0);
 await input.evaluate(e=>e.dispatchEvent(new KeyboardEvent('keydown',{key:'Enter',code:'Enter',isComposing:true,bubbles:true})));expect(sent).toHaveLength(0);
 await input.press('Enter');await expect.poll(()=>sent.length).toBe(1);expect(sent[0].body).toBe('Первая строка\nВторая строка');await expect(input).toHaveValue('');
 await input.fill('@Лив');await page.getByRole('option',{name:'Ливеринов Иван',exact:true}).waitFor();await input.press('Enter');await expect(input).toHaveValue('@Ливеринов Иван ');expect(sent).toHaveLength(1);
 await input.press('Enter');await expect.poll(()=>sent.length).toBe(2);expect(sent[1].mentions).toEqual(['ivan']);await expect(input).toHaveValue('');
});

for(const width of [1280,390])test(`simple approval form works without chat source at ${width}px`,async({page})=>{
 await fixture(page);await page.setViewportSize({width,height:1000});const posts:any[]=[];let approvals:any[]=[];const comments:any[]=[];
 await page.route(`**/tasks/${taskId}/comments/`,r=>r.fulfill({json:comments}));
 await page.route('**/approval-options/',r=>r.fulfill({json:[{id:'approver',name:'Екатерина'}]}));
 await page.route(`**/tasks/${taskId}/approvals/`,async r=>{if(r.request().method()==='POST'){const body=r.request().postDataJSON();posts.push(body);if(width===390&&posts.length===1){await r.fulfill({status:503,json:{detail:'Временно недоступно'}});return}const c={id:'new-request-comment',author:'me',author_display:'Иван',body:body.text,created_at:'2026-10-16T10:00:00Z',mentions:[]};comments.push(c);const a={...body,comment:c.id,id:'created',requester_display:'Иван',approver_display:'Екатерина',status:'PENDING',round_number:1,version:1,source_body:body.text,history:[],available_actions:[]};approvals.push(a);await r.fulfill({status:201,json:a})}else await r.fulfill({json:approvals})});
 await page.goto(`/tasks/${taskId}`);const header=page.locator('.task-chat-heading');const button=header.getByRole('button',{name:'Запросить согласование',exact:true});await expect(button).toHaveCount(1);await expect(page.getByRole('log').getByRole('button',{name:'Запросить согласование',exact:true})).toHaveCount(0);
 const a=await button.boundingBox(),b=await header.getByRole('heading',{name:'Чат задачи'}).boundingBox();expect(a&&b&&a.x>b.x).toBeTruthy();await button.click();const panel=page.getByRole('region',{name:'Запрос согласования',exact:true});await expect(panel.getByRole('combobox')).toHaveCount(1);await expect(panel.getByRole('textbox')).toHaveCount(1);await expect(panel.getByText('Сообщение для согласования',{exact:true})).toHaveCount(0);await expect(panel.locator('blockquote')).toHaveCount(0);await panel.getByRole('combobox',{name:'Согласующий',exact:true}).selectOption('approver');await expect(panel.getByRole('button',{name:'Отправить на согласование'})).toBeDisabled();await panel.getByRole('textbox',{name:'Текст запроса согласования'}).fill('Проверьте новое решение');expect(await page.evaluate(()=>document.documentElement.scrollWidth<=innerWidth)).toBeTruthy();await panel.screenshot({path:`test-results/checklists/simple-approval-${width}.png`});await panel.getByRole('button',{name:'Отправить на согласование'}).click();
 if(width===390){await expect(panel.getByRole('alert')).toBeVisible();await expect(panel.getByRole('textbox')).toHaveValue('Проверьте новое решение');expect(comments).toHaveLength(0);await panel.getByRole('button',{name:'Отправить на согласование'}).click()}
 await expect(panel).toHaveCount(0);expect(posts).toHaveLength(width===390?2:1);expect(posts[0].comment).toBeUndefined();expect(posts[0].approver).toBe('approver');if(posts.length===2)expect(posts[0].command_id).toBe(posts[1].command_id);await expect(page.getByRole('log').locator('.task-chat-message-line').getByText('Проверьте новое решение',{exact:true})).toHaveCount(1);await expect(page.getByRole('log').locator('.chat-approval-chip')).toHaveCount(1);
 await button.click();await panel.getByRole('textbox',{name:'Текст запроса согласования'}).press('Escape');await expect(panel).toHaveCount(0);await expect(button).toBeFocused();
});

test('simple approval action remains hidden without request permission',async({page})=>{
 await fixture(page);await page.route(`**/tasks/${taskId}/approval-options/`,r=>r.fulfill({status:403,json:{detail:'Нет права'}}));await page.goto(`/tasks/${taskId}`);await page.getByRole('heading',{name:'Чат задачи',exact:true}).waitFor();await expect(page.locator('.task-chat-heading').getByRole('button',{name:'Запросить согласование'})).toHaveCount(0);
});


for(const width of [1280,390])test(`opening bell marks all notifications read and removes badge at ${width}px`,async({page})=>{
 await fixture(page);await page.setViewportSize({width,height:1000});const notifications=Array.from({length:15},(_,i)=>({id:`notice-${i}`,title:`Уведомление ${i+1}`,message:'Рабочее событие',is_read:false,action_url:`/tasks/${taskId}`}));const reads:string[]=[];
 await page.route('**/api/v1/notifications/**',async route=>{const u=new URL(route.request().url());if(route.request().method()==='POST'){if(u.pathname.endsWith('/read-all/'))notifications.forEach(n=>n.is_read=true);else{const id=u.pathname.split('/').at(-3)!;reads.push(id);notifications.find(n=>n.id===id)!.is_read=true}await route.fulfill({json:{status:'ok'}})}else{const list=u.searchParams.has('unread')?notifications.filter(n=>!n.is_read):notifications;await route.fulfill({json:{count:list.length,results:list}})}});
 await page.goto(`/tasks/${taskId}`);const bell=page.locator('.notification-bell>button');await expect(bell.locator('b')).toHaveText('15');await bell.click();const popover=page.locator('.notification-popover');const popBox=await popover.boundingBox();expect(popBox&&popBox.x>=0&&popBox.x+popBox.width<=width).toBeTruthy();await expect(popover.getByText('Уведомление 1',{exact:true})).toBeVisible();await expect(bell.locator('b')).toHaveCount(0);expect(reads).toHaveLength(0);expect(notifications.every(n=>n.is_read)).toBe(true);await expect(popover.locator('button.read')).toHaveCount(5);await expect(popover.getByRole('link',{name:'Все уведомления'})).toHaveAttribute('href','/#notifications');await expect(popover.getByRole('button',{name:'Прочитать все',exact:true})).toHaveCount(0);await expect(bell.locator('b')).toHaveCount(0);await page.evaluate(()=>window.dispatchEvent(new Event('focus')));await expect(bell.locator('b')).toHaveCount(0);await bell.click();await bell.click();await expect(popover.getByText('Уведомление 1',{exact:true})).toBeVisible();await expect(popover.locator('button.read')).toHaveCount(5);await expect(bell.locator('b')).toHaveCount(0);await popover.screenshot({path:`test-results/checklists/notification-read-${width}.png`});
});

test('failed automatic read keeps accurate paginated badge until retry confirms',async({page})=>{
 await fixture(page);const notifications=Array.from({length:40},(_,i)=>({id:`paged-${i}`,title:`Событие ${i}`,message:'Проверка',is_read:false}));let failAll=true;
 await page.route('**/api/v1/notifications/**',async route=>{const u=new URL(route.request().url());if(route.request().method()==='POST'){if(u.pathname.endsWith('/read-all/')){if(failAll){await route.fulfill({status:503,json:{detail:'Unavailable'}});return}notifications.forEach(n=>n.is_read=true)}else{const id=u.pathname.split('/').at(-3)!;if(id==='paged-0'){await route.fulfill({status:503,json:{detail:'Unavailable'}});return}notifications.find(n=>n.id===id)!.is_read=true}await route.fulfill({json:{status:'ok'}})}else{const list=u.searchParams.has('unread')?notifications.filter(n=>!n.is_read):notifications;await route.fulfill({json:{count:list.length,results:list.slice(0,25)}})}});
 await page.goto(`/tasks/${taskId}`);const bell=page.locator('.notification-bell>button');await expect(bell.locator('b')).toHaveText('40');await bell.click();await expect(bell.locator('b')).toHaveText('40');await expect(page.getByRole('alert')).toContainText('Не удалось');const all=page.locator('.notification-popover').getByRole('button',{name:'Прочитать все'});await all.click();await expect(page.getByRole('alert')).toContainText('Не удалось прочитать');await expect(bell.locator('b')).toHaveText('40');failAll=false;await all.click();await expect(bell.locator('b')).toHaveCount(0);
});

test('notification center read updates bell and late unread response cannot restore count',async({page})=>{
 await fixture(page);const notifications=Array.from({length:3},(_,i)=>({id:`center-${i}`,title:`Из центра ${i}`,message:'Событие',is_read:false,priority:'normal',entity_type:'Task',created_at:'2026-10-16T10:00:00Z'}));let hold=false,release:()=>void=()=>{},held=false;
 await page.route('**/api/v1/notifications/**',async route=>{const u=new URL(route.request().url());if(route.request().method()==='POST'){if(u.pathname.endsWith('/read-all/'))notifications.forEach(n=>n.is_read=true);else notifications.find(n=>n.id===u.pathname.split('/').at(-3))!.is_read=true;await route.fulfill({json:{status:'ok'}});return}const items=u.searchParams.has('unread')?notifications.filter(n=>!n.is_read):notifications;const snapshot=JSON.parse(JSON.stringify({count:items.length,results:items}));if(hold&&u.searchParams.has('unread')){hold=false;held=true;await new Promise<void>(r=>release=r)}await route.fulfill({json:snapshot})});
 await page.goto('/#notifications');const bell=page.locator('.notification-bell>button');await expect(bell.locator('b')).toHaveText('3');await page.locator('.notification-list').getByRole('button').first().click();await expect(bell.locator('b')).toHaveText('2');hold=true;await page.evaluate(()=>window.dispatchEvent(new Event('focus')));await expect.poll(()=>held).toBe(true);await page.getByRole('button',{name:'Прочитать все',exact:true}).click();await expect(bell.locator('b')).toHaveCount(0);release();await page.waitForTimeout(300);await expect(bell.locator('b')).toHaveCount(0);
});


test('bell shows five latest already-read notifications after reload',async({page})=>{
 await fixture(page);const notifications=Array.from({length:8},(_,i)=>({id:`history-${i}`,title:`Прочитанное ${i+1}`,message:'История',is_read:true,created_at:`2026-10-16T10:0${7-i}:00Z`}));let historyReads=0;
 await page.route('**/api/v1/notifications/**',async route=>{const u=new URL(route.request().url());if(route.request().method()==='POST'){await route.fulfill({json:{status:'ok'}});return}const items=u.searchParams.has('unread')?[]:notifications;if(!u.searchParams.has('unread'))historyReads++;await route.fulfill({json:{count:items.length,results:items}})});
 await page.goto(`/tasks/${taskId}`);const bell=page.locator('.notification-bell>button');await bell.click();const pop=page.locator('.notification-popover');await expect(pop.getByText('Прочитанное 1',{exact:true})).toBeVisible();await expect(pop.locator('button.read')).toHaveCount(5);await expect(pop.getByText('Прочитанное 6',{exact:true})).toHaveCount(0);await expect(bell.locator('b')).toHaveCount(0);await page.reload();await bell.click();await expect(pop.getByText('Прочитанное 1',{exact:true})).toBeVisible();await expect(pop.locator('button.read')).toHaveCount(5);expect(historyReads).toBeGreaterThanOrEqual(2);
});
