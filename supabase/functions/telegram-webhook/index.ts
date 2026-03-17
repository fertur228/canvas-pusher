import { serve } from "https://deno.land/std@0.168.0/http/server.ts"
import { createClient } from "https://esm.sh/@supabase/supabase-js@2.39.0"

// Environment Variables
const TELEGRAM_BOT_TOKEN = Deno.env.get("TELEGRAM_BOT_TOKEN") || ""
const SUPABASE_URL = Deno.env.get("SUPABASE_URL") || ""
const SUPABASE_SERVICE_ROLE_KEY = Deno.env.get("SUPABASE_SERVICE_ROLE_KEY") || ""
const GITHUB_PAT = Deno.env.get("GITHUB_PAT") || ""
const GITHUB_REPO = Deno.env.get("GITHUB_REPO") || "" // Example: "fertur228/canvas-pusher"

// Init Supabase Client with Admin privileges to read tables
const supabase = createClient(SUPABASE_URL, SUPABASE_SERVICE_ROLE_KEY)

// ---------------------------------------------
// GPA Calculator Logic (Narxoz Scale)
// ---------------------------------------------
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

// ---------------------------------------------
// Telegram Interactions
// ---------------------------------------------
async function sendTelegramMessage(chatId: number, text: string, replyMarkup?: any) {
  const url = `https://api.telegram.org/bot${TELEGRAM_BOT_TOKEN}/sendMessage`;
  const payload: any = {
    chat_id: chatId,
    text: text,
    parse_mode: 'HTML'
  };
  
  if (replyMarkup) {
    payload.reply_markup = replyMarkup;
  }

  await fetch(url, {
    method: 'POST',
    headers: { 'Content-Type': 'application/json' },
    body: JSON.stringify(payload)
  });
}

// ---------------------------------------------
// Actions Handlers
// ---------------------------------------------
async function handleStatsRequest(chatId: number) {
  // Fetch from the fastest source - Supabase course_grades
  const { data: grades, error } = await supabase
    .from('course_grades')
    .select('*')
    .eq('user_id', chatId);

  if (error || !grades || grades.length === 0) {
    await sendTelegramMessage(
      chatId, 
      "Не удалось найти оценки. Возможно, бот еще ни разу не успел их скачать из Canvas. Нажмите 'Обновить сейчас'."
    );
    return;
  }

  const courseScores: Record<string, number> = {};
  let htmlText = "🎓 <b>Моя успеваемость</b>\n\n";

  for (const grade of grades) {
    const cname = grade.course_name;
    const score = parseFloat(grade.current_score) || 0.0;
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

  // Provide interactive button to force refresh via GH Actions
  const inlineKeyboard = {
    inline_keyboard: [
      [{ text: "🔄 Обновить сейчас", callback_data: "force_refresh" }]
    ]
  };

  await sendTelegramMessage(chatId, htmlText, inlineKeyboard);
}

async function triggerGitHubWorkflow(chatId: number) {
  if (!GITHUB_PAT || !GITHUB_REPO) {
    await sendTelegramMessage(chatId, "❌ Ошибка: Не настроен токен GitHub.");
    return;
  }

  const url = `https://api.github.com/repos/${GITHUB_REPO}/actions/workflows/check_canvas.yml/dispatches`;
  const response = await fetch(url, {
    method: 'POST',
    headers: {
      'Authorization': `Bearer ${GITHUB_PAT}`,
      'Accept': 'application/vnd.github.v3+json',
      'Content-Type': 'application/json'
    },
    body: JSON.stringify({ ref: 'main' })
  });

  if (response.ok) {
    await sendTelegramMessage(chatId, "🚀 <b>Синхронизация запущена!</b>\nПарсер собирает новые данные из Canvas вне очереди. Обновленные данные появятся примерно через минуту.");
  } else {
    const errText = await response.text();
    console.error("GitHub API Error:", errText);
    await sendTelegramMessage(chatId, "❌ Не удалось запустить принудительное обновление GitHub Actions.");
  }
}

// ---------------------------------------------
// Webhook Server
// ---------------------------------------------
serve(async (req) => {
  try {
    if (req.method !== 'POST') {
      return new Response('Method Not Allowed', { status: 405 });
    }

    const body = await req.json();
    
    // 1. Text Messages (e.g. /stats)
    if (body.message && body.message.text) {
      const chatId = body.message.chat.id;
      const text = body.message.text.trim();
      
      if (text === '/stats' || text === '/start') {
        await handleStatsRequest(chatId);
      }
    }
    
    // 2. Button Clicks (Callback Queries)
    if (body.callback_query) {
      const callbackData = body.callback_query.data;
      const chatId = body.callback_query.message.chat.id;
      const callbackQueryId = body.callback_query.id;
      
      // Stop the spinning loader on the button
      await fetch(`https://api.telegram.org/bot${TELEGRAM_BOT_TOKEN}/answerCallbackQuery`, {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({ callback_query_id: callbackQueryId })
      });
      
      if (callbackData === 'get_stats') {
        await handleStatsRequest(chatId);
      } else if (callbackData === 'force_refresh') {
        await triggerGitHubWorkflow(chatId);
      }
    }

    return new Response('OK', { status: 200 })
  } catch (error) {
    console.error('Error handling request:', error);
    return new Response('Internal Server Error', { status: 500 });
  }
});
