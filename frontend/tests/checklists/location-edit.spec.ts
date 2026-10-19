import {test,expect,Page} from '@playwright/test';
const id='00000000-0000-4000-8000-000000000013';
async function fixture(page:Page,{edit=true,failPage=false,failSave=false}={}) {
  let pageFailure=failPage,saveFailure=failSave;
  const writes:any[]=[];const pages:number[]=[];
  let task={id,number:'TASK-13',title:'Смена объекта',description:'Сохранённое описание',status:'in_progress',priority:'normal',version:1,location:'old',responsible_department:'it',can_change_department:false,available_actions:edit?['edit']:[],checklist_progress:{completed:0,total:0}};
  const first=Array.from({length:25},(_,i)=>({id:i===0?'old':`location-${i}`,name:i===0?'Исходный объект':`Объект ${i}`,is_active:true}));
  await page.addInitScript(()=>sessionStorage.setItem('access','synthetic-location-test'));
  await page.route('**/api/**',async route=>{
    const r=route.request(),u=new URL(r.url()),p=u.pathname;let data:any={count:0,next:null,results:[]};
    if(p.endsWith('/auth/me/'))data={id:1,full_name:'Синтетический пользователь',roles:[],employee:null};
    else if(p.endsWith('/employees/dashboard/')){await route.fulfill({status:503,json:{}});return;}
    else if(p.endsWith('/locations/')){const n=Number(u.searchParams.get('page')||1);pages.push(n);if(n===2&&pageFailure){pageFailure=false;await route.fulfill({status:503,json:{detail:'Вторая страница недоступна'}});return;}data=n===1?{count:27,next:'https://unused.invalid/locations/?page=2',results:first}:{count:27,next:null,results:[{id:'new',name:'О!Пушка',code:'OBJ-55',is_active:true},{id:'archived',name:'Архивный',is_archived:true}]};}
    else if(p.endsWith(`/tasks/${id}/`)){if(r.method()==='PATCH'){writes.push(r.postDataJSON());if(saveFailure){saveFailure=false;await route.fulfill({status:400,json:{detail:'Ответственному требуется доступ к выбранному объекту.'}});return;}task={...task,...r.postDataJSON(),version:task.version+1};}data=task;}
    else if(p.endsWith('/tasks/assignment-options/'))data=u.searchParams.has('department')?{responsible:{name:'Синтетический руководитель'},executors:[]}:{departments:[{id:'it',name:'IT'}],priority_hours:{normal:72}};
    else if(['/comments/','/attachments/','/checklists/','/watchers/','/approvals/'].some(x=>p.endsWith(x)))data=[];
    else if(p.endsWith('/activity/'))data={results:[]};
    await route.fulfill({json:data});
  });return {writes,pages};
}
for(const width of [1280,390])test(`location edit, failure, cancel and save at ${width}px`,async({page})=>{
  const f=await fixture(page,{failSave:true});await page.setViewportSize({width,height:900});await page.goto(`/tasks/${id}`);
  await page.getByText('Изменить параметры',{exact:true}).click();const form=page.locator('details').filter({has:page.getByText('Изменить параметры',{exact:true})});
  const select=form.getByLabel('Объект / локация',{exact:true});await expect(select).toBeEnabled();await expect(select.locator('option[value="new"]')).toHaveText('О!Пушка · OBJ-55');expect(f.pages.slice(-2)).toEqual([1,2]);
  await expect(select.locator('option[value="archived"]')).toHaveCount(0);
  await select.selectOption('new');await form.getByRole('button',{name:'Отмена',exact:true}).click();expect(f.writes).toHaveLength(0);
  await page.getByText('Изменить параметры',{exact:true}).click();await expect(select).toHaveValue('old');await select.selectOption('new');await form.getByRole('button',{name:'Сохранить',exact:true}).click();
  await expect(form.getByRole('alert')).toContainText('Ответственному требуется доступ');await expect(select).toHaveValue('new');expect(f.writes[0]).toEqual({version:1,location:'new'});
  await form.getByRole('button',{name:'Сохранить',exact:true}).click();await expect.poll(()=>f.writes.length).toBe(2);await expect(page.getByRole('alert')).toHaveCount(0);
  await page.getByText('Изменить параметры',{exact:true}).click();await expect(form.getByLabel('Объект / локация')).toHaveValue('new');
  expect(await page.evaluate(()=>document.documentElement.scrollWidth<=innerWidth)).toBeTruthy();await form.screenshot({path:`test-results/checklists/location-edit-${width}.png`});
});
test('creation loads later pages and a failed page requires retry',async({page})=>{
  const f=await fixture(page,{failPage:true});await page.goto('/tasks/new');const select=page.getByLabel('Объект / локация',{exact:true});
  await expect(page.getByRole('alert')).toContainText('Вторая страница недоступна');await expect(select).toBeDisabled();await expect(select.locator('option[value="old"]')).toHaveCount(0);
  await page.getByRole('button',{name:'Повторить загрузку объектов'}).click();await expect(select).toBeEnabled();await select.selectOption('new');expect(f.pages.slice(-4)).toEqual([1,2,1,2]);expect(f.writes).toHaveLength(0);
});
test('viewer cannot open task parameter editing',async({page})=>{
  await fixture(page,{edit:false});await page.goto(`/tasks/${id}`);await expect(page.getByRole('heading',{name:'Смена объекта'})).toBeVisible();await expect(page.getByText('Изменить параметры',{exact:true})).toHaveCount(0);
});

