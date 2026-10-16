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
