/** Pure, bounded Telegram views. Stored model data and cached academic data stay distinct. */
export const escape = (x: unknown) => String(x ?? '').replace(/[&<>"']/g, c => ({'&':'&amp;','<':'&lt;','>':'&gt;','"':'&quot;',"'":'&#39;'}[c]!));
export const menu = {keyboard:[[{text:'📅 Deadlines'},{text:'🔄 Check Canvas Now'}],[{text:'📊 My Grades'},{text:'🧠 Fly Brain'}],[{text:'⚙️ System Status'}]],resize_keyboard:true,is_persistent:true};
export const labels:Record<string,string>={upcoming:'Предстоящие',overdue:'Просроченные',today:'Сегодня',week:'7 дней',month:'30 дней',all:'Все несданные',undated:'Без дедлайна'};
export function command(text:string):string {
 const aliases:Record<string,string>={'📅 Deadlines':'/deadlines','🔄 Check Canvas Now':'/check','📊 My Grades':'/stats','🧠 Fly Brain':'/brain','⚙️ System Status':'/status'};
 return aliases[text]??text.trim().split(/\s+/)[0].split('@')[0].toLowerCase();
}
export function localDate(value:unknown):string {
 const d=new Date(String(value??''));
 return Number.isFinite(d.getTime())?new Intl.DateTimeFormat('ru-RU',{timeZone:'Asia/Almaty',dateStyle:'short',timeStyle:'short',hourCycle:'h23'}).format(d)+' (Asia/Almaty)':'—';
}
export function remaining(value:unknown,now:number):string {
 const diff=new Date(String(value)).getTime()-now;
 if(!Number.isFinite(diff))return 'не указан';
 const minutes=Math.ceil(Math.abs(diff)/60000),days=Math.floor(minutes/1440),hours=Math.floor(minutes%1440/60);
 return `${diff<0?'просрочено на':'осталось'} ${days} д ${hours} ч ${minutes%60} мин`;
}
export function deadlineView(data:any,view:string,origin:string,now=Date.now()) {
 const page=Number(data.page)||0,total=Number(data.total)||0;
 const keyboard:any[][]=[['upcoming','overdue','today'].map(k=>({text:labels[k],callback_data:`deadlines:${k}:0`})),['week','month','all','undated'].map(k=>({text:labels[k],callback_data:`deadlines:${k}:0`}))];
 let text=`📅 <b>${escape(labels[view])}</b>\nПоследняя успешная синхронизация: ${localDate(data.synced_at)}\n`;
 if(!data.synced_at)text+='Ещё не синхронизировано. Список заданий пока недоступен.';
 else {
  if(data.stale)text+='⚠️ Снимок старше 30 минут; данные могут быть устаревшими.\n';
  if(data.invalid_deadlines)text+='⚠️ Есть некорректные даты; такие записи не включены в датированные списки.\n';
  if(!data.rows?.length)text+='В этом разделе последнего проверенного снимка заданий нет.';
  for(const row of (data.rows??[]).slice(0,3)) {
   let card=`\n<b>${escape(String(row.name??'Задание').slice(0,70))}</b>\n${escape(String(row.course_name??'Курс').slice(0,45))}\nДедлайн: ${row.due_at?localDate(row.due_at):'не установлен'}\n${row.due_at?remaining(row.due_at,now)+'\n':''}Статус: не сдано`;
   if(typeof row.points_possible==='number'&&Number.isFinite(row.points_possible))card+=` · Баллы: ${row.points_possible}`;
   try {const url=new URL(row.html_url);if(url.protocol==='https:'&&url.origin===origin&&!url.username&&!url.password){const link=`\n<a href="${escape(url.href)}">Открыть в Canvas</a>`;if(card.length+link.length<1050)card+=link;}}catch{/* Optional API-provided link is absent/malformed. */}
   text+=card+'\n';
  }
  text+=`\nСтраница ${page+1}/${Math.max(1,Math.ceil(total/3))} · Заданий: ${total}`;
 }
 const nav=[];if(page>0)nav.push({text:'←',callback_data:`deadlines:${view}:${page-1}`});if((page+1)*3<total)nav.push({text:'→',callback_data:`deadlines:${view}:${page+1}`});if(nav.length)keyboard.push(nav);
 keyboard.push([{text:'🔄 Check Canvas Now',callback_data:'check'},{text:'Меню',callback_data:'menu'}]);
 return {text,keyboard:{inline_keyboard:keyboard}};
}
