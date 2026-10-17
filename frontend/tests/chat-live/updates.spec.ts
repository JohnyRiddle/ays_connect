import {test,expect,BrowserContext,Page} from '@playwright/test';

// Two independent browser sessions share synthetic server state. No live user data or messages.
function server(){
 const task={id:'task-1',number:'T-1',title:'Проверка чата',status:'in_progress',version:7,active_priority:null,available_actions:[]};
 const comments:any[]=[{id:'comment-1',author:'requester',author_display:'Инициатор',body:'Закупка оборудования',created_at:'2026-10-17T12:00:00Z'}];
 const approval:any={id:'approval-1',comment:'comment-1',approver:'approver',requester_display:'Инициатор',approver_display:'Согласующий',status:'PENDING',round_number:1,version:1,source_body:'Закупка оборудования',history:[],available_actions:[]};
 const writes:string[]=[]; let failApprovals=false;
 async function connect(context:BrowserContext,who:string){
  await context.addInitScript(who=>sessionStorage.setItem('access',who),who);
  await context.route('**/api/internal/v1/**',async route=>{
   const request=route.request(),path=new URL(request.url()).pathname,method=request.method();
   const json=(value:unknown,status=200)=>route.fulfill({status,json:value});
   if(method!=='GET')writes.push(path);
   if(path.endsWith('/comments/')){
    if(method==='POST'){comments.push({id:`comment-${comments.length+1}`,author:who,author_display:who,body:request.postDataJSON().body,created_at:new Date().toISOString()});return json(comments.at(-1),201)}
    return json(comments);
   }
   if(path.endsWith('/approvals/')){
    if(failApprovals)return json({detail:'Temporary'},503);
    const actions=who==='approver'&&approval.status==='PENDING'?['clarify','approve']:who==='requester'&&approval.status==='CLARIFICATION_REQUESTED'?['resubmit']:[];
    return json([{...approval,available_actions:actions}]);
   }
   if(/\/approvals\/approval-1\/(clarify|resubmit|approve)\/$/.test(path)){
    const action=path.split('/').at(-2)!;
    approval.status=action==='clarify'?'CLARIFICATION_REQUESTED':action==='approve'?'APPROVED':'PENDING';approval.version++;
    if(action==='resubmit')approval.round_number++;
    approval.history.push({id:String(approval.version),sequence:approval.version,round_number:approval.round_number,action,actor_display:who,text:request.postDataJSON().text,created_at:new Date().toISOString()});
    return json(approval);
   }
   if(path.endsWith('/approval-options/'))return json([]);
   if(path.endsWith('/tasks/task-1/'))return json(task);
   if(path.endsWith('/activity/'))return json({results:[]});
   return json([]);
  });
 }
 return {connect,comments,approval,task,writes,setFail:(value:boolean)=>{failApprovals=value}};
}
const chip=(page:Page)=>page.locator('.chat-approval-chip>summary');
for(const width of [1280,390])test(`two sessions receive comments and clarification without reload (${width}px)`,async({browser})=>{
 const state=server();const requester=await browser.newContext({viewport:{width,height:900}}),approver=await browser.newContext({viewport:{width,height:900}});
 await state.connect(requester,'requester');await state.connect(approver,'approver');
 const a=await requester.newPage(),b=await approver.newPage();
 try{
  await Promise.all([a.goto('/tests/chat-live/index.html'),b.goto('/tests/chat-live/index.html')]);
  await expect(chip(a)).toContainText('Ожидает согласования');await expect(chip(b)).toContainText('Ожидает согласования');
  let navigations=0;a.on('framenavigated',()=>navigations++);b.on('framenavigated',()=>navigations++);
  await a.getByRole('textbox',{name:'Новый комментарий'}).fill('Несохранённый черновик');
  await b.getByRole('textbox',{name:'Новый комментарий'}).fill('Новое сообщение собеседника');await b.getByRole('button',{name:'Отправить',exact:true}).click();
  await expect(a.locator('article.comment').filter({hasText:'Новое сообщение собеседника'})).toBeVisible({timeout:8000});
  await expect(a.getByRole('textbox',{name:'Новый комментарий'})).toHaveValue('Несохранённый черновик');
  await chip(b).click();await b.getByRole('button',{name:'Запросить уточнение',exact:true}).click();await b.getByRole('textbox',{name:'Запросить уточнение — комментарий обязателен'}).fill('Уточните количество');await b.getByRole('button',{name:'Подтвердить',exact:true}).click();
  await expect(chip(a)).toContainText('Нужно уточнение',{timeout:8000});await expect(chip(a).locator('.approval-attention')).toHaveText('!');
  await expect(a.locator('.work-status')).toHaveText('В работе');
  await chip(a).click();await a.getByRole('button',{name:'Отправить новый раунд',exact:true}).click();await a.getByRole('textbox',{name:'Отправить новый раунд — комментарий обязателен'}).fill('Нужно две штуки');await a.getByRole('button',{name:'Подтвердить',exact:true}).click();
  await expect(chip(b)).toContainText('Ожидает согласования',{timeout:8000});await expect(chip(a).locator('.approval-attention')).toHaveCount(0);await expect(chip(b).locator('.approval-attention')).toHaveCount(0);
  expect(state.task).toMatchObject({status:'in_progress',version:7});expect(state.writes.every(path=>path.includes('/comments/')||path.includes('/approvals/'))).toBeTruthy();expect(navigations).toBe(0);
 }finally{await requester.close();await approver.close()}
});
test('approval polling recovers after network failure and retains draft',async({browser})=>{
 const state=server(),context=await browser.newContext();await state.connect(context,'requester');const page=await context.newPage();
 try{await page.goto('/tests/chat-live/index.html');await expect(chip(page)).toContainText('Ожидает согласования');await page.getByRole('textbox',{name:'Новый комментарий'}).fill('Черновик');
 state.setFail(true);await expect(page.getByRole('alert')).toContainText('Повторим автоматически',{timeout:8000});state.setFail(false);state.approval.status='CLARIFICATION_REQUESTED';await expect(chip(page)).toContainText('Нужно уточнение',{timeout:8000});await expect(page.getByRole('alert')).toHaveCount(0);await expect(page.getByRole('textbox',{name:'Новый комментарий'})).toHaveValue('Черновик');
 }finally{await context.close()}
});
test('remote round change invalidates an open decision without losing its draft',async({browser})=>{
 const state=server(),context=await browser.newContext();await state.connect(context,'approver');const page=await context.newPage();
 try{await page.goto('/tests/chat-live/index.html');await expect(chip(page)).toContainText('Ожидает согласования');await chip(page).click();await page.getByRole('button',{name:'Согласовано',exact:true}).click();
 await page.getByRole('textbox',{name:'Согласовано — комментарий обязателен'}).fill('Проверено для первого раунда');
 state.approval.version+=2;state.approval.round_number=2;
 await expect(page.getByText('Согласование изменилось.',{exact:false})).toBeVisible({timeout:8000});await expect(page.getByRole('button',{name:'Подтвердить',exact:true})).toBeDisabled();
 await expect(page.getByRole('textbox',{name:'Согласовано — комментарий обязателен'})).toHaveValue('Проверено для первого раунда');expect(state.writes).toEqual([]);
 await page.getByRole('button',{name:'Выбрать действие заново'}).click();await page.getByRole('button',{name:'Согласовано',exact:true}).click();await expect(page.getByRole('textbox',{name:'Согласовано — комментарий обязателен'})).toHaveValue('Проверено для первого раунда');
 }finally{await context.close()}
});
