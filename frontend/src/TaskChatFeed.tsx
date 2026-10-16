import React,{useLayoutEffect,useRef} from 'react';

export function TaskChatFeed({children,scrollRequest,active}:{children:React.ReactNode;scrollRequest:number;active:boolean}) {
 const viewport=useRef<HTMLDivElement>(null),content=useRef<HTMLDivElement>(null),stickToBottom=useRef(true),lastRequest=useRef(scrollRequest);
 useLayoutEffect(()=>{
  if(lastRequest.current!==scrollRequest){stickToBottom.current=true;lastRequest.current=scrollRequest}
  if(active&&stickToBottom.current&&viewport.current)viewport.current.scrollTop=viewport.current.scrollHeight;
 },[children,scrollRequest,active]);
 useLayoutEffect(()=>{
  if(!content.current)return;
  const observer=new ResizeObserver(()=>{if(active&&stickToBottom.current&&viewport.current)viewport.current.scrollTop=viewport.current.scrollHeight});
  observer.observe(content.current);if(viewport.current)observer.observe(viewport.current);return()=>observer.disconnect();
 },[active]);
 return <div ref={viewport} className="task-chat-feed" role="log" aria-label="Сообщения задачи" aria-live="polite" aria-relevant="additions" tabIndex={0} onScroll={()=>{const node=viewport.current;if(node)stickToBottom.current=node.scrollHeight-node.scrollTop-node.clientHeight<48}}><div ref={content} className="task-chat-feed-content">{children}</div></div>;
}
