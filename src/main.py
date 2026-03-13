import os
import sys
import httpx
import logging
from datetime import datetime, timezone, timedelta
from dotenv import load_dotenv

from canvasapi import Canvas
from supabase import create_client, Client

from src.core.scanner import CanvasScanner
from src.core.diff_engine import diff_objects, check_reminders, DiffType

logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(name)s - %(levelname)s - %(message)s')
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
    """Sends a text message using MarkdownV2."""
    if not TELEGRAM_BOT_TOKEN or not TELEGRAM_CHAT_ID:
        logger.warning("Telegram credentials not provided. Skipping message.")
        return

    url = f"https://api.telegram.org/bot{TELEGRAM_BOT_TOKEN}/sendMessage"
    payload = {
        "chat_id": TELEGRAM_CHAT_ID,
        "text": text,
        "parse_mode": "MarkdownV2"
    }
    
    try:
        response = httpx.post(url, json=payload, timeout=10.0)
        response.raise_for_status()
    except Exception as e:
        logger.error(f"Failed to send Telegram message: {e}")
        run_stats["errors"] += 1

def escape_markdown(text: str) -> str:
    """Escapes markdown v2 reserved characters."""
    if not text:
        return ""
    reserved = ['_', '*', '[', ']', '(', ')', '~', '`', '>', '#', '+', '-', '=', '|', '{', '}', '.', '!']
    for char in reserved:
        text = str(text).replace(char, f"\\{char}")
    return text

def convert_utc_to_local(utc_str: str) -> str:
    """Converts a Canvas UTC timestamp to localized Almaty/Tashkent string.
    Since pytz isn't strictly necessary with Python 3.9+ zoneinfo, we use basic offset roughly.
    Assuming +05:00 for Almaty/Tashkent."""
    if not utc_str:
        return "Unknown"
    try:
        utc_dt = datetime.fromisoformat(utc_str.replace("Z", "+00:00"))
        # Using fixed offset for Almaty/Tashkent (+5 UTC)
        from datetime import timezone, timedelta
        local_timezone = timezone(timedelta(hours=5))
        local_dt = utc_dt.astimezone(local_timezone)
        return local_dt.strftime("%d\\.%m\\.%Y %H:%M")
    except Exception:
        return escape_markdown(utc_str)

def process_assignments(scanner: CanvasScanner, user_id: int):
    try:
        live_assignments = scanner.fetch_all_assignments()
    except Exception as e:
        logger.error(f"Error fetching assignments: {e}")
        return

    # Fetch existing states
    try:
        response = scanner.supabase_client.table("canvas_state") \
            .select("*").eq("user_id", user_id).eq("object_type", "assignment").execute()
        saved_states = {item["object_id"]: item for item in response.data}
    except Exception as e:
        logger.error(f"Error fetching state from Supabase: {e}")
        return
        
    current_time = datetime.now(timezone.utc)

    for live in live_assignments:
        assignment_id = live.get("id")
        if not assignment_id:
            continue
            
        saved_record = saved_states.get(assignment_id)
        old_state = saved_record["state_data"] if saved_record else None
        
        # Check standard state updates
        diff = diff_objects(old_state, live, "assignment")
        
        if diff:
            run_stats["changes"] += 1
            if diff.diff_type == DiffType.NEW:
                msg = (f"📌 *{escape_markdown(live.get('name'))}*\n\n"
                       f"📅 *Дедлайн:* {convert_utc_to_local(live.get('due_at'))}\n"
                       f"💯 *Вес:* {escape_markdown(str(live.get('points_possible')))} points")
                send_telegram_message(msg)
                
            elif diff.diff_type == DiffType.UPDATED:
                msg = (f"📌 *Обновлено: {escape_markdown(live.get('name'))}*\n\n"
                       f"📅 *Дедлайн:* {convert_utc_to_local(live.get('due_at'))}\n"
                       f"💯 *Вес:* {escape_markdown(str(live.get('points_possible')))} points")
                send_telegram_message(msg)

        # Smart Reminders logic
        reminder_type = check_reminders(live, current_time)
        if reminder_type:
            # Check if this reminder was already sent
            last_reminder_type = saved_record.get("last_reminder_type") if saved_record else None
            
            if reminder_type != last_reminder_type:
                msg = (f"⚠️ *Напоминание {escape_markdown(reminder_type)}*\n\n"
                       f"📌 *{escape_markdown(live.get('name'))}*\n"
                       f"📅 *Дедлайн:* {convert_utc_to_local(live.get('due_at'))}")
                send_telegram_message(msg)
                
                # We need to save the reminder_type state
                live["_last_reminder_trigger"] = reminder_type
        
        # Save state if changed or reminder sent or new
        needs_saving = diff is not None or (reminder_type and reminder_type != (saved_record.get("last_reminder_type") if saved_record else None))
        
        if needs_saving:
            try:
                scanner.supabase_client.table("canvas_state").upsert({
                    "user_id": user_id,
                    "course_id": live.get("course_id", 0),
                    "object_type": "assignment",
                    "object_id": assignment_id,
                    "state_data": live,
                    "last_reminder_type": reminder_type if reminder_type else (saved_record.get("last_reminder_type") if saved_record else None)
                }).execute()
            except Exception as e:
                logger.error(f"Failed to upsert state for assignment {assignment_id}: {e}")

def process_files(scanner: CanvasScanner, user_id: int):
    try:
        live_files = scanner.fetch_all_files()
    except Exception as e:
        logger.error(f"Error fetching files: {e}")
        return

    try:
        response = scanner.supabase_client.table("canvas_state") \
            .select("*").eq("user_id", user_id).eq("object_type", "file").execute()
        saved_states = {item["object_id"]: item for item in response.data}
    except Exception as e:
        logger.error(f"Error fetching state from Supabase: {e}")
        return

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
                msg = (f"📁 *Новый файл загружен* 📁\n\n"
                       f"📚 *Курс ID:* {live.get('course_id')}\n"
                       f"📄 *Файл:* {escape_markdown(live.get('display_name'))}\n"
                       f"🔗 [Скачать]({escape_markdown(live.get('url'))})")
                send_telegram_message(msg)
                
            elif diff.diff_type == DiffType.UPDATED:
                msg = (f"🔄 *Файл обновлен* 🔄\n\n"
                       f"📄 *Файл:* {escape_markdown(live.get('display_name'))}\n"
                       f"🔗 [Скачать]({escape_markdown(live.get('url'))})")
                send_telegram_message(msg)

            try:
                scanner.supabase_client.table("canvas_state").upsert({
                    "user_id": user_id,
                    "course_id": live.get("course_id", 0),
                    "object_type": "file",
                    "object_id": file_id,
                    "state_data": live
                }).execute()
            except Exception as e:
                logger.error(f"Failed to upsert state for file {file_id}: {e}")

def process_announcements(scanner: CanvasScanner, user_id: int):
    try:
        live_announcements = scanner.fetch_all_announcements()
    except Exception as e:
        logger.error(f"Error fetching announcements: {e}")
        return

    try:
        response = scanner.supabase_client.table("canvas_state") \
            .select("*").eq("user_id", user_id).eq("object_type", "announcement").execute()
        saved_states = {item["object_id"]: item for item in response.data}
    except Exception as e:
        logger.error(f"Error fetching state from Supabase: {e}")
        return

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
                # clean up HTML tags out of message
                raw_message = live.get('message', '')
                clean_msg = re.sub('<[^<]+>', '', raw_message).strip()
                if len(clean_msg) > 500:
                    clean_msg = clean_msg[:500] + "..."
                    
                msg = (f"📢 *Новое Объявление* 📢\n\n"
                       f"👤 *От:* {escape_markdown(live.get('author_name'))}\n"
                       f"📌 *Тема:* {escape_markdown(live.get('title'))}\n\n"
                       f"{escape_markdown(clean_msg)}")
                send_telegram_message(msg)
                
            elif diff.diff_type == DiffType.UPDATED:
                msg = (f"✏️ *Обновление Объявления* ✏️\n\n"
                       f"📌 *Тема:* {escape_markdown(live.get('title'))}")
                send_telegram_message(msg)

            try:
                scanner.supabase_client.table("canvas_state").upsert({
                    "user_id": user_id,
                    "course_id": 0,
                    "object_type": "announcement",
                    "object_id": ann_id,
                    "state_data": live
                }).execute()
            except Exception as e:
                logger.error(f"Failed to upsert state for announcement {ann_id}: {e}")

def process_health_check(supabase, user_id: int):
    # Check last health check timestamp
    try:
        response = supabase.table("health_checks").select("*").eq("user_id", user_id).order("created_at", desc=True).limit(1).execute()
        
        should_run = False
        if not response.data:
            should_run = True # first time
        else:
            last_run_str = response.data[0].get("created_at")
            if last_run_str:
                last_run = datetime.fromisoformat(last_run_str.replace("Z", "+00:00"))
                if (datetime.now(timezone.utc) - last_run).total_seconds() > 168 * 3600: # 168 hours = 1 week
                    should_run = True
            else:
                should_run = True
                
        if should_run:
            # Aggregate changes over the last 168 hours from health_checks to get actual week statistics
            week_ago = (datetime.now(timezone.utc) - timedelta(days=7)).isoformat()
            
            # Since we record 'errors' and 'changes' per run in health_checks (we'll save every run's stats but only notify weekly),
            # let's modify the approach: We save run stats in a separate `run_logs` or just emit the weekly summary based on the delta.
            # To keep to the user's specs without adding new tables, we can query `canvas_state` for updated_at > week_ago for [X]
            
            changes_res = supabase.table("canvas_state") \
                .select("id", count="exact") \
                .eq("user_id", user_id) \
                .gte("updated_at", week_ago) \
                .execute()
                
            total_week_changes = changes_res.count if hasattr(changes_res, 'count') and changes_res.count is not None else len(changes_res.data)
            
            msg = (f"🤖 *Health Check*\n\n"
                   f"Бот работает стабильно\\.\n"
                   f"За неделю отслежено {total_week_changes} изменений\\.\n"
                   f"Ошибок связи в текущей сессии: {run_stats['errors']}")
            send_telegram_message(msg)
            
            supabase.table("health_checks").insert({
                "user_id": user_id,
                "total_changes": total_week_changes,
                "total_errors": run_stats["errors"]
            }).execute()
            logger.info("Weekly health check sent.")
            
    except Exception as e:
        logger.error(f"Failed to process health check: {e}")


def main():
    print("--- Проверка переменных ---")
    missing = []
    
    if CANVAS_URL:
        print("CANVAS_API_URL — OK")
    else:
        print("CANVAS_API_URL — MISSING")
        missing.append("CANVAS_API_URL")
        
    if CANVAS_TOKEN:
        print("CANVAS_API_KEY — OK")
    else:
        print("CANVAS_API_KEY — MISSING")
        missing.append("CANVAS_API_KEY")
        
    if SUPABASE_URL:
        print("SUPABASE_URL — OK")
    else:
        print("SUPABASE_URL — MISSING")
        missing.append("SUPABASE_URL")
        
    if SUPABASE_KEY:
        print("SUPABASE_SERVICE_KEY — OK")
    else:
        print("SUPABASE_SERVICE_KEY — MISSING")
        missing.append("SUPABASE_SERVICE_KEY")
        
    if TELEGRAM_BOT_TOKEN:
        print("TELEGRAM_BOT_TOKEN — OK")
    else:
        print("TELEGRAM_BOT_TOKEN — MISSING")
        missing.append("TELEGRAM_BOT_TOKEN")
        
    if TELEGRAM_CHAT_ID:
        print("TELEGRAM_CHAT_ID — OK")
    else:
        print("TELEGRAM_CHAT_ID — MISSING")
        missing.append("TELEGRAM_CHAT_ID")
        
    print("---------------------------")

    if missing:
        logger.error(f"Missing critical environment variables: {', '.join(missing)}")
        sys.exit(0)  # Exit gracefully for cron

    try:
        user_id = int(TELEGRAM_CHAT_ID)
    except ValueError:
        logger.error("TELEGRAM_CHAT_ID must be a numeric ID.")
        sys.exit(0)

    try:
        canvas = Canvas(CANVAS_URL, CANVAS_TOKEN)
        # Verify connection
        canvas.get_current_user()
    except Exception as e:
        logger.error(f"Canvas API connection failed: {e}")
        sys.exit(0)

    try:
        supabase: Client = create_client(SUPABASE_URL, SUPABASE_KEY)
    except Exception as e:
        logger.error(f"Supabase connection failed: {e}")
        sys.exit(0)
        
    scanner = CanvasScanner(canvas, supabase)
    
    # Process assignments
    process_assignments(scanner, user_id)
    
    # Process files
    process_files(scanner, user_id)
    
    # Process announcements
    process_announcements(scanner, user_id)
    
    # Process health check
    process_health_check(supabase, user_id)

if __name__ == "__main__":
    main()
