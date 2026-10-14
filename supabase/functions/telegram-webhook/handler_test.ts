import {handler, type Config} from './handler.ts';
const config:Config={secret:'test-secret',chat:'123',user:'123',bot:'test-bot',url:'https://db.invalid',key:'test-key',githubToken:'',repo:'',ref:'main',observatory:'https://observatory.invalid'};
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
 if(path.includes('course_grades'))return Response.json([{course_name:'<private&course>',current_score:95}]);
 if(path.includes('sendMessage')){sent=JSON.parse(String(init?.body)).text;return Response.json({ok:true,result:{message_id:12}});}
 if(path.includes('webhook_updates')){ack=true;return new Response(null,{status:204});}
 throw new Error('unexpected');
 }) as typeof fetch;
 assert((await handler(config,request)(req({...update,message:{...update.message,text:'/stats'}}))).status===200);
 assert(sent.includes('&lt;private&amp;course&gt;')&&!sent.includes('<private&course>')&&ack);
});
