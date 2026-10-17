// Server-render the actual approval component; browser interaction is tested separately.
import {test,after} from 'node:test';
import assert from 'node:assert/strict';
import React from 'react';
import {renderToStaticMarkup} from 'react-dom/server';
import {createServer} from 'vite';
const server=await createServer({server:{middlewareMode:true},appType:'custom'});
after(()=>server.close());
const {CommentApprovals}=await server.ssrLoadModule('/src/TaskApprovals.tsx');
const approval={id:'a',comment:'c',approver:'p',requester_display:'Инициатор',approver_display:'Согласующий',round_number:1,version:1,source_body:'Запрос',history:[],available_actions:[]};
for(const status of ['PENDING','CLARIFICATION_REQUESTED','APPROVED','CANCELLED']){
 test(`actual message badge renders attention only for ${status}`,()=>{
  const html=renderToStaticMarkup(React.createElement(CommentApprovals,{taskId:'task',comment:{id:'c'},approvals:[{...approval,status}],reload:async()=>{}}));
  assert.equal((html.match(/class="approval-attention"/g)||[]).length,status==='CLARIFICATION_REQUESTED'?2:0);
  if(status==='CLARIFICATION_REQUESTED'){
   assert.match(html,/aria-hidden="true">!<\/span>/);
   assert.match(html,/Нужно уточнение/);
   assert.match(html,/<summary>.*approval-attention/);
  }
 });
}
