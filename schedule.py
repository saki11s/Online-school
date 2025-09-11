from telebot import types
import re
import modules.database as db

ADMIN_STATE_AWAITING_SCHEDULE_TEXT = 5

def get_manage_schedule_menu():
    """Возвращает меню управления расписанием для администратора."""
    markup = types.InlineKeyboardMarkup(row_width=1)
    btn_update_schedule = types.InlineKeyboardButton("Обновить/Задать расписание", callback_data="admin_schedule_update")
    btn_back_to_admin = types.InlineKeyboardButton("⬅️ Назад в Админ-панель", callback_data="admin_back_to_main")
    markup.add(btn_update_schedule, btn_back_to_admin)
    return markup

def show_manage_schedule_panel(bot, chat_id, message_id):
    """Показывает панель управления расписанием."""
    bot.edit_message_text(
        chat_id=chat_id,
        message_id=message_id,
        text="🗓️ **Управление расписанием**\n\nЗдесь вы можете задать расписание на неделю.",
        reply_markup=get_manage_schedule_menu(),
        parse_mode="Markdown"
    )

def start_schedule_update_flow(bot, chat_id, admin_states):
    """Начинает процесс обновления расписания."""
    template = (
        "Пожалуйста, отправьте полное расписание на неделю одним сообщением.\n\n"
        "**Используйте строгий шаблон:**\n"
        "```\n"
        "Понедельник:\n"
        "10:00 - Предмет 1\n\n"
        "Вторник:\n"
        "11:00 - Предмет 2\n"
        "...\n"
        "```\n\n"
        "**Правила:**\n"
        "1. Название дня недели с большой буквы и с двоеточием.\n"
        "2. Пустая строка между днями."
    )
    bot.send_message(chat_id, template, parse_mode="Markdown")
    admin_states[chat_id] = ADMIN_STATE_AWAITING_SCHEDULE_TEXT

def process_schedule_update(message, bot, admin_states):
    """Обрабатывает и сохраняет новое расписание."""
    schedule_text = message.text
    if db.update_schedule(schedule_text):
        bot.send_message(message.chat.id, "✅ Расписание успешно обновлено!")
    else:
        bot.send_message(message.chat.id, "❌ Произошла ошибка при обновлении расписания.")
    
    admin_states[message.chat.id] = 0

def parse_schedule_for_day(full_text, day_name):
    """Ищет и возвращает расписание на конкретный день."""
    if not full_text:
        return None
        
    pattern = re.compile(f"^{re.escape(day_name)}:(.*?)(?=\n\n\w+:|$)", re.DOTALL | re.MULTILINE)
    match = pattern.search(full_text)
    
    if match:
        schedule_for_day = match.group(1).strip()
        return schedule_for_day if schedule_for_day else "На этот день занятий не найдено."
    return "На этот день занятий не найдено."