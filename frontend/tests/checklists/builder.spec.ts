import {test,expect,Page} from '@playwright/test';
const taskId='00000000-0000-4000-8000-000000000003';
const item={id:'item-1',text:'Температура',position:1,required:true,section:'Кухня',help_text:'Измерьте температуру',answer_type:'number',options:[],min_value:0,max_value:10,answer:null,is_completed:false,version:1};
async function fixture(page:Page,manage=true,attached=false,watcherMode=false){
  let templates:any[]=[{id:'template-1',name:'Открытие кухни',description:'Ежедневная проверка',version:1,is_active:true,items:[item]}];
  let checklists:any[]=attached?[{id:'attached-1',name:'Проверка перед открытием',items:[
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
    else if(p.endsWith('/checklists/from-template/')){data={id:'attached-1',name:templates[0].name,source_template_version:1,items:[{...item}]};checklists.push(data);}
    else if(p.endsWith('/checklists/'))data=checklists;
    else if(p.endsWith('/items/item-1/complete/')){const body=req.postDataJSON();checklists[0].items[0]={...item,answer:body.answer,is_completed:true,version:2,completed_at:'2026-10-14T09:00:00Z'};task.checklist_progress={completed:1,total:1};data=checklists[0].items[0];}
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
  await page.getByLabel('Раздел',{exact:true}).fill('Перед открытием');
  await page.getByLabel('Текст пункта',{exact:true}).fill('Оборудование исправно');
  await page.getByLabel('Тип ответа',{exact:true}).selectOption('boolean');
  await page.getByRole('button',{name:'Добавить пункт',exact:true}).click();
  await page.getByLabel('Текст пункта',{exact:true}).nth(1).fill('Температура');
  await page.getByLabel('Тип ответа',{exact:true}).nth(1).selectOption('number');
  await page.getByLabel('Минимум',{exact:true}).fill('0');await page.getByLabel('Максимум',{exact:true}).fill('10');
  await page.getByRole('button',{name:'Предпросмотр',exact:true}).click();
  await expect(page.getByRole('heading',{name:'Перед открытием',exact:true})).toBeVisible();
  await page.getByLabel('Ответ: Оборудование исправно',{exact:true}).selectOption('false');
  await page.getByRole('button',{name:'Редактор',exact:true}).click();
  const posted=page.waitForRequest(r=>r.url().endsWith('/checklist-templates/')&&r.method()==='POST');
  await page.getByRole('button',{name:'Сохранить шаблон',exact:true}).click();
  expect((await posted).postDataJSON().items).toHaveLength(2);
  await expect(page.getByRole('status')).toContainText('Шаблон сохранён');
  expect(await page.evaluate(()=>document.documentElement.scrollWidth<=innerWidth)).toBeTruthy();
  await page.screenshot({path:`${process.env.AYS_CHECKLIST_OUTPUT||'test-results/checklists'}/builder-${width}.png`,fullPage:true});
});
test('template attaches to task and numeric zero is saved with item version',async({page})=>{
  await fixture(page);await page.goto(`/tasks/${taskId}`);
  await page.getByLabel('Шаблон',{exact:true}).selectOption('template-1');await page.getByRole('button',{name:'Прикрепить чек-лист',exact:true}).click();
  await expect(page.getByRole('heading',{name:'Кухня',exact:true})).toBeVisible();
  await page.getByLabel('Ответ: Температура',{exact:true}).fill('0');
  const posted=page.waitForRequest(r=>r.url().endsWith('/items/item-1/complete/'));
  await page.getByRole('button',{name:'Сохранить ответ',exact:true}).click();
  expect((await posted).postDataJSON()).toMatchObject({answer:0,version:1});
  await expect(page.getByRole('button',{name:'Изменить ответ',exact:true})).toBeVisible();
  await expect(page.getByRole('heading',{name:'Чек-листы · 1/1',exact:true})).toBeVisible();
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
  await expect(panel.getByRole('heading',{name:'Чек-листы · 1/6',exact:true})).toBeVisible();
  await expect(panel.getByRole('progressbar')).toHaveAttribute('value','1');
  await expect(panel.getByText('Всё готово',{exact:true})).toBeVisible();
  await expect(panel.getByLabel('Комментарий',{exact:true}).first()).not.toBeVisible();
  await panel.locator('.cb-comment summary').first().click();
  await expect(panel.getByLabel('Комментарий',{exact:true}).first()).toBeVisible();
  await panel.getByLabel('Комментарий',{exact:true}).first().fill('Проверено исполнителем');
  expect(await page.evaluate(()=>document.documentElement.scrollWidth<=innerWidth)).toBeTruthy();
  await panel.screenshot({path:`test-results/checklists/task-layout-${width}.png`});
});

for(const width of [1280,390])test(`watcher search, sequential selection and safe removal at ${width}px`,async({page})=>{
  await fixture(page,true,false,true);await page.setViewportSize({width,height:1000});await page.goto(`/tasks/${taskId}`);
  const panel=page.locator('.task-watchers');const search=panel.getByRole('combobox',{name:'Добавить наблюдателя'});
  await expect(panel.getByRole('listbox')).toHaveCount(0);
  await search.fill('Ак');await expect(panel.getByRole('option',{name:'Аксёнов Александр'})).toBeVisible();
  await expect(panel.getByRole('option')).toHaveCount(1);
  await search.press('Escape');await expect(panel.getByRole('listbox')).toHaveCount(0);
  await search.press('ArrowDown');await search.press('Enter');
  await expect(panel.locator('.person-row').filter({hasText:'Аксёнов Александр'})).toBeVisible();
  await expect(search).toHaveValue('');
  await search.fill('Беж');await panel.getByRole('option',{name:'Бежаев Сергей'}).click();
  await expect(panel.locator('.person-row')).toHaveCount(3);
  await search.fill('Ак');await expect(panel.getByRole('status')).toHaveText('Сотрудники не найдены');
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
