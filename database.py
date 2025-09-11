import psycopg2
from psycopg2 import sql
import config
import datetime

def get_db_connection():
    try:
        conn = psycopg2.connect(
            host=config.PG_HOST,
            port=config.PG_PORT,
            database=config.PG_DATABASE,
            user=config.PG_USER,
            password=config.PG_PASSWORD
        )
        return conn
    except psycopg2.Error as e:
        print(f"Ошибка подключения к базе данных: {e}")
        return None

def init_db():
    conn = get_db_connection()
    if conn:
        try:
            cur = conn.cursor()

            cur.execute("""
                CREATE TABLE IF NOT EXISTS support_requests (
                    id SERIAL PRIMARY KEY,
                    user_id BIGINT NOT NULL,
                    username VARCHAR(255),
                    full_name VARCHAR(255),
                    description TEXT NOT NULL,
                    status VARCHAR(50) DEFAULT 'Открыт',
                    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                    assigned_to BIGINT,
                    resolved_at TIMESTAMP
                );
            """)

            cur.execute("""
                CREATE TABLE IF NOT EXISTS faq (
                    id SERIAL PRIMARY KEY,
                    question TEXT NOT NULL,
                    answer TEXT NOT NULL,
                    category VARCHAR(255),
                    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
                );
            """)

            cur.execute("""
                CREATE TABLE IF NOT EXISTS users (
                    id BIGINT PRIMARY KEY,
                    username VARCHAR(255),
                    first_name VARCHAR(255),
                    last_name VARCHAR(255),
                    is_admin BOOLEAN DEFAULT FALSE,
                    registered_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
                );
            """)
            
            cur.execute("""
                CREATE TABLE IF NOT EXISTS schedule (
                    id INT PRIMARY KEY DEFAULT 1,
                    schedule_text TEXT,
                    updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
                );
            """)
            
            cur.execute("""
                CREATE TABLE IF NOT EXISTS support_messages (
                    id SERIAL PRIMARY KEY,
                    request_id INTEGER NOT NULL REFERENCES support_requests(id) ON DELETE CASCADE,
                    sender_id BIGINT NOT NULL,
                    sender_name VARCHAR(255),
                    sender_type VARCHAR(10) NOT NULL, -- 'user' or 'admin'
                    message_text TEXT NOT NULL,
                    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
                );
            """)

            conn.commit()
            print("База данных инициализирована успешно.")
        except psycopg2.Error as e:
            print(f"Ошибка при инициализации базы данных: {e}")
        finally:
            cur.close()
            conn.close()

def add_support_request(user_id, username, full_name, description):
    conn = get_db_connection()
    if conn:
        try:
            cur = conn.cursor()
            cur.execute(
                """
                INSERT INTO support_requests (user_id, username, full_name, description)
                VALUES (%s, %s, %s, %s) RETURNING id;
                """,
                (user_id, username, full_name, description)
            )
            request_id = cur.fetchone()[0]
            conn.commit()
            return request_id
        except psycopg2.Error as e:
            print(f"Ошибка при добавлении запроса в техподдержку: {e}")
            conn.rollback()
            return None
        finally:
            cur.close()
            conn.close()
            
def add_support_message(request_id, sender_id, sender_name, sender_type, message_text):
    """Добавляет сообщение в историю переписки по запросу."""
    conn = get_db_connection()
    if conn:
        try:
            cur = conn.cursor()
            cur.execute(
                """
                INSERT INTO support_messages (request_id, sender_id, sender_name, sender_type, message_text)
                VALUES (%s, %s, %s, %s, %s);
                """,
                (request_id, sender_id, sender_name, sender_type, message_text)
            )
            conn.commit()
        except psycopg2.Error as e:
            print(f"Ошибка при добавлении сообщения в историю: {e}")
            conn.rollback()
        finally:
            cur.close()
            conn.close()

def get_messages_for_request(request_id):
    """Возвращает все сообщения для конкретного запроса."""
    conn = get_db_connection()
    if conn:
        try:
            cur = conn.cursor()
            cur.execute(
                """
                SELECT sender_name, sender_type, message_text, created_at
                FROM support_messages WHERE request_id = %s ORDER BY created_at ASC;
                """,
                (request_id,)
            )
            return cur.fetchall()
        except psycopg2.Error as e:
            print(f"Ошибка при получении истории сообщений: {e}")
            return []
        finally:
            cur.close()
            conn.close()
            
def get_user_support_requests(user_id):
    conn = get_db_connection()
    if conn:
        try:
            cur = conn.cursor()
            cur.execute(
                """
                SELECT id, description, status, created_at FROM support_requests
                WHERE user_id = %s ORDER BY created_at DESC;
                """,
                (user_id,)
            )
            requests = cur.fetchall()
            return requests
        except psycopg2.Error as e:
            print(f"Ошибка при получении запросов пользователя: {e}")
            return []
        finally:
            cur.close()
            conn.close()

def get_all_faq_items():
    conn = get_db_connection()
    if conn:
        try:
            cur = conn.cursor()
            cur.execute("SELECT question, answer FROM faq ORDER BY id;")
            faq_items = cur.fetchall()
            return faq_items
        except psycopg2.Error as e:
            print(f"Ошибка при получении FAQ: {e}")
            return []
        finally:
            cur.close()
            conn.close()

def get_all_support_requests():
    conn = get_db_connection()
    if conn:
        try:
            cur = conn.cursor()
            cur.execute(
                """
                SELECT id, user_id, username, full_name, description, status, created_at
                FROM support_requests ORDER BY created_at DESC;
                """
            )
            requests = cur.fetchall()
            return requests
        except psycopg2.Error as e:
            print(f"Ошибка при получении всех запросов: {e}")
            return []
        finally:
            cur.close()
            conn.close()

def get_new_support_requests(minutes_threshold=10):
    conn = get_db_connection()
    if conn:
        try:
            cur = conn.cursor()
            time_threshold = datetime.datetime.now() - datetime.timedelta(minutes=minutes_threshold)
            cur.execute(
                """
                SELECT id, user_id, username, full_name, description, status, created_at
                FROM support_requests
                WHERE created_at >= %s AND status = 'Открыт'
                ORDER BY created_at ASC;
                """,
                (time_threshold,)
            )
            requests = cur.fetchall()
            return requests
        except psycopg2.Error as e:
            print(f"Ошибка при получении новых запросов: {e}")
            return []
        finally:
            cur.close()
            conn.close()

def get_support_request_by_id(request_id):
    conn = get_db_connection()
    if conn:
        try:
            cur = conn.cursor()
            cur.execute(
                """
                SELECT id, user_id, username, full_name, description, status, created_at
                FROM support_requests WHERE id = %s;
                """,
                (request_id,)
            )
            request = cur.fetchone()
            return request
        except psycopg2.Error as e:
            print(f"Ошибка при получении запроса по ID: {e}")
            return None
        finally:
            cur.close()
            conn.close()

def update_support_request_status(request_id, new_status, admin_id=None):
    conn = get_db_connection()
    if conn:
        try:
            cur = conn.cursor()
            if new_status == 'Решен':
                cur.execute(
                    """
                    UPDATE support_requests SET status = %s, assigned_to = %s, resolved_at = CURRENT_TIMESTAMP
                    WHERE id = %s;
                    """,
                    (new_status, admin_id, request_id)
                )
            else:
                cur.execute(
                    """
                    UPDATE support_requests SET status = %s, assigned_to = %s
                    WHERE id = %s;
                    """,
                    (new_status, admin_id, request_id)
                )
            conn.commit()
            return True
        except psycopg2.Error as e:
            print(f"Ошибка при обновлении статуса запроса: {e}")
            conn.rollback()
            return False
        finally:
            cur.close()
            conn.close()

def add_or_update_user(user_id, username, first_name, last_name, is_admin=False):
    conn = get_db_connection()
    if conn:
        try:
            cur = conn.cursor()
            cur.execute(
                """
                INSERT INTO users (id, username, first_name, last_name, is_admin)
                VALUES (%s, %s, %s, %s, %s)
                ON CONFLICT (id) DO UPDATE SET
                    username = EXCLUDED.username,
                    first_name = EXCLUDED.first_name,
                    last_name = EXCLUDED.last_name,
                    is_admin = EXCLUDED.is_admin;
                """,
                (user_id, username, first_name, last_name, is_admin)
            )
            conn.commit()
            return True
        except psycopg2.Error as e:
            print(f"Ошибка при добавлении/обновлении пользователя: {e}")
            conn.rollback()
            return False
        finally:
            cur.close()
            conn.close()

def update_schedule(schedule_text):
    conn = get_db_connection()
    if conn:
        try:
            cur = conn.cursor()
            cur.execute(
                """
                INSERT INTO schedule (id, schedule_text, updated_at)
                VALUES (1, %s, CURRENT_TIMESTAMP)
                ON CONFLICT (id) DO UPDATE SET
                    schedule_text = EXCLUDED.schedule_text,
                    updated_at = EXCLUDED.updated_at;
                """,
                (schedule_text,)
            )
            conn.commit()
            return True
        except psycopg2.Error as e:
            print(f"Ошибка при обновлении расписания: {e}")
            conn.rollback()
            return False
        finally:
            cur.close()
            conn.close()

def get_schedule():
    conn = get_db_connection()
    if conn:
        try:
            cur = conn.cursor()
            cur.execute("SELECT schedule_text FROM schedule WHERE id = 1;")
            result = cur.fetchone()
            return result[0] if result else None
        except psycopg2.Error as e:
            print(f"Ошибка при получении расписания: {e}")
            return None
        finally:
            cur.close()
            conn.close()