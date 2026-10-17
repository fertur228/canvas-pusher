import {handler, type Config} from './handler.ts';
const config:Config={secret:'test-secret',chat:'123',user:'123',bot:'101:synthetic',url:'https://db.invalid',key:'test-key',githubToken:'',repo:'',ref:'main',observatory:'https://observatory.invalid'};
const update={update_id:42,message:{chat:{id:123},from:{id:123},text:'/brain'}};
function req(body:unknown=update,secret='test-secret'){return new Request('https://webhook.invalid',{method:'POST',headers:{'X-Telegram-Bot-Api-Secret-Token':secret},body:JSON.stringify(body)});}
function assert(value:unknown){if(!value)throw new Error('assertion failed');}
Deno.test('missing/wrong secret, wrong chat and wrong actor do no IO',async()=>{
 let calls=0;const h=handler(config,(()=>{calls++;throw new Error('unexpected');}) as typeof fetch);
 assert((await h(req(update,''))).status===403);
 assert((await h(req({...update,message:{...update.message,chat:{id:456}}}))).status===403);
 assert((await h(req({...update,message:{...update.message,from:{id:456}}}))).status===403);
 assert(calls===0);
});
Deno.test('brain delivery is deduplicated; no blind resend after uncertain send',async()=>{
 let claimed=false,sends=0;
 const request=(async(url:string|URL|Request)=>{
 const path=String(url);
 if(path.includes('webhook_claim')){const result=!claimed;claimed=true;return Response.json(result);}
 if(path.includes('flymind_accounts'))return Response.json([{id:'account'}]);
 if(path.includes('flymind_experiments'))return Response.json([]);
 if(path.includes('sendMessage')){sends++;throw new Error('lost response');}
 throw new Error('unexpected');
 }) as typeof fetch;
 const h=handler(config,request);assert((await h(req())).status===200);assert((await h(req())).status===200);assert(sends===1);
});
Deno.test('academic HTML escaped; acknowledgement persisted',async()=>{
 let sent='',ack=false;
 const request=(async(url:string|URL|Request,init?:RequestInit)=>{
 const path=String(url);
 if(path.includes('webhook_claim'))return Response.json(true);
 if(path.includes('flymind_accounts'))return Response.json([{id:'account'}]);
 if(path.includes('course_grades'))return Response.json([{course_name:'<private&course>',current_score:95}]);
 if(path.includes('sendMessage')){sent=JSON.parse(String(init?.body)).text;return Response.json({ok:true,result:{message_id:12}});}
 if(path.includes('webhook_updates')){ack=true;return new Response(null,{status:204});}
 throw new Error('unexpected');
 }) as typeof fetch;
 assert((await handler(config,request)(req({...update,message:{...update.message,text:'/stats'}}))).status===200);
 assert(sent.includes('&lt;private&amp;course&gt;')&&!sent.includes('<private&course>')&&ack);
});

Deno.test('start/menu commands and persistent buttons preserve separate grades action',async()=>{
 const texts=['/start','/start@new_bot','/menu','📊 My Grades','🧠 Fly Brain','⚙️ System Status','📅 Deadlines','📊 Мои оценки','🧠 Мозг мухи','⚙️ Статус системы','📅 Дедлайны'];
 for(const text of texts){let sent:any,grades=0,neural=0;
  const request=(async(url:string|URL|Request,init?:RequestInit)=>{
   const path=String(url);
   if(path.includes('webhook_claim'))return Response.json(true);
   if(path.includes('flymind_accounts'))return Response.json([{id:'account',canvas_origin:'https://canvas.invalid'}]);
   if(path.includes('course_grades')){grades++;return Response.json([]);}
   if(path.includes('flymind_experiments')){neural++;return Response.json([]);}
   if(path.includes('flymind_health')||path.includes('flymind_manual_requests'))return Response.json([]);
   if(path.includes('flymind_deadlines'))return Response.json({synced_at:null,rows:[]});
   if(path.includes('sendMessage')){sent=JSON.parse(String(init?.body));return Response.json({ok:true,result:{message_id:3}});}
   if(path.includes('webhook_updates'))return new Response(null,{status:204});
   throw new Error(path);
  }) as typeof fetch;
  assert((await handler(config,request)(req({...update,message:{...update.message,text}}))).status===200);
  if(text.startsWith('/start')||text==='/menu'){assert(sent.reply_markup.is_persistent&&grades===0&&neural===0);assert(sent.reply_markup.keyboard[0][0].text==='📅 Дедлайны');}
  if(text==='📅 Deadlines'||text==='📅 Дедлайны')assert(sent.text.includes('Ещё не синхронизировано')&&neural===0);
 }
});
Deno.test('bot update identity and acknowledgement are bot scoped',async()=>{
 const seen=new Set<string>();let sends=0;const ack:string[]=[];
 const request=(async(url:string|URL|Request,init?:RequestInit)=>{
  const path=String(url),payload=JSON.parse(String(init?.body??'{}'));
  if(path.includes('webhook_claim')){const key=payload.p_bot+':'+payload.p_update;const fresh=!seen.has(key);seen.add(key);return Response.json(fresh);}
  if(path.includes('flymind_accounts'))return Response.json([{id:'account'}]);
  if(path.includes('sendMessage')){sends++;return Response.json({ok:true,result:{message_id:1}});}
  if(path.includes('webhook_updates')){ack.push(path);return new Response(null,{status:204});}
  throw new Error(path);
 }) as typeof fetch;
 const body={...update,message:{...update.message,text:'/menu'}};
 await handler(config,request)(req(body));await handler(config,request)(req(body));await handler({...config,bot:'102:synthetic'},request)(req(body));
 assert(sends===2&&ack[0].includes('bot_id=eq.101')&&ack[1].includes('bot_id=eq.102'));
});
Deno.test('database outage is retryable before claim and never fabricates an empty list',async()=>{
 let sends=0;const request=(async(url:string|URL|Request)=>{if(String(url).includes('sendMessage'))sends++;return new Response(null,{status:503});}) as typeof fetch;
 assert((await handler(config,request)(req({...update,message:{...update.message,text:'/deadlines'}}))).status===503);assert(sends===0);
});
Deno.test('manual refresh configuration failure never dispatches old legacy workflow',async()=>{
 let dispatches=0;let text='';
 const request=(async(url:string|URL|Request,init?:RequestInit)=>{
  const path=String(url);if(path.includes('dispatches'))dispatches++;
  if(path.includes('webhook_claim'))return Response.json(true);
  if(path.includes('flymind_accounts'))return Response.json([{id:'account'}]);
  if(path.includes('sendMessage')){text=JSON.parse(String(init?.body)).text;return Response.json({ok:true,result:{message_id:1}});}
  throw new Error(path);
 }) as typeof fetch;
 await handler(config,request)(req({...update,message:{...update.message,text:'/check'}}));
 assert(dispatches===0&&text.includes('Запуск не выполнен'));
});
Deno.test('accepted dispatch remains pending; repeated button press does not dispatch again',async()=>{
 let created=false,dispatches=0;const texts:string[]=[];
 const request=(async(url:string|URL|Request,init?:RequestInit)=>{
  const path=String(url);
  if(path.includes('webhook_claim'))return Response.json(true);
  if(path.includes('flymind_accounts'))return Response.json([{id:'account'}]);
  if(path.includes('/actions/variables/')){const n=path.split('/').pop()!;return Response.json({value:({CANVAS_WORKER_ENABLED:'true',FLYMIND_ENABLED:'true',FLYMIND_ACCOUNT_ID:'account',DELIVERY_MODE:'test',FLYMIND_PRODUCTION_AUTHORIZED:'false'} as Record<string,string>)[n]});}
  if(path.includes('/contents/'))return Response.json({encoding:'base64',content:btoa('MANUAL_REQUEST_ID: src.flymind.manual_sync run')});
  if(path.includes('/dispatches')){dispatches++;assert(JSON.parse(String(init?.body)).inputs.manual_request_id==='request');return new Response(null,{status:204});}
  if(path.includes('/actions/workflows/'))return Response.json({state:'active'});
  if(path.includes('rpc/flymind_manual_request')){const fresh=!created;created=true;return Response.json({accepted:fresh,id:'request',state:fresh?'queued':'dispatched'});}
  if(path.includes('flymind_manual_requests')||path.includes('webhook_updates'))return new Response(null,{status:204});
  if(path.includes('sendMessage')){texts.push(JSON.parse(String(init?.body)).text);return Response.json({ok:true,result:{message_id:1}});}
  if(path.includes('answerCallbackQuery'))return Response.json({ok:true,result:true});
  throw new Error(path);
 }) as typeof fetch;
 const h=handler({...config,manualEnabled:true,githubToken:'synthetic',repo:'owner/repo'},request);
 await h(req({...update,message:{...update.message,text:'/check'}}));
 await h(req({update_id:43,callback_query:{id:'cb',data:'check',from:{id:123},message:{chat:{id:123},message_id:1}}}));
 assert(dispatches===1&&texts[0].includes('ещё не завершена')&&texts[1].includes('Повторный запуск не создан'));
});
Deno.test('deadline callback edits a bounded cached page without simulation or workflow dispatch',async()=>{
 let edited:any;let queried:any;
 const request=(async(url:string|URL|Request,init?:RequestInit)=>{
  const path=String(url);
  if(path.includes('webhook_claim'))return Response.json(true);
  if(path.includes('flymind_accounts'))return Response.json([{id:'account',canvas_origin:'https://canvas.invalid'}]);
  if(path.includes('flymind_deadlines')){queried=JSON.parse(String(init?.body));return Response.json({synced_at:'2026-10-14T18:00:00Z',page:1,total:4,rows:[{name:'SYNTHETIC',has_submitted:false,due_at:null}]});}
  if(path.includes('editMessageText')){edited=JSON.parse(String(init?.body));return Response.json({ok:true,result:{message_id:77}});}
  if(path.includes('answerCallbackQuery'))return Response.json({ok:true,result:true});
  if(path.includes('webhook_updates'))return new Response(null,{status:204});
  throw new Error('unexpected network operation');
 }) as typeof fetch;
 await handler(config,request)(req({update_id:45,callback_query:{id:'cb',data:'deadlines:all:1',from:{id:123},message:{chat:{id:123},message_id:77}}}));
 assert(queried.p_page===1&&queried.p_view==='all'&&edited.message_id===77&&edited.text.includes('Страница 2/2'));
});
Deno.test('Telegram rate-limit or lost acknowledgement never causes blind webhook resend',async()=>{
 for(const status of [429,500]){let claimed=false,sends=0;
  const request=(async(url:string|URL|Request)=>{
   const path=String(url);if(path.includes('webhook_claim')){const fresh=!claimed;claimed=true;return Response.json(fresh);}
   if(path.includes('flymind_accounts'))return Response.json([{id:'account'}]);
   if(path.includes('sendMessage')){sends++;return Response.json({ok:false,error_code:status,parameters:{retry_after:30}},{status});}
   throw new Error('unexpected');
  }) as typeof fetch;
  const h=handler(config,request),body={...update,message:{...update.message,text:'/menu'}};
  assert((await h(req(body))).status===200);await h(req(body));assert(sends===1);
 }
});

Deno.test('zero is a recorded grade; missing grades excluded; physical grade never fabricated',async()=>{
 let sent='';
 const request=(async(url:string|URL|Request,init?:RequestInit)=>{
  const path=String(url);
  if(path.includes('webhook_claim'))return Response.json(true);
  if(path.includes('flymind_accounts'))return Response.json([{id:'account'}]);
  if(path.includes('course_grades'))return Response.json([
   {course_name:'zero',current_score:0},{course_name:'unknown',current_score:null},
   {course_name:'Физическая культура',current_score:50}]);
  if(path.includes('sendMessage')){sent+=JSON.parse(String(init?.body)).text;return Response.json({ok:true,result:{message_id:12}});}
  if(path.includes('webhook_updates'))return new Response(null,{status:204});
  throw new Error('unexpected');
 }) as typeof fetch;
 await handler(config,request)(req({...update,message:{...update.message,text:'/stats'}}));
 assert(sent.includes('zero: 0% (GPA 0)')&&sent.includes('unknown: без оценки'));
 assert(sent.includes('Физическая культура: 50% (GPA 1)')&&sent.includes('0.29 / 4.0')&&sent.includes('Не официальный'));
});
