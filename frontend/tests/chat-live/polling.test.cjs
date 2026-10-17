// Deterministic hook lifecycle tests. Node >=22.13; browser suite is separate.
const {test}=require('node:test');
const assert=require('node:assert/strict');
const fs=require('node:fs');
const vm=require('node:vm');
const {stripTypeScriptTypes}=require('node:module');
const settle=async()=>{for(let i=0;i<30;i++)await Promise.resolve()};
const deferred=()=>{let resolve,reject;const promise=new Promise((a,b)=>{resolve=a;reject=b});return{promise,resolve,reject}};
class WorkApiError extends Error{constructor(status){super('API failure');this.status=status}}
function mount(file,hook,read){
 const intervals=new Set(),timeouts=new Set(),events=new Map();let slots=[],position=0,effect,cleanup,deps,changed,task='one';
 const eventKey=(target,type)=>target+':'+type;
 const target=name=>({addEventListener:(type,fn)=>events.set(eventKey(name,type),fn),removeEventListener:(type)=>events.delete(eventKey(name,type))});
 const document={...target('document'),visibilityState:'visible'};
 const window={...target('window'),setInterval:fn=>{intervals.add(fn);return fn},clearInterval:fn=>intervals.delete(fn),setTimeout:fn=>{timeouts.add(fn);return fn},clearTimeout:fn=>timeouts.delete(fn)};
 const useState=initial=>{const i=position++;if(!(i in slots))slots[i]=initial;return[slots[i],value=>{slots[i]=typeof value==='function'?value(slots[i]):value}]};
 const useRef=initial=>{const i=position++;if(!(i in slots))slots[i]={current:initial};return slots[i]};
 const useEffect=(fn,next)=>{changed=!deps||JSON.stringify(next)!==JSON.stringify(deps);if(changed){effect=fn;deps=next}};
 const source=fs.readFileSync(file,'utf8').replace(/^import .*;\r?\n/gm,'');
 const code=stripTypeScriptTypes(source,{mode:'transform'}).replace(/^export /gm,'')+`\nexports.hook=${hook};`;
 const context={exports:{},useState,useRef,useEffect,window,document,AbortController,WorkApiError,workRequest:read,tasksApi:{comments:read}};
 vm.runInNewContext(code,context);
 const render=(id=task)=>{task=id;position=0;const value=context.exports.hook(task);if(changed){cleanup?.();cleanup=effect();changed=false}return value};
 render();return{render,intervals,timeouts,document,tick:()=>{for(const fn of intervals)fn()},event:(target,type)=>events.get(eventKey(target,type))?.(),unmount:()=>cleanup?.()};
}
for(const [file,hook,key,refresh,error] of [
 ['src/useTaskApprovals.ts','useTaskApprovals','items','refresh','error'],
 ['src/useTaskComments.ts','useTaskComments','comments','refreshComments','chatError'],
]){
 test(`${hook}: two independent mounted sessions receive updates on polling`,async()=>{
  let server=[{id:'1',status:'PENDING'}];const read=async()=>structuredClone(server);
  const a=mount(file,hook,read),b=mount(file,hook,read);await settle();assert.equal(a.render()[key].length,1);assert.equal(b.render()[key].length,1);
  server=[{id:'1',status:'CLARIFICATION_REQUESTED'},{id:'2'}];a.tick();b.tick();await settle();assert.equal(a.render()[key][0].status,'CLARIFICATION_REQUESTED');assert.equal(b.render()[key].length,2);a.unmount();b.unmount();
 });
 test(`${hook}: queued explicit refresh wins over a pre-command response`,async()=>{
  const old=deferred();let calls=0;const app=mount(file,hook,()=>++calls===1?old.promise:Promise.resolve([{id:'new'}]));
  const refreshDone=app.render()[refresh]();app.tick();assert.equal(calls,1);old.resolve([{id:'old'}]);await refreshDone;assert.equal(calls,2);assert.equal(app.render()[key][0].id,'new');app.unmount();
 });
 test(`${hook}: stale task response and unmounted responses are ignored`,async()=>{
  const old=deferred();let count=0;const app=mount(file,hook,()=>++count===1?old.promise:Promise.resolve([{id:'new-task'}]));app.render('two');await settle();old.resolve([{id:'old-task'}]);await settle();assert.equal(app.render()[key][0].id,'new-task');app.unmount();assert.equal(app.intervals.size,0);
 });
 test(`${hook}: hidden pause, visible refresh, transient recovery and access revocation`,async()=>{
  let calls=0,failure=0;const app=mount(file,hook,async()=>{calls++;if(failure)throw new WorkApiError(failure);return[{id:'1'}]});await settle();app.document.visibilityState='hidden';app.tick();await settle();assert.equal(calls,1);
  app.document.visibilityState='visible';app.event('document','visibilitychange');await settle();assert.equal(calls,2);
  failure=503;app.tick();await settle();assert.equal(app.render()[key].length,1);assert.ok(app.render()[error]);failure=0;app.tick();await settle();assert.equal(app.render()[error],'');
  failure=403;app.tick();await settle();assert.equal(app.render()[key].length,0);const before=calls;app.tick();await settle();assert.equal(calls,before);app.unmount();
 });
}
