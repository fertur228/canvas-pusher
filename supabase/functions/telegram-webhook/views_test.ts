import {deadlineView,localDate,command} from './views.ts';
function assert(x:unknown){if(!x)throw new Error('assertion failed');}
Deno.test('Almaty timezone crosses UTC date; overdue and missing dates are explicit',()=>{
 assert(localDate('2026-10-14T20:00:00Z').includes('15.10.2026'));
 assert(localDate('2026-10-14T20:00:00Z').includes('01:00'));
 const result=deadlineView({synced_at:'2026-10-14T18:00:00Z',stale:true,total:2,rows:[{name:'<bad&>',course_name:'<course>',due_at:'2026-10-14T18:00:00Z',points_possible:100,html_url:'https://canvas.invalid/assignment?a=1&b=2'},{name:'No deadline',due_at:null}]},'all','https://canvas.invalid',Date.parse('2026-10-14T19:00:00Z'));
 assert(result.text.includes('&lt;bad&amp;&gt;')&&!result.text.includes('<bad&>'));
 assert(result.text.includes('просрочено')&&result.text.includes('не установлен')&&result.text.includes('старше 30 минут'));
 assert(result.text.includes('Открыть в Canvas')&&result.text.includes('Последняя успешная синхронизация'));
});
Deno.test('maximum escaped titles and links stay inside Telegram length; navigation preserves filter',()=>{
 const rows=Array.from({length:3},()=>({name:'&'.repeat(1000),course_name:'&'.repeat(1000),due_at:'2026-10-14T18:00:00Z',html_url:'https://canvas.invalid/'+ '&'.repeat(5000)}));
 const result=deadlineView({synced_at:'2026-10-14T18:00:00Z',rows,total:100,page:2,invalid_deadlines:1},'week','https://canvas.invalid');
 assert(result.text.length<4096&&!result.text.includes('href='));
 const buttons=result.keyboard.inline_keyboard.flat();assert(buttons.some(b=>b.callback_data==='deadlines:week:1')&&buttons.some(b=>b.callback_data==='deadlines:week:3'));
});
Deno.test('unsafe URLs rejected and menu aliases resolve exactly',()=>{
 const result=deadlineView({synced_at:'2026-10-14T18:00:00Z',total:1,rows:[{name:'Task',html_url:'https://evil.invalid/steal'}]},'undated','https://canvas.invalid');
 assert(!result.text.includes('href='));
 assert(command('🔄 Check Canvas Now')==='/check'&&command('/deadlines@bot')==='/deadlines');
});
