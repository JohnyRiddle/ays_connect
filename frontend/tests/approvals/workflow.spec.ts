import {test,expect,Browser,Page} from '@playwright/test';
import fs from 'node:fs';
const fixturePath=process.env.AYS_APPROVAL_FIXTURE;
if(!fixturePath)throw Error('AYS_APPROVAL_FIXTURE must point to synthetic staging fixture JSON');
const fixture=JSON.parse(fs.readFileSync(fixturePath,'utf8'));
const api=process.env.AYS_APPROVAL_API_URL||'http://127.0.0.1:8035/api/internal/v1';
async function login(browser:Browser,who:string,width:number){
 const context=await browser.newContext({viewport:{width,height:1000}});const page=await context.newPage();await page.goto(`/tasks/${fixture.task}`);
 await page.getByRole('textbox',{name:'Электронная почта'}).fill(who+'@approvals.demo.invalid');await page.getByLabel('Пароль',{exact:true}).fill('Demo12345!');await page.getByRole('button',{name:'Войти',exact:true}).click();
 await expect(page.getByRole('heading',{name:'STAGING: обсуждение закупки',exact:true})).toBeVisible();
 return {context,page};
}
async function taskState(page:Page){
 const token=await page.evaluate(()=>sessionStorage.getItem('access'));const r=await page.request.get(api+'/tasks/'+fixture.task+'/',{headers:{Authorization:'Bearer '+token}});expect(r.ok()).toBeTruthy();return await r.json();
}
for(const width of [1280,390])test(`real API approval rounds and task invariance at ${width}px`,async({browser})=>{
 const requester=await login(browser,'requester',width);const approver=await login(browser,'approver',width);
 const page=requester.page;const title=`Предложение ${width} ${Date.now()}`;
 const chat=page.getByRole('textbox',{name:'Новый комментарий'});await chat.fill(title+' @Сог');await page.locator('.task-chat-mentions').getByRole('option',{name:'Согласующий Сергей'}).click();await page.getByRole('button',{name:'Отправить',exact:true}).click();
 const comment=page.locator('article.comment').filter({hasText:title});await expect(comment).toBeVisible();await expect(comment.locator('.task-approval')).toHaveCount(0);
 const before=await taskState(page);
 await comment.getByRole('button',{name:'Запросить согласование',exact:true}).click();
 await comment.getByRole('combobox',{name:'Согласующий из упомянутых'}).selectOption(fixture.approver);
 await expect(comment.getByRole('button',{name:'Отправить на согласование'})).toBeDisabled();
 await comment.getByRole('textbox',{name:'Текст запроса согласования'}).fill('Проверьте предложение и подтвердите решение');await comment.getByRole('button',{name:'Отправить на согласование'}).click();
 await expect(comment.locator('.approval-status')).toHaveText('Ожидает согласования');
 const approvalId=(await page.evaluate(()=>sessionStorage.getItem('access')))&&await comment.locator('.task-approval').count();expect(approvalId).toBe(1);
 await approver.page.reload();const apComment=approver.page.locator('article.comment').filter({hasText:title});
 await apComment.getByRole('button',{name:'Запросить уточнение',exact:true}).click();await expect(apComment.getByRole('button',{name:'Подтвердить',exact:true})).toBeDisabled();
 await apComment.getByRole('textbox',{name:'Запросить уточнение — комментарий обязателен'}).fill('Уточните состав закупки');await apComment.getByRole('button',{name:'Подтвердить',exact:true}).click();await expect(apComment.locator('.approval-status')).toHaveText('Нужно уточнение');
 await page.reload();await comment.getByRole('button',{name:'Отправить новый раунд',exact:true}).click();await comment.getByRole('textbox',{name:'Отправить новый раунд — комментарий обязателен'}).fill('Состав закупки уточнён');await comment.getByRole('button',{name:'Подтвердить',exact:true}).click();await expect(comment.locator('.task-approval>small')).toContainText('Раунд 2');
 await approver.page.reload();await apComment.getByRole('button',{name:'Согласовано',exact:true}).click();await expect(apComment.getByRole('button',{name:'Подтвердить',exact:true})).toBeDisabled();await apComment.getByRole('textbox',{name:'Согласовано — комментарий обязателен'}).fill('Предложение согласовано');await apComment.getByRole('button',{name:'Подтвердить',exact:true}).click();await expect(apComment.locator('.approval-status')).toHaveText('Согласовано');
 await page.reload();await comment.locator('.task-approval details>summary').click();await expect(comment.locator('.task-approval li')).toHaveCount(4);await expect(comment.getByText('Уточните состав закупки',{exact:true})).toBeVisible();
 expect(await taskState(page)).toEqual(before);
 expect(await page.evaluate(()=>document.documentElement.scrollWidth<=innerWidth)).toBeTruthy();
 await comment.screenshot({path:`test-results/approvals/approved-${width}.png`});
 if(width===1280){await comment.getByRole('button',{name:'Отправить новый раунд',exact:true}).click();await comment.getByRole('textbox',{name:'Отправить новый раунд — комментарий обязателен'}).fill('Повторная проверка');await comment.getByRole('button',{name:'Подтвердить',exact:true}).click();await comment.getByRole('button',{name:'Отменить согласование',exact:true}).click();await comment.getByRole('textbox',{name:'Отменить согласование — комментарий обязателен'}).fill('Проверка больше не требуется');await comment.getByRole('button',{name:'Подтвердить',exact:true}).click();await expect(comment.locator('.approval-status')).toHaveText('Отменено');expect(await taskState(page)).toEqual(before);}
 await requester.context.close();await approver.context.close();
});
