import { serve } from "https://deno.land/std@0.168.0/http/server.ts"
import { createClient } from "https://esm.sh/@supabase/supabase-js@2.39.0"

const corsHeaders = {
  'Access-Control-Allow-Origin': '*',
  'Access-Control-Allow-Headers': 'authorization, x-client-info, apikey, content-type',
  'Access-Control-Allow-Methods': 'POST, OPTIONS'
}

// Environment Variables
const TELEGRAM_BOT_TOKEN = Deno.env.get("TELEGRAM_BOT_TOKEN") || ""
const SUPABASE_URL = Deno.env.get("SUPABASE_URL") || ""
const SUPABASE_SERVICE_ROLE_KEY = Deno.env.get("SUPABASE_SERVICE_ROLE_KEY") || ""
const GITHUB_PAT = Deno.env.get("GITHUB_PAT") || ""
const GITHUB_REPO = Deno.env.get("GITHUB_REPO") || "" 
const TELEGRAM_CHAT_ID = Deno.env.get("TELEGRAM_CHAT_ID") || ""

console.log("[Init] Edge Function Boot. Envs Check:", {
  hasTelegram: !!TELEGRAM_BOT_TOKEN,
  hasSupabaseUrl: !!SUPABASE_URL,
  hasSupabaseKey: !!SUPABASE_SERVICE_ROLE_KEY,
  hasGitHubPAT: !!GITHUB_PAT,
  repo: GITHUB_REPO
})

const supabase = createClient(SUPABASE_URL, SUPABASE_SERVICE_ROLE_KEY)

function getGradePoint(percentage: number): number {
  if (percentage == null || isNaN(percentage)) return 0.0;
  if (percentage >= 95.0) return 4.0;
  if (percentage >= 90.0) return 3.67;
  if (percentage >= 85.0) return 3.33;
  if (percentage >= 80.0) return 3.0;
  if (percentage >= 75.0) return 2.67;
  if (percentage >= 70.0) return 2.33;
  if (percentage >= 65.0) return 2.0;
  if (percentage >= 60.0) return 1.67;
  if (percentage >= 55.0) return 1.33;
  if (percentage >= 50.0) return 1.0;
  return 0.0;
}

function calculateGpa(courseScores: Record<string, number>): number {
  let totalPoints = 0.0;
  let totalCredits = 0;

  for (const [courseName, score] of Object.entries(courseScores)) {
    let credits = 5;
    let gradePoint = 0.0;

    if (courseName.toLowerCase().includes("физическая культура")) {
      credits = 2;
      gradePoint = 4.0; 
    } else {
      gradePoint = getGradePoint(score);
    }

    totalPoints += gradePoint * credits;
    totalCredits += credits;
  }

  if (totalCredits === 0) return 0.0;
  return Number((totalPoints / totalCredits).toFixed(2));
}

async function sendTelegramMessage(chatId: number, text: string, replyMarkup?: any) {
  console.log(`[Telegram] Sending message to ${chatId}...`);
  const url = `https://api.telegram.org/bot${TELEGRAM_BOT_TOKEN}/sendMessage`;
  const payload: any = {
    chat_id: chatId,
    text: text,
    parse_mode: 'HTML'
  };
  
  if (replyMarkup) {
    payload.reply_markup = replyMarkup;
  }

  const res = await fetch(url, {
    method: 'POST',
    headers: { 'Content-Type': 'application/json' },
    body: JSON.stringify(payload)
  });
  
  const resText = await res.text();
  console.log(`[Telegram] Response: ${res.status} | Body: ${resText}`);
}

async function handleStatsRequest(chatId: number) {
  console.log(`[App] Handling /stats for User ID: ${chatId}`);
  
  console.log(`[DB] Fetching course_grades...`);
  const { data: grades, error } = await supabase
    .from('course_grades')
    .select('*')
    .eq('user_id', chatId);

  if (error) {
    console.error("[DB] Supabase Fetch Error:", error);
    await sendTelegramMessage(chatId, "❌ Ошибка базы данных при получении оценок.");
    return;
  }
  
  console.log(`[DB] Fetched ${grades?.length || 0} grades.`);

  const inlineKeyboard = {
    inline_keyboard: [
      [{ text: "🔄 Обновить сейчас", callback_data: "force_refresh" }]
    ]
  };

  if (!grades || grades.length === 0) {
    await sendTelegramMessage(
      chatId, 
      "Не удалось найти оценки. Возможно, бот еще ни разу не успел их скачать из Canvas. Нажмите 'Обновить сейчас'.",
      inlineKeyboard
    );
    return;
  }

  const courseScores: Record<string, number> = {};
  let htmlText = "🎓 <b>Моя успеваемость</b>\n\n";

  for (const grade of grades) {
    const cname = grade.course_name;
    const score = parseFloat(grade.current_score) || 0.0;

    // Filter 0% scores (unstarted or ungraded courses)
    if (score === 0.0) {
      console.log(`[App] Ignoring ${cname}: Score is 0%`);
      htmlText += `📘 <b>${cname}</b>: без оценки\n`;
      continue;
    }

    // Filter out "Practic" / "Practice" subjects
    if (cname.toLowerCase().includes("practic")) {
      console.log(`[App] Ignoring ${cname}: Contains 'Practic'`);
      continue;
    }

    courseScores[cname] = score;

    if (cname.toLowerCase().includes("физическая культура")) {
      htmlText += `🏃‍♂️ <b>${cname}</b>: Зачет (4.0)\n`;
    } else {
      const gp = getGradePoint(score);
      htmlText += `📘 <b>${cname}</b>: ${score}% (GPA: ${gp})\n`;
    }
  }

  const totalGpa = calculateGpa(courseScores);
  htmlText += `\n🏆 <b>Итоговый GPA: ${totalGpa} / 4.0</b>`;

  console.log(`[App] Computed GPA: ${totalGpa}. Sending report...`);
  await sendTelegramMessage(chatId, htmlText, inlineKeyboard);
}

async function triggerGitHubWorkflow(chatId: number) {
  console.log(`[App] Triggering GitHub Workflow for Repo: ${GITHUB_REPO}`);
  if (!GITHUB_PAT || !GITHUB_REPO) {
    console.error("[App] Missing GitHub PAT or Repo ENV.");
    await sendTelegramMessage(chatId, "❌ Ошибка: Не настроен токен GitHub.");
    return;
  }

  const url = `https://api.github.com/repos/${GITHUB_REPO}/actions/workflows/check_canvas.yml/dispatches`;
  const response = await fetch(url, {
    method: 'POST',
    headers: {
      'Authorization': `Bearer ${GITHUB_PAT}`,
      'Accept': 'application/vnd.github.v3+json',
      'Content-Type': 'application/json',
      'User-Agent': 'Supabase-Edge-Function'
    },
    body: JSON.stringify({ 
      ref: 'main', 
      inputs: { chat_id: chatId.toString() } 
    })
  });

  if (response.ok) {
    console.log(`[GitHub] Workflow dispatched successfully! HTTP 2xx`);
    await sendTelegramMessage(chatId, "🚀 <b>Синхронизация запущена!</b>\nПарсер собирает новые данные из Canvas вне очереди. Обновленные данные появятся примерно через минуту.");
  } else {
    const errText = await response.text();
    console.error(`[GitHub] API Error: ${response.status}`, errText);
    await sendTelegramMessage(chatId, "❌ Не удалось запустить принудительное обновление GitHub Actions.");
  }
}

serve(async (req) => {
  // CORS Preflight
  if (req.method === 'OPTIONS') {
    return new Response('ok', { headers: corsHeaders })
  }

  try {
    if (req.method !== 'POST') {
      console.warn(`[HTTP] Method Not Allowed: ${req.method}`);
      return new Response('Method Not Allowed', { status: 405, headers: corsHeaders });
    }

    const bodyText = await req.text();
    console.log(`[HTTP] Incoming POST Payload:`, bodyText);
    
    // Parse JSON safely
    let body;
    try {
      body = JSON.parse(bodyText);
    } catch(e) {
      console.error("[HTTP] Invalid JSON Payload!");
      return new Response('Bad Request', { status: 400, headers: corsHeaders });
    }

    let incomingChatId = null;
    if (body.message && body.message.chat) {
      incomingChatId = body.message.chat.id;
    } else if (body.callback_query && body.callback_query.message && body.callback_query.message.chat) {
      incomingChatId = body.callback_query.message.chat.id;
    }

    if (incomingChatId !== null && TELEGRAM_CHAT_ID) {
      if (incomingChatId.toString() !== TELEGRAM_CHAT_ID) {
        console.warn(`[Auth] Unauthorized access attempt from ID: ${incomingChatId}`);
        await sendTelegramMessage(incomingChatId, "❌ Доступ запрещен. Это приватный бот.");
        return new Response(JSON.stringify({ error: 'Unauthorized' }), { status: 403, headers: corsHeaders });
      }
    }
    
    // 1. Text Messages (e.g. /stats)
    if (body.message && body.message.text) {
      const chatId = body.message.chat.id;
      const text = body.message.text.trim();
      console.log(`[Telegram] Received Message '${text}' from Chat ID: ${chatId}`);
      
      if (text === '/stats' || text === '/start') {
        await handleStatsRequest(chatId);
      }
    }
    
    // 2. Button Clicks (Callback Queries)
    if (body.callback_query) {
      const callbackData = body.callback_query.data;
      const chatId = body.callback_query.message.chat.id;
      const callbackQueryId = body.callback_query.id;
      
      console.log(`[Telegram] Received Callback '${callbackData}' from Chat ID: ${chatId}`);
      
      // Stop the spinning loader on the button
      const ansUrl = `https://api.telegram.org/bot${TELEGRAM_BOT_TOKEN}/answerCallbackQuery`;
      console.log(`[Telegram] Answering CallbackQueryId: ${callbackQueryId}`);
      try {
        await fetch(ansUrl, {
          method: 'POST',
          headers: { 'Content-Type': 'application/json' },
          body: JSON.stringify({ callback_query_id: callbackQueryId })
        });
      } catch (e) {
        console.error("[Telegram] Failed to answerCallbackQuery:", e);
      }
      
      if (callbackData === 'get_stats') {
        await handleStatsRequest(chatId);
      } else if (callbackData === 'force_refresh') {
        await triggerGitHubWorkflow(chatId);
      } else {
        console.warn(`[Telegram] Unknown callback data: ${callbackData}`);
      }
    }

    return new Response(JSON.stringify({ ok: true }), { 
      status: 200, 
      headers: { ...corsHeaders, 'Content-Type': 'application/json' } 
    })
  } catch (error) {
    console.error('[HTTP] Unhandled Error in serve block:', error);
    return new Response(JSON.stringify({ error: 'Internal Server Error' }), { 
      status: 500, 
      headers: { ...corsHeaders, 'Content-Type': 'application/json' } 
    });
  }
});
