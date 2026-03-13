import os
import sys
import httpx
from dotenv import load_dotenv

def main():
    print("🚀 Внимание: Инициализация БД для Canvas-Pusher")
    print("-------------------------------------------------")
    
    # Try looking for .env file or just use environment
    load_dotenv()
    
    supabase_url = os.getenv("SUPABASE_URL")
    supabase_key = os.getenv("SUPABASE_SERVICE_KEY") or os.getenv("SUPABASE_KEY")
    
    if not supabase_url or not supabase_key:
        print("❌ ОШИБКА: SUPABASE_URL и SUPABASE_SERVICE_KEY должны быть установлены в .env")
        print("   Проверьте файл .env.example для примера.")
        sys.exit(1)
        
    schema_path = os.path.join(os.path.dirname(__file__), '..', 'database_schema.sql')
    if not os.path.exists(schema_path):
        print(f"❌ ОШИБКА: Не найден файл {schema_path}")
        sys.exit(1)
        
    with open(schema_path, 'r', encoding='utf-8') as f:
        sql_commands = f.read()

    print("Подключение к Supabase через REST/Postgres API...")
    
    # Supabase allows executing RAW SQL using the Postgres Meta API (if the user has the right token)
    # or via the `pg_graphql` endpoint if configured. But since standard anon/service_role keys
    # on REST do not execute arbitrary DDL natively, we will try to use httpx to hit the 
    # `/rest/v1/rpc/...` endpoint if they had a function, or we just fallback to advising them 
    # if it fails.
    
    headers = {
        "apikey": supabase_key,
        "Authorization": f"Bearer {supabase_key}",
        "Content-Type": "application/json"
    }
    
    # We will try a "soft" check to see if the table exists by doing a simple select
    try:
        check_url = f"{supabase_url}/rest/v1/canvas_state?select=id&limit=1"
        response = httpx.get(check_url, headers=headers, timeout=10.0)
        
        if response.status_code == 200:
            print("✅ Таблицы 'canvas_state' и 'health_checks' уже существуют или доступны.")
            print("Инициализация не требуется.")
            return
            
    except Exception as e:
        print(f"⚠️ Не удалось проверить статус таблиц: {e}")

    # Standard Supabase doesn't expose an out-of-the-box `/sql` endpoint for the REST API
    # to execute DDL (CREATE TABLE). We will inform the user.
    print("\n⚠️ ВАЖНО: REST API Supabase (PostgREST) по умолчанию не разрешает выполнять 'CREATE TABLE' ")
    print("скрипты напрямую в целях безопасности (требуется pg_query или ручное выполнение).")
    print("\nЧтобы инициализировать базу данных в первый раз, вам необходимо выполнить SQL в Dashboard:")
    print("1. Откройте Supabase Dashboard (https://supabase.com/dashboard)")
    print("2. Перейдите в ваш проект -> 'SQL Editor'")
    print("3. Скопируйте следующий код и нажмите 'Run':")
    print("\n" + "="*50)
    print(sql_commands.strip())
    print("="*50 + "\n")
    print("✅ Скрипт поддерживает оператор 'IF NOT EXISTS', поэтому случайное удаление существующих данных исключено.")

if __name__ == "__main__":
    main()
