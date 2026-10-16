import {test,expect,Page} from '@playwright/test';
const id='employee-one';
async function fixture(page:Page,manage=true){
 await page.addInitScript(()=>sessionStorage.setItem('access','synthetic-employee-settings'));
 await page.route('**/api/**',async route=>{
  const p=new URL(route.request().url()).pathname;let data:any={results:[]};
  if(p.endsWith('/auth/me/'))data={id:1,full_name:'Администратор',email:'admin@example.invalid',roles:[],employee:null};
  else if(p.endsWith('/employees/dashboard/')){await route.fulfill({status:503,json:{}});return;}
  else if(p.endsWith(`/people/employees/${id}/`))data={id,display_name:'Могунова Юлия',account_status:'ACTIVE',account:{email:'julia@example.invalid'},roles:[{code:'approvals',name:'Участник согласования'},...Array.from({length:51},()=>({code:'objects',name:'Просмотр объектов'}))],functional_groups:[{id:'g1',name:'Рабочая группа'}]};
  else if(p.includes('/people/employees/denied/')){await route.fulfill({status:403,json:{detail:'Нет доступа к сотруднику'}});return;}
  else if(p.endsWith(`/employees/${id}/objects/`))data={can_manage:manage,employment_location_name:'Офис',responsibility_mode:'selected',responsibility_locations:[],roles:Array.from({length:51},(_,i)=>({name:'Просмотр объектов',location:'loc'+i,location_name:i===0?'OhMyGesh':`Объект ${i}`,scopes:['location','own']}))};
  else if(p.endsWith('/invitations/options/'))data={locations:[{id:'loc0',name:'OhMyGesh'}],roles:[{id:'role0',name:'Просмотр объектов'}],allow_all_responsibility:false};
  await route.fulfill({status:200,json:data});
 });
}
for(const width of [1280,390])test(`separate pages, grouped roles and search at ${width}`,async({page})=>{
 await fixture(page);await page.setViewportSize({width,height:1000});let objectCalls=0;page.on('request',r=>{if(r.url().endsWith('/objects/'))objectCalls++});
 await page.goto(`/people/employees/${id}`);
 await expect(page.getByRole('heading',{name:'Могунова Юлия',exact:true})).toBeVisible();
 await expect(page.getByRole('heading',{name:'Доступ и группы',exact:true})).toHaveCount(0);expect(objectCalls).toBe(0);
 const menu=page.getByRole('button',{name:'Настройки сотрудника'});await menu.click();await expect(page.getByRole('link',{name:'Объекты и права',exact:true})).toBeVisible();await page.keyboard.press('Escape');await expect(page.getByRole('link',{name:'Объекты и права',exact:true})).not.toBeVisible();
 await menu.click();await page.getByRole('link',{name:'Доступ и группы',exact:true}).click();
 await expect(page.getByRole('heading',{name:'Доступ и группы',exact:true})).toBeVisible();await expect(page.getByText('Просмотр объектов',{exact:true})).toHaveCount(1);await expect(page.getByText('Назначений: 51',{exact:true})).toBeVisible();
 await page.getByLabel('Поиск ролей и групп').fill('Рабочая');await expect(page.getByText('Рабочая группа',{exact:true})).toBeVisible();await expect(page.getByText('Подходящих ролей нет',{exact:true})).toBeVisible();
 await page.getByRole('link',{name:'Объекты и права',exact:true}).click();await expect(page.getByRole('heading',{name:'Объекты и права',exact:true})).toBeVisible();await page.getByLabel('Поиск объектов и ролей').fill('OhMy');await expect(page.locator('.employee-object-list article')).toHaveCount(1);await expect(page.getByText('Выбранный объект · Собственные данные',{exact:true})).toBeVisible();
 await page.getByLabel('Поиск объектов и ролей').fill('не существует');await expect(page.getByText('Подходящих объектов и ролей нет')).toBeVisible();await page.getByLabel('Поиск объектов и ролей').fill('');
 await page.reload();await expect(page.getByRole('heading',{name:'Объекты и права',exact:true})).toBeVisible();expect(await page.evaluate(()=>document.documentElement.scrollWidth<=innerWidth)).toBeTruthy();await page.screenshot({path:`${process.env.AYS_EMPLOYEE_SETTINGS_OUTPUT||'test-results/employee-settings'}/objects-${width}.png`,fullPage:true});
 await page.getByRole('button',{name:'← К карточке сотрудника'}).click();await expect(page.getByRole('heading',{name:'Могунова Юлия',exact:true})).toBeVisible();
});
test('read-only objects and forbidden direct route preserve API boundary',async({page})=>{
 await fixture(page,false);await page.goto(`/people/employees/${id}/objects`);await expect(page.getByRole('heading',{name:'Объекты и права',exact:true})).toBeVisible();await expect(page.getByText('Изменить ответственность или объектный доступ',{exact:true})).toHaveCount(0);
 await page.goto('/people/employees/denied/access');await expect(page.getByText('Нет доступа к сотруднику',{exact:true})).toBeVisible();await expect(page.getByText('Просмотр объектов',{exact:true})).toHaveCount(0);
});

test('object editor retains explicit scoped assignment payload',async({page})=>{
 await fixture(page);await page.goto(`/people/employees/${id}/objects`);await page.getByText('Изменить ответственность или объектный доступ',{exact:true}).click();
 await page.getByLabel('Найти объект',{exact:true}).fill('OhMy');await page.getByRole('checkbox',{name:'OhMyGesh',exact:true}).check();await page.getByRole('combobox',{name:'Роль',exact:true}).selectOption('role0');
 const sent=page.waitForRequest(r=>r.method()==='POST'&&r.url().endsWith(`/employees/${id}/access/`));await page.getByRole('button',{name:'Назначить роль в выбранных объектах',exact:true}).click();expect((await sent).postDataJSON()).toEqual({action:'assign',role:'role0',access_locations:['loc0']});
});

