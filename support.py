from telebot import types
import modules.database as db
import config
import modules.faq_matcher as faq_matcher

SUPPORT_STATE_NONE = 0
SUPPORT_STATE_AWAITING_DESCRIPTION = 1
SUPPORT_STATE_AWAITING_REPLY = 2

user_support_states = {}
user_replying_to_request_id = {}

def get_support_menu():
    markup = types.InlineKeyboardMarkup(row_width=1)
    btn_faq = types.InlineKeyboardButton("Часто задаваемые вопросы (FAQ)", callback_data="support_faq")
    btn_create_request = types.InlineKeyboardButton("Создать запрос", callback_data="support_create_request")
    btn_check_status = types.InlineKeyboardButton("Проверить статус запроса", callback_data="support_check_status")
    btn_back = types.InlineKeyboardButton("⬅️ Назад в главное меню", callback_data="back_to_main")
    markup.add(btn_faq, btn_create_request, btn_check_status, btn_back)
    return markup

def start_create_request_flow(message, bot):
    bot.send_message(message.chat.id, "Опишите вашу проблему максимально подробно, и я постараюсь найти ответ в базе знаний. Если ответа не найдется, я создам запрос в техподдержку.")
    user_support_states[message.chat.id] = SUPPORT_STATE_AWAITING_DESCRIPTION

def process_support_description(message, bot):
    user_id = message.chat.id
    username = message.from_user.username
    full_name = f"{message.from_user.first_name} {message.from_user.last_name if message.from_user.last_name else ''}".strip()
    description = message.text

    all_faq_items = db.get_all_faq_items()
    
    best_match = faq_matcher.find_best_faq_match(description, all_faq_items)
    
    if best_match:
        faq_question, faq_answer = best_match
        bot.send_message(
            user_id,
            f"💡 **Найден возможный ответ в нашем FAQ:**\n\n"
            f"**Вопрос:** {faq_question}\n"
            f"**Ответ:** {faq_answer}",
            parse_mode="Markdown"
        )
        bot.send_message(user_id, "Надеюсь, это помогло! Если проблема не решена, вы можете создать запрос снова.", reply_markup=get_support_menu())
        user_support_states[user_id] = SUPPORT_STATE_NONE
        return

    request_id = db.add_support_request(user_id, username, full_name, description)

    if request_id:
        db.add_support_message(request_id, user_id, full_name, 'user', description)
        bot.send_message(user_id, f"Спасибо, ваш запрос #{request_id} принят и будет рассмотрен. Мы свяжемся с вами в ближайшее время.")
        notify_admins_new_request(bot, request_id, user_id, full_name, description)
    else:
        bot.send_message(user_id, "Извините, не удалось создать запрос. Пожалуйста, попробуйте позже.")

    user_support_states[user_id] = SUPPORT_STATE_NONE
    bot.send_message(user_id, "Что еще могу сделать?", reply_markup=get_support_menu())


def show_faq(message, bot):
    faq_items = db.get_all_faq_items()
    markup = types.InlineKeyboardMarkup()
    btn_back = types.InlineKeyboardButton("⬅️ Назад в меню поддержки", callback_data="back_to_support_menu")
    markup.add(btn_back)
    
    if not faq_items:
        bot.send_message(message.chat.id, "Пока нет часто задаваемых вопросов.", reply_markup=markup)
        return

    faq_text = "📚 **Часто задаваемые вопросы:**\n\n"
    for i, (question, answer) in enumerate(faq_items):
        faq_text += f"**{i+1}. {question}**\n"
        faq_text += f"{answer}\n\n"

    bot.send_message(message.chat.id, faq_text, parse_mode="Markdown", reply_markup=markup)

def show_user_requests(message, bot):
    user_id = message.chat.id
    requests = db.get_user_support_requests(user_id)
    
    markup = types.InlineKeyboardMarkup()
    
    if not requests:
        btn_back = types.InlineKeyboardButton("⬅️ Назад в меню поддержки", callback_data="back_to_support_menu")
        markup.add(btn_back)
        bot.send_message(user_id, "У вас пока нет активных или завершенных запросов.", reply_markup=markup)
        return

    requests_text = "Ваши запросы в техподдержку:\n\n"
    for req_id, desc, status, created_at in requests:
        requests_text += (
            f"**Запрос #{req_id}** (от {created_at.strftime('%d.%m.%Y %H:%M')})\n"
            f"Описание: {desc[:100]}...\n"
            f"Статус: `{status}`\n\n"
        )
    
    btn_clear = types.InlineKeyboardButton("🗑️ Очистить мою историю запросов", callback_data="user_confirm_delete_my_requests")
    btn_back = types.InlineKeyboardButton("⬅️ Назад в меню поддержки", callback_data="back_to_support_menu")
    markup.add(btn_clear, btn_back)
    
    bot.send_message(user_id, requests_text, parse_mode="Markdown", reply_markup=markup)

def notify_admins_new_request(bot, request_id, user_id, user_full_name, description):
    markup = types.InlineKeyboardMarkup()
    btn_details = types.InlineKeyboardButton("Просмотреть запрос", callback_data=f"admin_view_request_details_{request_id}")
    markup.add(btn_details)
    
    for admin_id in config.ADMIN_IDS:
        try:
            bot.send_message(
                admin_id,
                f"🚨 **НОВЫЙ ЗАПРОС В ТЕХПОДДЕРЖКУ!** 🚨\n\n"
                f"**ID запроса:** #{request_id}\n"
                f"**От пользователя:** {user_full_name} (ID: `{user_id}`)\n"
                f"**Описание:** {description}",
                parse_mode="Markdown",
                reply_markup=markup
            )
        except Exception as e:
            print(f"Не удалось отправить уведомление админу {admin_id}: {e}")

def start_reply_flow(message, bot, request_id):
    chat_id = message.chat.id
    user_support_states[chat_id] = SUPPORT_STATE_AWAITING_REPLY
    user_replying_to_request_id[chat_id] = request_id
    bot.send_message(chat_id, "Введите ваш ответ для техподдержки:")

def process_user_reply(message, bot):
    user_id = message.chat.id
    request_id = user_replying_to_request_id.get(user_id)
    user_full_name = f"{message.from_user.first_name} {message.from_user.last_name or ''}".strip()
    reply_text = message.text
    
    if not request_id:
        return

    db.add_support_message(request_id, user_id, user_full_name, 'user', reply_text)

    for admin_id in config.ADMIN_IDS:
        try:
            markup = types.InlineKeyboardMarkup()
            btn_details = types.InlineKeyboardButton("Перейти к запросу", callback_data=f"admin_view_request_details_{request_id}")
            markup.add(btn_details)
            bot.send_message(
                admin_id,
                f"💬 **Новый ответ от пользователя по запросу #{request_id}**\n\n"
                f"**От:** {user_full_name} (ID: `{user_id}`)\n"
                f"**Сообщение:**\n{reply_text}",
                parse_mode="Markdown",
                reply_markup=markup
            )
        except Exception as e:
            print(f"Не удалось отправить ответ админу {admin_id}: {e}")

    bot.send_message(user_id, "Ваше сообщение отправлено в техподдержку.")
    
    user_support_states[user_id] = SUPPORT_STATE_NONE
    if user_id in user_replying_to_request_id:
        del user_replying_to_request_id[user_id]

def notify_admin_of_status_change(bot, request_id, new_status, user_full_name):
    for admin_id in config.ADMIN_IDS:
        try:
            bot.send_message(
                admin_id,
                f"ℹ️ Пользователь **{user_full_name}** закрыл запрос **#{request_id}**.\n"
                f"Новый статус: **{new_status}**",
                parse_mode="Markdown"
            )
        except Exception as e:
            print(f"Не удалось уведомить админа {admin_id} о смене статуса: {e}")
