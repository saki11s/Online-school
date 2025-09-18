from telebot import types
from telebot.apihelper import ApiTelegramException
import config
import modules.database as db
import modules.support as support_module
import re

ADMIN_STATE_NONE = 0
ADMIN_STATE_MANAGE_REQUESTS = 1
ADMIN_STATE_AWAITING_ANSWER_TEXT = 2
ADMIN_STATE_AWAITING_FAQ_QUESTION = 3
ADMIN_STATE_AWAITING_FAQ_ANSWER = 4
ADMIN_STATE_AWAITING_BULK_FAQ_TEXT = 6
ADMIN_STATE_AWAITING_GROUP_NAME = 7


admin_states = {}
admin_current_request_id = {}
admin_current_faq_question = {}
admin_current_message_to_edit = {}

def is_admin(user_id):
    return user_id in config.ADMIN_IDS

def get_admin_main_menu():
    markup = types.InlineKeyboardMarkup(row_width=1)
    btn_manage_requests = types.InlineKeyboardButton("Управление запросами ТП", callback_data="admin_manage_requests")
    btn_manage_faq = types.InlineKeyboardButton("Управление FAQ", callback_data="admin_manage_faq")
    btn_manage_schedule = types.InlineKeyboardButton("Управление расписанием", callback_data="admin_manage_schedule")
    btn_manage_classes = types.InlineKeyboardButton("Управление классами", callback_data="admin_manage_classes")
    btn_back_to_main = types.InlineKeyboardButton("⬅️ Главное меню (Пользователь)", callback_data="back_to_main")
    markup.add(btn_manage_requests, btn_manage_faq, btn_manage_schedule, btn_manage_classes, btn_back_to_main)
    return markup

def show_admin_panel(bot, chat_id, message_id, user_id):
    if not is_admin(user_id):
        bot.send_message(chat_id, "У вас нет прав администратора.")
        return
    
    try:
        bot.edit_message_text(
            chat_id=chat_id,
            message_id=message_id,
            text="⚙️ **Админ-панель**\nВыберите действие:",
            reply_markup=get_admin_main_menu(),
            parse_mode="Markdown"
        )
    except Exception:
        bot.send_message(chat_id, "⚙️ **Админ-панель**\nВыберите действие:", reply_markup=get_admin_main_menu(), parse_mode="Markdown")

    admin_states[chat_id] = ADMIN_STATE_NONE
    
def get_manage_requests_menu():
    markup = types.InlineKeyboardMarkup(row_width=1)
    btn_view_new = types.InlineKeyboardButton("Показать новые запросы", callback_data="admin_view_new_requests")
    btn_view_all = types.InlineKeyboardButton("Показать все запросы", callback_data="admin_view_all_requests")
    btn_delete_one = types.InlineKeyboardButton("🗑️ Удалить запрос по ID", callback_data="admin_delete_request_menu")
    btn_delete_all = types.InlineKeyboardButton("⚠️ Очистить ВСЕ запросы", callback_data="admin_confirm_delete_all")
    btn_back = types.InlineKeyboardButton("⬅️ Назад в Админ-панель", callback_data="admin_back_to_main")
    markup.add(btn_view_new, btn_view_all, btn_delete_one, btn_delete_all, btn_back)
    return markup

def show_requests_list(message, bot, is_new_requests=False):
    chat_id = message.chat.id
    
    if is_new_requests:
        requests = db.get_new_support_requests()
        title = "🆕 **Новые запросы:**\n"
    else:
        requests = db.get_all_support_requests()
        title = "📊 **Все запросы в техподдержку:**\n"

    if not requests:
        markup = types.InlineKeyboardMarkup()
        btn_back = types.InlineKeyboardButton("⬅️ Назад к управлению запросами", callback_data="admin_manage_requests")
        markup.add(btn_back)
        bot.send_message(chat_id, f"На данный момент нет {'новых' if is_new_requests else ''} запросов.", reply_markup=markup)
        return

    markup = types.InlineKeyboardMarkup(row_width=1)
    for req_id, user_id, username, full_name, description, status, created_at in requests:
        short_desc = description[:50] + "..." if len(description) > 50 else description
        button_text = f"#{req_id} | {full_name} ({status}): {short_desc}"
        markup.add(types.InlineKeyboardButton(button_text, callback_data=f"admin_view_request_details_{req_id}"))
    
    markup.add(types.InlineKeyboardButton("⬅️ Назад к управлению запросами", callback_data="admin_manage_requests"))
    
    bot.send_message(chat_id, title + "\nВыберите запрос для просмотра:", reply_markup=markup, parse_mode="Markdown")
    admin_states[chat_id] = ADMIN_STATE_MANAGE_REQUESTS

def show_request_details_for_admin(bot, chat_id, message_id, request_id):
    request_data = db.get_support_request_by_id(request_id)

    if not request_data:
        bot.send_message(chat_id, f"Запрос с ID #{request_id} не найден.")
        return

    req_id, user_id, username, full_name, description, status, created_at = request_data

    history = db.get_messages_for_request(req_id)
    history_text = "\n\n**📜 История переписки:**\n"
    if history:
        for sender_name, sender_type, msg_text, msg_time in history:
            sender_prefix = "👤 Пользователь" if sender_type == 'user' else "⚙️ Админ"
            history_text += f"_{msg_time.strftime('%d.%m %H:%M')}_ | **{sender_prefix} ({sender_name})**:\n{msg_text}\n\n"
    else:
        history_text += "_Переписки еще нет._"


    details_text = (
        f"📋 **Детали запроса #{req_id}**\n\n"
        f"**От пользователя:** {full_name} (@{username if username else 'нет'}) (ID: `{user_id}`)\n"
        f"**Дата/Время:** {created_at.strftime('%d.%m.%Y %H:%M')}\n"
        f"**Статус:** `{status}`"
        f"{history_text}"
    )

    markup = types.InlineKeyboardMarkup(row_width=2)
    
    if status == 'Открыт':
        markup.add(types.InlineKeyboardButton("▶️ Взять в работу", callback_data=f"admin_change_status_Изучаем проблему_{req_id}"))
    elif status == 'Изучаем проблему':
        markup.add(types.InlineKeyboardButton("✅ Решить (Решен)", callback_data=f"admin_change_status_Решен_{req_id}"))
    
    markup.add(types.InlineKeyboardButton("💬 Ответить пользователю", callback_data=f"admin_start_answer_{req_id}"))
    markup.add(types.InlineKeyboardButton("⬅️ Назад к списку запросов", callback_data="admin_manage_requests"))
    
    try:
        bot.edit_message_text(
            chat_id=chat_id,
            message_id=message_id,
            text=details_text,
            reply_markup=markup,
            parse_mode="Markdown"
        )
    except Exception:
        bot.send_message(chat_id, details_text, reply_markup=markup, parse_mode="Markdown")

    admin_states[chat_id] = ADMIN_STATE_MANAGE_REQUESTS
    admin_current_message_to_edit[chat_id] = message_id

def start_answer_flow_from_details(message, bot, request_id):
    chat_id = message.chat.id
    admin_current_request_id[chat_id] = request_id
    admin_current_message_to_edit[chat_id] = message.message_id
    bot.send_message(chat_id, f"Введите ваш ответ на запрос #{request_id} для пользователя:")
    admin_states[chat_id] = ADMIN_STATE_AWAITING_ANSWER_TEXT

def process_admin_answer(message, bot):
    chat_id = message.chat.id
    admin_id = message.from_user.id
    admin_name = f"{message.from_user.first_name} {message.from_user.last_name or ''}".strip()
    request_id = admin_current_request_id.get(chat_id)
    answer_text = message.text
    message_id_to_edit = admin_current_message_to_edit.get(chat_id)

    if not request_id or not message_id_to_edit:
        bot.send_message(chat_id, "Ошибка: не найден ID запроса. Начните заново.")
        admin_states[chat_id] = ADMIN_STATE_NONE
        return

    request_data = db.get_support_request_by_id(request_id)
    if not request_data:
        bot.send_message(chat_id, "Ошибка: запрос не найден в базе данных.")
        admin_states[chat_id] = ADMIN_STATE_NONE
        return

    _, user_requester_id, _, _, _, current_status, _ = request_data

    user_markup = types.InlineKeyboardMarkup(row_width=1)
    btn_resolve = types.InlineKeyboardButton("✅ Проблема решена", callback_data=f"user_resolve_request_{request_id}")
    btn_reply = types.InlineKeyboardButton("💬 Ответить техподдержке", callback_data=f"user_reply_to_request_{request_id}")
    user_markup.add(btn_resolve, btn_reply)

    try:
        bot.send_message(
            user_requester_id,
            f"📢 **Ответ по вашему запросу #{request_id} от поддержки:**\n\n"
            f"{answer_text}",
            parse_mode="Markdown",
            reply_markup=user_markup
        )
        bot.send_message(chat_id, f"Ответ на запрос #{request_id} отправлен пользователю.")
        
        db.add_support_message(request_id, admin_id, admin_name, 'admin', answer_text)

        if current_status == 'Открыт':
            db.update_support_request_status(request_id, "Изучаем проблему", admin_id)
            bot.send_message(chat_id, f"Статус запроса #{request_id} автоматически изменен на **'Изучаем проблему'**.", parse_mode="Markdown")
            bot.send_message(
                user_requester_id,
                f"🔔 **Обновление по вашему запросу #{request_id}:**\n"
                f"Новый статус: **`Изучаем проблему`**",
                parse_mode="Markdown"
            )

    except Exception as e:
        bot.send_message(chat_id, f"Не удалось отправить ответ пользователю (ID: {user_requester_id}): {e}")

    admin_states[chat_id] = ADMIN_STATE_NONE
    if chat_id in admin_current_request_id:
        del admin_current_request_id[chat_id]
    
    show_request_details_for_admin(bot, chat_id, message_id_to_edit, request_id)

    if chat_id in admin_current_message_to_edit:
        del admin_current_message_to_edit[chat_id]

def change_request_status(bot, call_id, chat_id, message_id_to_edit, request_id, new_status, admin_id):
    if db.update_support_request_status(request_id, new_status, admin_id):
        bot.answer_callback_query(call_id, f"Статус изменен на '{new_status}'")
        
        request_data = db.get_support_request_by_id(request_id)
        if request_data:
            user_requester_id = request_data[1]
            bot.send_message(
                user_requester_id,
                f"🔔 **Обновление по вашему запросу #{request_id}:**\n"
                f"Новый статус: **`{new_status}`**"
                f"{' (Ваш запрос решен)' if new_status == 'Решен' else ''}",
                parse_mode="Markdown"
            )
        
        show_request_details_for_admin(bot, chat_id, message_id_to_edit, request_id)
        return True
    else:
        bot.answer_callback_query(call_id, "Ошибка при изменении статуса")
        return False

def get_manage_faq_menu():
    markup = types.InlineKeyboardMarkup(row_width=1)
    btn_add_faq = types.InlineKeyboardButton("➕ Добавить FAQ (по одному)", callback_data="admin_add_faq")
    btn_bulk_update_faq = types.InlineKeyboardButton("🔄 Обновить/Задать FAQ списком", callback_data="admin_bulk_update_faq")
    btn_view_faq = types.InlineKeyboardButton("Показать FAQ", callback_data="support_faq_from_admin")
    btn_delete_all_faq = types.InlineKeyboardButton("⚠️ Очистить ВСЕ FAQ", callback_data="admin_confirm_delete_all_faq")
    btn_back = types.InlineKeyboardButton("⬅️ Назад в Админ-панель", callback_data="admin_back_to_main")
    markup.add(btn_add_faq, btn_bulk_update_faq, btn_view_faq, btn_delete_all_faq, btn_back)
    return markup

def start_add_faq_flow(message, bot):
    bot.send_message(message.chat.id, "Введите вопрос для нового FAQ:")
    admin_states[message.chat.id] = ADMIN_STATE_AWAITING_FAQ_QUESTION

def process_faq_question(message, bot):
    question = message.text
    admin_current_faq_question[message.chat.id] = question
    bot.send_message(message.chat.id, f"Вопрос принят: `{question}`\nТеперь введите ответ на этот вопрос:", parse_mode="Markdown")
    admin_states[message.chat.id] = ADMIN_STATE_AWAITING_FAQ_ANSWER

def process_faq_answer(message, bot):
    chat_id = message.chat.id
    answer = message.text
    question = admin_current_faq_question.get(chat_id)

    if not question:
        bot.send_message(chat_id, "Ошибка: вопрос не был сохранен. Начните сначала.")
        admin_states[chat_id] = ADMIN_STATE_NONE
        if chat_id in admin_current_faq_question: del admin_current_faq_question[chat_id]
        return
    
    conn = db.get_db_connection()
    if conn:
        try:
            cur = conn.cursor()
            cur.execute("INSERT INTO faq (question, answer) VALUES (%s, %s);", (question, answer))
            conn.commit()
            bot.send_message(chat_id, "Новый FAQ успешно добавлен!")
        except Exception as e:
            bot.send_message(chat_id, f"Ошибка при добавлении FAQ: {e}")
            conn.rollback()
        finally:
            cur.close()
            conn.close()

    admin_states[chat_id] = ADMIN_STATE_NONE
    if chat_id in admin_current_faq_question: del admin_current_faq_question[chat_id]
    
    bot.send_message(chat_id, "Выберите действие:", reply_markup=get_manage_faq_menu())

def show_deletable_requests_list(bot, chat_id, message_id):
    requests = db.get_all_support_requests()
    
    if not requests:
        markup = types.InlineKeyboardMarkup()
        btn_back = types.InlineKeyboardButton("⬅️ Назад к управлению запросами", callback_data="admin_manage_requests")
        markup.add(btn_back)
        bot.edit_message_text(chat_id=chat_id, message_id=message_id, text="Нет запросов для удаления.", reply_markup=markup)
        return

    markup = types.InlineKeyboardMarkup(row_width=1)
    for req_id, user_id, username, full_name, description, status, created_at in requests:
        short_desc = description[:50] + "..." if len(description) > 50 else description
        button_text = f"❌ #{req_id} | {full_name} ({status}): {short_desc}"
        markup.add(types.InlineKeyboardButton(button_text, callback_data=f"admin_confirm_delete_one_{req_id}"))
    
    markup.add(types.InlineKeyboardButton("⬅️ Назад к управлению запросами", callback_data="admin_manage_requests"))
    
    bot.edit_message_text(chat_id=chat_id, message_id=message_id, text="Выберите запрос для удаления:", reply_markup=markup, parse_mode="Markdown")

def start_bulk_faq_update_flow(bot, chat_id):
    template = (
        "Пожалуйста, отправьте список вопросов и ответов для FAQ одним сообщением.\n"
        "**Все существующие FAQ будут удалены и заменены на новые.**\n\n"
        "**Используйте строгий шаблон:**\n"
        "```\n"
        "Вопрос: Ваш первый вопрос?\n"
        "Ответ: Ваш первый ответ.\n\n"
        "Вопрос: Ваш второй вопрос?\n"
        "Ответ: Ваш второй ответ.\n"
        "```\n\n"
        "**Правила:**\n"
        "1. Каждый вопрос начинается с 'Вопрос:'.\n"
        "2. Каждый ответ начинается с 'Ответ:'.\n"
        "3. Между парами 'Вопрос/Ответ' должна быть пустая строка (два переноса строки).\n"
        "4. Убедитесь, что все вопросы заканчиваются вопросительным знаком '?'."
    )
    bot.send_message(chat_id, template, parse_mode="Markdown")
    admin_states[chat_id] = ADMIN_STATE_AWAITING_BULK_FAQ_TEXT

def process_bulk_faq_text(message, bot, admin_states):
    chat_id = message.chat.id
    faq_text = message.text
    
    faq_items = []
    matches = re.findall(r"Вопрос:\s*(.*?)\s*Ответ:\s*(.*?)(?=\n\nВопрос:|\Z)", faq_text, re.DOTALL | re.IGNORECASE)

    if not matches:
        bot.send_message(chat_id, "❌ Не удалось распознать вопросы и ответы из текста. Проверьте формат.")
        admin_states[chat_id] = ADMIN_STATE_NONE
        bot.send_message(chat_id, "Что еще хотите сделать в админ-панели?", reply_markup=get_admin_main_menu())
        return

    for question, answer in matches:
        question = question.strip()
        answer = answer.strip()
        if question and answer:
            faq_items.append((question, answer))
    
    if not faq_items:
        bot.send_message(chat_id, "❌ Не удалось извлечь корректные пары Вопрос/Ответ из текста. Проверьте формат.")
    elif db.bulk_update_faq(faq_items):
        bot.send_message(chat_id, f"✅ FAQ успешно обновлен! Добавлено {len(faq_items)} записей.")
    else:
        bot.send_message(chat_id, "❌ Произошла ошибка при массовом обновлении FAQ.")
    
    admin_states[chat_id] = ADMIN_STATE_NONE
    bot.send_message(chat_id, "Что еще хотите сделать в админ-панели?", reply_markup=get_admin_main_menu())

def confirm_delete_all_faq(bot, chat_id, message_id):
    markup = types.InlineKeyboardMarkup(row_width=2)
    btn_yes = types.InlineKeyboardButton("ДА, УДАЛИТЬ ВСЕ", callback_data="admin_do_delete_all_faq")
    btn_no = types.InlineKeyboardButton("Отмена", callback_data="admin_manage_faq")
    markup.add(btn_yes, btn_no)
    bot.edit_message_text(chat_id=chat_id, message_id=message_id, text="⚠️ **ВНИМАНИЕ!**\nВы уверены, что хотите удалить **ВСЕ** вопросы и ответы из FAQ? Это действие необратимо.", reply_markup=markup, parse_mode="Markdown")

def get_manage_classes_menu():
    markup = types.InlineKeyboardMarkup(row_width=1)
    btn_add_group = types.InlineKeyboardButton("➕ Добавить группу", callback_data="admin_add_group")
    btn_delete_group = types.InlineKeyboardButton("🗑️ Удалить группу", callback_data="admin_delete_group")
    btn_back = types.InlineKeyboardButton("⬅️ Назад в Админ-панель", callback_data="admin_back_to_main")
    markup.add(btn_add_group, btn_delete_group, btn_back)
    return markup

def show_manage_classes_panel(bot, chat_id, message_id):
    groups = db.get_all_groups_with_classes()
    text = "🏫 **Управление классами и группами**\n\n"
    if groups:
        text += "Текущий список групп:\n"
        current_class = ""
        for _, class_number, group_name in groups:
            if str(class_number) != current_class:
                current_class = str(class_number)
                text += f"\n**{current_class} Класс:** "
            text += f"`{group_name}` "
    else:
        text += "Пока не создано ни одной группы."
    
    bot.edit_message_text(
        text=text, 
        chat_id=chat_id, 
        message_id=message_id, 
        reply_markup=get_manage_classes_menu(), 
        parse_mode="Markdown"
    )

def start_add_group_flow(bot, chat_id):
    bot.send_message(chat_id, "Введите номер класса и букву группы в формате: `11А` или `9Б`")
    admin_states[chat_id] = ADMIN_STATE_AWAITING_GROUP_NAME

def process_add_group(message, bot):
    chat_id = message.chat.id
    text = message.text.strip()
    
    match = re.match(r'^(\d{1,2})([А-Яа-я])$', text)
    if not match:
        bot.send_message(chat_id, "Неверный формат. Пожалуйста, введите в формате `11А` (цифра и одна буква).")
        return
    
    class_number = int(match.group(1))
    group_name = match.group(2).upper()

    if not (1 <= class_number <= 11):
        bot.send_message(chat_id, "Номер класса должен быть от 1 до 11.")
        return
        
    success, message_text = db.add_class_group(class_number, group_name)
    bot.send_message(chat_id, message_text)

    admin_states[chat_id] = ADMIN_STATE_NONE
    bot.send_message(chat_id, "Возвращаю в админ-панель...", reply_markup=get_admin_main_menu())


def show_deletable_groups_list(bot, chat_id, message_id):
    groups = db.get_all_groups_with_classes()
    if not groups:
        bot.edit_message_text(chat_id=chat_id, message_id=message_id, text="Нет групп для удаления.", reply_markup=types.InlineKeyboardMarkup().add(types.InlineKeyboardButton("⬅️ Назад", callback_data="admin_manage_classes")))
        return
    
    markup = types.InlineKeyboardMarkup(row_width=1)
    for group_id, class_number, group_name in groups:
        markup.add(types.InlineKeyboardButton(f"❌ {class_number}{group_name}", callback_data=f"admin_confirm_delete_group_{group_id}"))
    markup.add(types.InlineKeyboardButton("⬅️ Назад", callback_data="admin_manage_classes"))
    bot.edit_message_text(chat_id=chat_id, message_id=message_id, text="Выберите группу для удаления:", reply_markup=markup)

def confirm_delete_group(bot, chat_id, message_id, group_id):
    group_info = db.get_group_info(group_id)
    if not group_info: return
    
    group_name = f"{group_info[2]}{group_info[1]}"
    markup = types.InlineKeyboardMarkup(row_width=2)
    btn_yes = types.InlineKeyboardButton("Да, удалить", callback_data=f"admin_do_delete_group_{group_id}")
    btn_no = types.InlineKeyboardButton("Отмена", callback_data="admin_delete_group")
    markup.add(btn_yes, btn_no)
    bot.edit_message_text(chat_id=chat_id, message_id=message_id, text=f"Вы уверены, что хотите удалить группу `{group_name}`? Все связанные расписания будут удалены, а ученики отвязаны.", reply_markup=markup, parse_mode="Markdown")

def do_delete_group(bot, call, group_id):
    if db.delete_group_by_id(group_id):
        bot.answer_callback_query(call.id, "Группа удалена.")
        show_deletable_groups_list(bot, call.message.chat.id, call.message.message_id)
    else:
        bot.answer_callback_query(call.id, "Ошибка при удалении.", show_alert=True)