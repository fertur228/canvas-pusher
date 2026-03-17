import os
import sys
import httpx
import logging
import asyncio
from datetime import datetime, timezone, timedelta
from dotenv import load_dotenv

from supabase import create_client, Client

from src.core.scanner import AsyncCanvasScanner
from src.core.diff_engine import diff_objects, check_reminders, DiffType
from src.core.gpa_engine import calculate_gpa, get_grade_point

logging.basicConfig(level=logging.INFO, format='%(message)s') # Keep it clean
logger = logging.getLogger(__name__)

# Basic in-memory stats for the current run
run_stats = {
    "changes": 0,
    "errors": 0
}

# Load environment variables
load_dotenv()

CANVAS_URL = os.getenv("CANVAS_API_URL")
CANVAS_TOKEN = os.getenv("CANVAS_API_KEY")
SUPABASE_URL = os.getenv("SUPABASE_URL")
SUPABASE_KEY = os.getenv("SUPABASE_SERVICE_KEY", os.getenv("SUPABASE_KEY"))
TELEGRAM_BOT_TOKEN = os.getenv("TELEGRAM_BOT_TOKEN")
TELEGRAM_CHAT_ID = os.getenv("TELEGRAM_CHAT_ID")

def send_telegram_message(text: str):
    """Sends a text message using HTML."""
    if not TELEGRAM_BOT_TOKEN or not TELEGRAM_CHAT_ID:
        return

    url = f"https://api.telegram.org/bot{TELEGRAM_BOT_TOKEN}/sendMessage"
    payload = {
        "chat_id": TELEGRAM_CHAT_ID,
        "text": text,
        "parse_mode": "HTML"
    }
    
    try:
        response = httpx.post(url, json=payload, timeout=10.0)
        response.raise_for_status()
    except Exception as e:
        logger.error(f"Failed to send Telegram message: {e}")
        run_stats["errors"] += 1

def send_welcome_message():
    if not TELEGRAM_BOT_TOKEN or not TELEGRAM_CHAT_ID:
        return
    url = f"https://api.telegram.org/bot{TELEGRAM_BOT_TOKEN}/sendMessage"
    
    keyboard = {
        "inline_keyboard": [[
            {"text": "📊 Мой GPA", "callback_data": "get_stats"}
        ]]
    }
    
    payload = {
        "chat_id": TELEGRAM_CHAT_ID,
        "text": "Привет! Я Canvas Pusher.\nЯ буду присылать обновления и напоминания о дедлайнах.\n\nНажми кнопку ниже или напиши /stats, чтобы узнать свой текущий GPA.",
        "reply_markup": keyboard
    }
    try:
        httpx.post(url, json=payload, timeout=10.0)
    except Exception:
        pass

async def check_telegram_updates(user_id: int) -> bool:
    """Checks for /stats command or callback query in the last 5 minutes."""
    if not TELEGRAM_BOT_TOKEN:
        return False
        
    url = f"https://api.telegram.org/bot{TELEGRAM_BOT_TOKEN}/getUpdates"
    stats_requested = False
    
    try:
        async with httpx.AsyncClient(timeout=10.0) as client:
            response = await client.get(url)
            if response.status_code == 200:
                updates = response.json().get("result", [])
                current_time = datetime.now(timezone.utc).timestamp()
                
                for update in updates:
                    message = update.get("message")
                    callback = update.get("callback_query")
                    
                    if message and message.get("chat", {}).get("id") == user_id:
                        msg_time = message.get("date", 0)
                        if current_time - msg_time < 300: # 5 minutes
                            text = message.get("text", "")
                            if text == "/start":
                                send_welcome_message()
                            elif text == "/stats":
                                stats_requested = True
                                
                    if callback and callback.get("message", {}).get("chat", {}).get("id") == user_id:
                        msg_time = callback.get("message", {}).get("date", 0)
                        if current_time - msg_time < 300: # 5 minutes
                            data = callback.get("data", "")
                            if data == "get_stats":
                                stats_requested = True
                                cb_id = callback.get("id")
                                await client.get(f"https://api.telegram.org/bot{TELEGRAM_BOT_TOKEN}/answerCallbackQuery", params={"callback_query_id": cb_id})
                                
    except Exception as e:
        logger.error(f"Failed to fetch Telegram updates: {e}")

    return stats_requested

def save_course_grades(supabase: Client, user_id: int, active_courses: list):
    grades_to_upsert = []
    for course in active_courses:
        course_score = None
        for enr in course.get("enrollments", []):
            if enr.get("type") == "student":
                course_score = enr.get("computed_current_score")
                break
                
        grades_to_upsert.append({
            "user_id": user_id,
            "course_id": course.get('id'),
            "course_name": course.get('name', 'Unknown Course'),
            "current_score": course_score
        })
        
    if grades_to_upsert:
        try:
            supabase.table("course_grades").upsert(grades_to_upsert).execute()
        except Exception as e:
            logger.error(f"Failed to upsert course grades: {e}")

def send_stats_report(supabase: Client, user_id: int):
    try:
        response = supabase.table("course_grades").select("*").eq("user_id", user_id).execute()
        grades = response.data
    except Exception as e:
        logger.error(f"Failed to fetch course grades: {e}")
        return

    if not grades:
        send_telegram_message("Не удалось найти текущие оценки. Подождите пару минут.")
        return

    course_scores = {}
    html_lines = ["🎓 <b>Моя успеваемость</b>\n"]
    
    for grade in grades:
        cname = grade.get("course_name")
        score = grade.get("current_score") or 0.0
        course_scores[cname] = float(score)
        
        if "Физическая культура" in cname:
            html_lines.append(f"🏃‍♂️ <b>{escape_html(cname)}</b>: Зачет (4.0)")
        else:
            gp = get_grade_point(score)
            html_lines.append(f"📘 <b>{escape_html(cname)}</b>: {score}% (GPA: {gp})")
            
    total_gpa = calculate_gpa(course_scores)
    html_lines.append(f"\n🏆 <b>Итоговый GPA: {total_gpa} / 4.0</b>")
    
    send_telegram_message("\n".join(html_lines))

def escape_html(text: str) -> str:
    """Escapes HTML reserved characters for Telegram HTML parse mode."""
    import html
    return html.escape(str(text)) if text is not None else ""

def convert_utc_to_local(utc_str: str) -> str:
    """Converts a Canvas UTC timestamp to localized Almaty/Tashkent string."""
    if not utc_str:
        return "Не установлен"
    try:
        utc_dt = datetime.fromisoformat(utc_str.replace("Z", "+00:00"))
        local_timezone = timezone(timedelta(hours=5))
        local_dt = utc_dt.astimezone(local_timezone)
        return local_dt.strftime("%d.%m.%Y %H:%M")
    except Exception:
        return "Уточняйте в Canvas"

def process_assignments(supabase: Client, user_id: int, live_assignments: list):
    try:
        response = supabase.table("canvas_state") \
            .select("*").eq("user_id", user_id).eq("object_type", "assignment").execute()
        saved_states = {item["object_id"]: item for item in response.data}
    except Exception as e:
        logger.error(f"Error fetching state from Supabase: {e}")
        return
        
    current_time = datetime.now(timezone.utc)

    states_to_upsert = []
    for live in live_assignments:
        assignment_id = live.get("id")
        if not assignment_id:
            continue
            
        saved_record = saved_states.get(assignment_id)
        old_state = saved_record["state_data"] if saved_record else None
        
        diff = diff_objects(old_state, live, "assignment")
        
        if diff:
            run_stats["changes"] += 1
            
            score = live.get("score")
            points = live.get("points_possible")
            course_score = live.get("course_score")
            
            score_str = f" | ⭐ <b>Оценка:</b> {escape_html(score)}" if score is not None else ""
            course_score_str = f"\n📈 <b>Общая оценка:</b> {escape_html(course_score)}%" if course_score is not None else ""
            
            if diff.diff_type == DiffType.NEW:
                msg = (f"📌 <b>{escape_html(live.get('name'))}</b>\n\n"
                       f"📚 <b>Дисциплина:</b> {escape_html(live.get('course_name'))}\n"
                       f"📅 <b>Дедлайн:</b> {convert_utc_to_local(live.get('due_at'))}\n"
                       f"💯 <b>Вес:</b> {escape_html(points)} points{score_str}"
                       f"{course_score_str}")
                send_telegram_message(msg)
                
            elif diff.diff_type == DiffType.UPDATED:
                msg = (f"📌 <b>Обновлено: {escape_html(live.get('name'))}</b>\n\n"
                       f"📚 <b>Дисциплина:</b> {escape_html(live.get('course_name'))}\n"
                       f"📅 <b>Дедлайн:</b> {convert_utc_to_local(live.get('due_at'))}\n"
                       f"💯 <b>Вес:</b> {escape_html(points)} points{score_str}"
                       f"{course_score_str}")
                send_telegram_message(msg)
                
            elif diff.diff_type == DiffType.UPDATED_GRADE:
                score_display = f"{score} / {points}" if points is not None else str(score)
                msg = (f"🔔 <b>НОВАЯ ОЦЕНКА!</b> 🔔\n\n"
                       f"📚 <b>Дисциплина:</b> {escape_html(live.get('course_name'))}\n"
                       f"📝 <b>Задание:</b> {escape_html(live.get('name'))}\n"
                       f"⭐ <b>Балл:</b> {escape_html(score_display)}"
                       f"{course_score_str}")
                send_telegram_message(msg)

        reminder_type = check_reminders(live, current_time)
        if reminder_type:
            last_reminder_type = saved_record.get("last_reminder_type") if saved_record else None
            
            if reminder_type != last_reminder_type:
                msg = (f"⚠️ <b>Напоминание {escape_html(reminder_type)}</b>\n\n"
                       f"📌 <b>{escape_html(live.get('name'))}</b>\n"
                       f"📚 <b>Дисциплина:</b> {escape_html(live.get('course_name'))}\n"
                       f"📅 <b>Дедлайн:</b> {convert_utc_to_local(live.get('due_at'))}")
                send_telegram_message(msg)
                live["_last_reminder_trigger"] = reminder_type
        
        needs_saving = diff is not None or (reminder_type and reminder_type != (saved_record.get("last_reminder_type") if saved_record else None))
        
        if needs_saving:
            payload = {
                "user_id": user_id,
                "course_id": live.get("course_id", 0),
                "course_name": live.get("course_name", "Unknown Course"),
                "object_type": "assignment",
                "object_id": assignment_id,
                "state_data": live,
                "last_reminder_type": reminder_type if reminder_type else (saved_record.get("last_reminder_type") if saved_record else None)
            }
            if saved_record and "id" in saved_record:
                payload["id"] = saved_record["id"]
            states_to_upsert.append(payload)

    if states_to_upsert:
        try:
            supabase.table("canvas_state").upsert(states_to_upsert).execute()
        except Exception as e:
            logger.error(f"Failed to batch upsert state for assignments: {e}")

def process_files(supabase: Client, user_id: int, live_files: list):
    try:
        response = supabase.table("canvas_state") \
            .select("*").eq("user_id", user_id).eq("object_type", "file").execute()
        saved_states = {item["object_id"]: item for item in response.data}
    except Exception as e:
        logger.error(f"Error fetching state from Supabase: {e}")
        return

    states_to_upsert = []
    for live in live_files:
        file_id = live.get("id")
        if not file_id:
            continue
            
        saved_record = saved_states.get(file_id)
        old_state = saved_record["state_data"] if saved_record else None
        
        diff = diff_objects(old_state, live, "file")
        
        if diff:
            run_stats["changes"] += 1
            if diff.diff_type == DiffType.NEW:
                msg = (f"📁 <b>Новый файл загружен</b> 📁\n\n"
                       f"📚 <b>Дисциплина:</b> {escape_html(live.get('course_name'))}\n"
                       f"📄 <b>Файл:</b> {escape_html(live.get('display_name'))}\n"
                       f"🔗 <a href='{escape_html(live.get('url'))}'>Скачать</a>")
                send_telegram_message(msg)
                
            elif diff.diff_type == DiffType.UPDATED:
                msg = (f"🔄 <b>Файл обновлен</b> 🔄\n\n"
                       f"📄 <b>Файл:</b> {escape_html(live.get('display_name'))}\n"
                       f"🔗 <a href='{escape_html(live.get('url'))}'>Скачать</a>")
                send_telegram_message(msg)

            payload = {
                "user_id": user_id,
                "course_id": live.get("course_id", 0),
                "course_name": live.get("course_name", "Unknown Course"),
                "object_type": "file",
                "object_id": file_id,
                "state_data": live
            }
            if saved_record and "id" in saved_record:
                payload["id"] = saved_record["id"]
            states_to_upsert.append(payload)

    if states_to_upsert:
        try:
            supabase.table("canvas_state").upsert(states_to_upsert).execute()
        except Exception as e:
            logger.error(f"Failed to batch upsert state for files: {e}")

def process_announcements(supabase: Client, user_id: int, live_announcements: list):
    try:
        response = supabase.table("canvas_state") \
            .select("*").eq("user_id", user_id).eq("object_type", "announcement").execute()
        saved_states = {item["object_id"]: item for item in response.data}
    except Exception as e:
        logger.error(f"Error fetching state from Supabase: {e}")
        return

    states_to_upsert = []
    for live in live_announcements:
        ann_id = live.get("id")
        if not ann_id:
            continue
            
        saved_record = saved_states.get(ann_id)
        old_state = saved_record["state_data"] if saved_record else None
        
        diff = diff_objects(old_state, live, "announcement")
        
        if diff:
            run_stats["changes"] += 1
            if diff.diff_type == DiffType.NEW:
                import re
                raw_message = live.get('message', '')
                clean_msg = re.sub('<[^<]+>', '', raw_message).strip()
                if len(clean_msg) > 500:
                    clean_msg = clean_msg[:500] + "..."
                    
                msg = (f"📢 <b>Новое Объявление</b> 📢\n\n"
                       f"📚 <b>Дисциплина:</b> {escape_html(live.get('course_name'))}\n"
                       f"👤 <b>От:</b> {escape_html(live.get('author_name'))}\n"
                       f"📌 <b>Тема:</b> {escape_html(live.get('title'))}\n\n"
                       f"{escape_html(clean_msg)}")
                send_telegram_message(msg)
                
            elif diff.diff_type == DiffType.UPDATED:
                msg = (f"✏️ <b>Обновление Объявления</b> ✏️\n\n"
                       f"📌 <b>Тема:</b> {escape_html(live.get('title'))}")
                send_telegram_message(msg)

            payload = {
                "user_id": user_id,
                "course_id": 0,
                "course_name": live.get("course_name", "Unknown Course"),
                "object_type": "announcement",
                "object_id": ann_id,
                "state_data": live
            }
            if saved_record and "id" in saved_record:
                payload["id"] = saved_record["id"]
            states_to_upsert.append(payload)

    if states_to_upsert:
        try:
            supabase.table("canvas_state").upsert(states_to_upsert).execute()
        except Exception as e:
            logger.error(f"Failed to batch upsert state for announcements: {e}")

def process_health_check(supabase: Client, user_id: int):
    try:
        response = supabase.table("health_checks").select("*").eq("user_id", user_id).order("created_at", desc=True).limit(1).execute()
        
        should_run = False
        if not response.data:
            should_run = True # first time
        else:
            last_run_str = response.data[0].get("created_at")
            if last_run_str:
                last_run = datetime.fromisoformat(last_run_str.replace("Z", "+00:00"))
                if (datetime.now(timezone.utc) - last_run).total_seconds() > 168 * 3600:
                    should_run = True
            else:
                should_run = True
                
        if should_run:
            week_ago = (datetime.now(timezone.utc) - timedelta(days=7)).isoformat()
            
            changes_res = supabase.table("canvas_state") \
                .select("id", count="exact") \
                .eq("user_id", user_id) \
                .gte("updated_at", week_ago) \
                .execute()
                
            total_week_changes = changes_res.count if hasattr(changes_res, 'count') and changes_res.count is not None else len(changes_res.data)
            
            msg = (f"🤖 <b>Health Check</b>\n\n"
                   f"Бот работает стабильно.\n"
                   f"За неделю отслежено {total_week_changes} изменений.\n"
                   f"Ошибок связи в текущей сессии: {run_stats['errors']}")
            send_telegram_message(msg)
            
            supabase.table("health_checks").insert({
                "user_id": user_id,
                "total_changes": total_week_changes,
                "total_errors": run_stats["errors"]
            }).execute()
            
    except Exception as e:
        logger.error(f"Failed to process health check: {e}")

async def async_main():
    missing = []
    if not CANVAS_URL: missing.append("CANVAS_API_URL")
    if not CANVAS_TOKEN: missing.append("CANVAS_API_KEY")
    if not SUPABASE_URL: missing.append("SUPABASE_URL")
    if not SUPABASE_KEY: missing.append("SUPABASE_SERVICE_KEY")
    if not TELEGRAM_BOT_TOKEN: missing.append("TELEGRAM_BOT_TOKEN")
    if not TELEGRAM_CHAT_ID: missing.append("TELEGRAM_CHAT_ID")

    if missing:
        logger.error(f"Missing critical environment variables: {', '.join(missing)}")
        sys.exit(0)

    try:
        user_id = int(TELEGRAM_CHAT_ID)
    except ValueError:
        logger.error("TELEGRAM_CHAT_ID must be a numeric ID.")
        sys.exit(0)

    try:
        supabase: Client = create_client(SUPABASE_URL, SUPABASE_KEY)
    except Exception as e:
        logger.error(f"Supabase connection failed: {e}")
        sys.exit(0)
        
    start_time = datetime.now()
    
    stats_requested = await check_telegram_updates(user_id)
    
    scanner = AsyncCanvasScanner(CANVAS_TOKEN, CANVAS_URL, supabase)
    active_courses = await scanner.get_active_courses()
    
    if not active_courses:
        logger.info("No active courses found. Exiting.")
        sys.exit(0)
        
    save_course_grades(supabase, user_id, active_courses)
        
    all_assignments, all_files, all_announcements = await scanner.scan_all(active_courses)
    
    process_assignments(supabase, user_id, all_assignments)
    process_files(supabase, user_id, all_files)
    process_announcements(supabase, user_id, all_announcements)
    process_health_check(supabase, user_id)
    
    if stats_requested or os.getenv("IS_AUTO_REPORT") == "true":
        send_stats_report(supabase, user_id)
    
    duration = (datetime.now() - start_time).total_seconds()
    logger.info(f"Run completed in {duration:.2f}s. Changes: {run_stats['changes']}, Errors: {run_stats['errors']}")

def main():
    asyncio.run(async_main())

if __name__ == "__main__":
    main()
