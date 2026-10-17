import {escape,menu,command as parseCommand,deadlineView,localDate} from './views.ts';
import {manualPreflight} from './manual.ts';
/** Testable webhook core. No payloads, academic records or credentials are logged. */
export type Config = { secret: string; chat: string; user: string; bot: string; url: string; key: string; githubToken: string; repo: string; ref: string; observatory: string; manualEnabled?: boolean };
export function gradePoint(score: number): number {
  const cuts = [[95,4],[90,3.67],[85,3.33],[80,3],[75,2.67],[70,2.33],[65,2],[60,1.67],[55,1.33],[50,1]];
  return cuts.find(([cut]) => score >= cut)?.[1] ?? 0;
}
async function equalSecret(a: string,b: string) {
  const hash=async(s:string)=>new Uint8Array(await crypto.subtle.digest('SHA-256',new TextEncoder().encode(s)));
  const [x,y]=await Promise.all([hash(a),hash(b)]);let difference=0;
  for(let i=0;i<x.length;i++)difference|=x[i]^y[i];return difference===0;
}
export function handler(config: Config, request: typeof fetch = fetch) {
  const botId=config.bot.split(':')[0];
  const headers = {apikey:config.key,Authorization:`Bearer ${config.key}`,'Content-Type':'application/json'};
  const api=async(path:string,body?:unknown) => {
    const response=await request(`${config.url}/rest/v1/${path}`,{method:body===undefined?'GET':'POST',headers,body:body===undefined?undefined:JSON.stringify(body),signal:AbortSignal.timeout(10000)});
    if(!response.ok)throw new Error('database_unavailable');return response.json();
  };
  const telegram=async(method:string,payload:unknown) => {
    const response=await request(`https://api.telegram.org/bot${config.bot}/${method}`,{method:'POST',headers:{'Content-Type':'application/json'},body:JSON.stringify(payload),signal:AbortSignal.timeout(10000)});
    const result=await response.json();if(!response.ok||result.ok!==true)throw new Error('telegram_outcome_uncertain');return result;
  };
  const send=(text:string,keyboard?:unknown)=>telegram('sendMessage',{chat_id:config.chat,text,parse_mode:'HTML',reply_markup:keyboard});
  return async(req:Request):Promise<Response> => {
    if(req.method!=='POST')return new Response('Method not allowed',{status:405});
    if(!config.secret||!config.chat||!config.bot||!config.key||!config.url||!config.user||!/^\d+$/.test(botId))return new Response('Not configured',{status:503});
    if(!await equalSecret(req.headers.get('X-Telegram-Bot-Api-Secret-Token')??'',config.secret))return new Response('Forbidden',{status:403});
    let body;
    try {
      const reader=req.body?.getReader();if(!reader)return new Response('Invalid update',{status:400});
      let size=0;const chunks:Uint8Array[]=[];
      while(true){const {done,value}=await reader.read();if(done)break;size+=value.length;if(size>65536){await reader.cancel();return new Response('Too large',{status:413});}chunks.push(value);}
      const bytes=new Uint8Array(size);let offset=0;for(const c of chunks){bytes.set(c,offset);offset+=c.length;}
      body=JSON.parse(new TextDecoder().decode(bytes));
    } catch {return new Response('Invalid JSON',{status:400});}
    const message=body.message??body.callback_query?.message;
    const actor=body.callback_query?.from??body.message?.from;
    if(!Number.isSafeInteger(body.update_id)||body.update_id<0||String(message?.chat?.id)!==config.chat||String(actor?.id)!==config.user)return new Response('Forbidden',{status:403});
    let claimed=false;
    try {
      claimed=await api('rpc/flymind_webhook_claim',{p_bot:botId,p_chat:config.chat,p_user:config.user,p_update:body.update_id})===true;
      if(!claimed)return new Response('Already handled or account disabled');
      const command=parseCommand(String(body.message?.text??''));
      const accounts=await api(`flymind_accounts?select=id,canvas_origin&telegram_chat_id=eq.${encodeURIComponent(config.chat)}&telegram_bot_id=eq.${botId}&telegram_user_id=eq.${encodeURIComponent(config.user)}&enabled=eq.true&limit=1`);
      if(!accounts.length)throw new Error('account_not_configured');
      const account=accounts[0];
      const callback=body.callback_query?.data;
      if(body.callback_query){try{await telegram('answerCallbackQuery',{callback_query_id:body.callback_query.id});}catch{/* Independent of command execution. */}}
      if(command==='/start'||command==='/menu'||callback==='menu') {
        await send('FlyMind · Главное меню\nВыберите действие. Нейронный сигнал — экспериментальное дополнение к обычным уведомлениям.',menu);
      } else if(command==='/deadlines'||String(callback??'').startsWith('deadlines:')) {
        const match=/^deadlines:(upcoming|overdue|today|week|month|all|undated):(\d{1,5})$/.exec(callback??'');
        if(callback&&!match)throw new Error('invalid_deadline_view');
        const view=match?.[1]??'upcoming',page=Number(match?.[2]??0);
        const data=await api('rpc/flymind_deadlines',{p_account:account.id,p_view:view,p_page:page});
        const rendered=deadlineView(data,view,account.canvas_origin);
        if(callback&&message?.message_id)await telegram('editMessageText',{chat_id:config.chat,message_id:message.message_id,text:rendered.text,parse_mode:'HTML',reply_markup:rendered.keyboard,link_preview_options:{is_disabled:true}});
        else await send(rendered.text,rendered.keyboard);
      } else if(command==='/status'||callback==='status') {
        const health=(await api(`flymind_health?account_id=eq.${account.id}&limit=1`))[0];
        const recent=(await api(`flymind_manual_requests?account_id=eq.${account.id}&order=created_at.desc&limit=1`))[0];
        const age=health?.last_attempt?Date.now()-Date.parse(health.last_attempt):Infinity;
        const status=age>90*60000?'failed':age>30*60000?'delayed':health?.status??'unknown';
        await send(`⚙️ Состояние: ${escape(status)}\nУспешная синхронизация снимков: ${localDate(health?.last_snapshot_success)}\nTelegram: ${localDate(health?.last_telegram_success)}\nNeural: ${localDate(health?.last_neural_success)}\nОчередь: ${escape(JSON.stringify(health?.queue??{}).slice(0,600))}\nРучной запрос: ${escape(recent?.state??'нет')}\n${recent?.state==='running'?'Завершение workflow ещё не подтверждено.':''}`,{inline_keyboard:[[{text:'📅 Дедлайны',callback_data:'deadlines:upcoming:0'}]]});
      } else if(command==='/stats'||callback==='get_stats') {
        const grades=await api(`course_grades?select=course_name,current_score&user_id=eq.${encodeURIComponent(config.chat)}&limit=100`);
        let points=0,credits=0;const lines=['🎓 <b>Моя успеваемость</b>'];
        for(const row of grades){const name=String(row.course_name??'').slice(0,120),score=Number(row.current_score);if(name.toLowerCase().includes('practic'))continue;
          if(row.current_score===null||row.current_score===undefined||row.current_score===''||!Number.isFinite(score)){lines.push(`${escape(name)}: без оценки`);continue;}
          const physical=name.toLowerCase().includes('физическая культура'),weight=physical?2:5,gp=gradePoint(score);points+=gp*weight;credits+=weight;lines.push(`${escape(name)}: ${score}% (GPA ${gp})`);
        }
        // Cap each message without cutting an HTML entity or tag.
        const pages:string[]=[];let page='';for(const line of lines){if(page.length+line.length>3000){pages.push(page);page='';}page+=line+'\n';}pages.push(page+`\nОценочный GPA: ${credits?(points/credits).toFixed(2):'—'} / 4.0\nНе официальный транскрипт: предполагается 5 кредитов на курс, 2 для физкультуры.`);
        for(const text of pages)await send(text,{inline_keyboard:[[{text:'🔄 Обновить сейчас',callback_data:'force_refresh'}],[{text:'🧠 Neural Observatory',callback_data:'brain'}]]});
      } else if(command==='/brain'||callback==='brain') {
        const rows=accounts.length?await api(`flymind_experiments?select=created_at,metadata&account_id=eq.${accounts[0].id}&order=created_at.desc&limit=1`):[];
        const row=rows[0],r=row?.metadata?.readout;
        let text=row?`🧠 Последний запуск: ${escape(row.created_at)}\nЭкспериментальный сигнал: ${escape(r?.classification??row.metadata?.status)}\nБиологически не валидировано.`:'🧠 Сохранённых запусков пока нет.';
        if(/^https:\/\/[A-Za-z0-9.-]+(?::443)?(?:\/[^\s]*)?$/.test(config.observatory))text+=`\n<a href="${escape(config.observatory)}">Observatory — требуется вход</a>`;
        await send(text);
      } else if(command==='/check'||callback==='check'||callback==='force_refresh') {
        try {await manualPreflight(config,account.id,request);}catch {
          await send('Ручная синхронизация недоступна: проверьте разрешение ручного запуска, GitHub token, флаги worker, выбранную ветку и completion workflow. Запуск не выполнен.');
          return new Response('Configuration gate closed');
        }
        const pending=await api('rpc/flymind_manual_request',{p_account:account.id,p_bot:botId,p_update:body.update_id,p_ref:config.ref});
        if(!pending.accepted)await send(`Повторный запуск не создан. Состояние: ${escape(pending.state)}. Проверить ход можно через /status.`);
        else {
          let state='uncertain';
          try {
            const response=await request(`https://api.github.com/repos/${config.repo}/actions/workflows/check_canvas.yml/dispatches`,{method:'POST',headers:{Authorization:`Bearer ${config.githubToken}`,Accept:'application/vnd.github+json','Content-Type':'application/json'},body:JSON.stringify({ref:config.ref,inputs:{manual_request_id:pending.id}}),signal:AbortSignal.timeout(10000)});
            state=response.ok?'dispatched':response.status>=500?'uncertain':'failed';
          }catch{/* Dispatch may have been accepted. Never dispatch this request twice. */}
          const saved=await request(`${config.url}/rest/v1/flymind_manual_requests?id=eq.${pending.id}&account_id=eq.${account.id}&state=eq.queued`,{method:'PATCH',headers,body:JSON.stringify({state,error_code:state==='dispatched'?null:'dispatch_'+state}),signal:AbortSignal.timeout(10000)});
          if(!saved.ok)throw new Error('dispatch_state_unavailable');
          await send(state==='dispatched'?'Запрос принят GitHub Actions. Синхронизация ещё не завершена; результат придёт после завершения workflow.':state==='uncertain'?'Результат запроса запуска неизвестен. Он сохранён для проверки; повторный dispatch не выполняется. Состояние: /status.':'GitHub отклонил запуск. Проверьте настройку workflow и доступ; синхронизация не выполнена.');
        }
      } else await send('Выберите действие в меню или используйте /menu.',menu);
      const response=await request(`${config.url}/rest/v1/flymind_webhook_updates?bot_id=eq.${botId}&update_id=eq.${body.update_id}`,{method:'PATCH',headers,body:JSON.stringify({status:'done'}),signal:AbortSignal.timeout(10000)});
      if(!response.ok)throw new Error('ack_failed');
      return new Response('OK');
    } catch {
      // Once claimed, never blindly repeat side effects after a lost acknowledgement.
      // A durable claimed row is observable and requires operator reconciliation.
      return new Response(claimed?'Outcome requires review':'Unavailable',{status:claimed?200:503});
    }
  };
}
