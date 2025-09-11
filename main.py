import telebot
from telebot import types
import config
import os
import datetime
import modules.database as db
import modules.support as support_module
import modules.admin as admin_module
import modules.schedule as schedule_module

if config.BOT_TOKEN is None:
    print("Ошибка: TELEGRAM_BOT_TOKEN не установлен в переменных окружения.")
    exit()

bot = telebot.TeleBot(config.BOT_TOKEN)

ADMIN_DOC_PATH = "admin_documentation.pdf"

def get_main_menu():
    markup = types.ReplyKeyboardMarkup(resize_keyboard=True, one_time_keyboard=False)
    btn_schedule = types.KeyboardButton("Расписание")
    btn_support = types.KeyboardButton("Техподдержка")
    markup.add(btn_schedule, btn_support)
    return markup

def get_schedule_menu():
    markup = types.InlineKeyboardMarkup(row_width=2)
    btn_today = types.InlineKeyboardButton("На сегодня", callback_data="schedule_today")
    btn_week = types.InlineKeyboardButton("На неделю", callback_data="schedule_week")
    btn_back = types.InlineKeyboardButton("⬅️ Назад", callback_data="back_to_main_from_schedule")
    markup.add(btn_today, btn_week, btn_back)
    return markup

@bot.message_handler(commands=['start', 'help'])
def send_welcome(message):
    user_id = message.from_user.id
    user_name = message.from_user.first_name if message.from_user.first_name else "Пользователь"
    full_name = f"{message.from_user.first_name} {message.from_user.last_name if message.from_user.last_name else ''}".strip()
    username = message.from_user.username
    
    is_admin_user = (user_id in config.ADMIN_IDS)
    db.add_or_update_user(user_id, username, message.from_user.first_name, message.from_user.last_name, is_admin_user)

    welcome_text = (
        f"Привет, {user_name}! 👋\n"
        f"Я бот для онлайн-школы."
    )
    bot.send_message(message.chat.id, welcome_text, reply_markup=get_main_menu_with_admin_button(is_admin_user))

    if is_admin_user:
        if os.path.exists(ADMIN_DOC_PATH):
            try:
                with open(ADMIN_DOC_PATH, 'rb') as doc_file:
                    bot.send_document(message.chat.id, doc_file, caption="✅ Ваша документация администратора:")
            except Exception as e:
                bot.send_message(message.chat.id, f"⚠️ Не удалось отправить документацию: {e}")
        else:
            bot.send_message(message.chat.id, f"⚠️ Файл документации '{ADMIN_DOC_PATH}' не найден.")


def get_main_menu_with_admin_button(is_admin_user):
    markup = get_main_menu()
    if is_admin_user:
        btn_admin_panel = types.KeyboardButton("⚙️ Админ-панель")
        markup.add(btn_admin_panel)
    return markup

@bot.message_handler(func=lambda message: message.text == "Расписание")
def show_schedule_options(message):
    bot.send_message(message.chat.id, "Что интересует по расписанию?", reply_markup=get_schedule_menu())

@bot.message_handler(func=lambda message: message.text == "Техподдержка")
def show_support_options(message):
    bot.send_message(message.chat.id, "Выбери опцию техподдержки:", reply_markup=support_module.get_support_menu())

@bot.message_handler(func=lambda message: message.text == "⚙️ Админ-панель" and admin_module.is_admin(message.from_user.id))
def show_admin_panel_entry(message):
    admin_module.show_admin_panel(bot, message.chat.id, message.message_id, message.from_user.id)

@bot.callback_query_handler(func=lambda call: True)
def callback_query(call):
    chat_id = call.message.chat.id
    user_id = call.from_user.id
    message_id = call.message.message_id 

    if call.data == "schedule_today":
        bot.answer_callback_query(call.id, "Загружаю расписание...")
        full_schedule = db.get_schedule()
        if not full_schedule:
            bot.send_message(chat_id, "Расписание еще не заполнено.")
            return

        days_of_week = ["Понедельник", "Вторник", "Среда", "Четверг", "Пятница", "Суббота", "Воскресенье"]
        day_index = datetime.datetime.now().weekday()
        current_day_name = days_of_week[day_index]
        today_schedule = schedule_module.parse_schedule_for_day(full_schedule, current_day_name)
        
        markup = types.InlineKeyboardMarkup()
        btn_back = types.InlineKeyboardButton("⬅️ Назад к выбору расписания", callback_data="back_to_schedule_menu")
        markup.add(btn_back)
        bot.send_message(chat_id, f"**Расписание на сегодня ({current_day_name}):**\n\n{today_schedule}", parse_mode="Markdown", reply_markup=markup)
        try: bot.delete_message(chat_id=chat_id, message_id=message_id)
        except: pass

    elif call.data == "schedule_week":
        bot.answer_callback_query(call.id, "Загружаю расписание...")
        full_schedule = db.get_schedule()
        markup = types.InlineKeyboardMarkup()
        btn_back = types.InlineKeyboardButton("⬅️ Назад к выбору расписания", callback_data="back_to_schedule_menu")
        markup.add(btn_back)
        if full_schedule:
            bot.send_message(chat_id, f"**Расписание на неделю:**\n\n{full_schedule}", parse_mode="Markdown", reply_markup=markup)
        else:
            bot.send_message(chat_id, "Расписание еще не заполнено.", reply_markup=markup)
        try: bot.delete_message(chat_id=chat_id, message_id=message_id)
        except: pass
    
    elif call.data == "back_to_schedule_menu":
        bot.answer_callback_query(call.id)
        bot.delete_message(chat_id=chat_id, message_id=message_id)
        bot.send_message(chat_id, "Что интересует по расписанию?", reply_markup=get_schedule_menu())
    
    elif call.data == "back_to_main_from_schedule":
        bot.answer_callback_query(call.id)
        bot.delete_message(chat_id=chat_id, message_id=message_id)
        bot.send_message(chat_id, "Главное меню", reply_markup=get_main_menu_with_admin_button(admin_module.is_admin(user_id)))

    elif call.data == "support_faq":
        bot.answer_callback_query(call.id, "Открываю FAQ...")
        support_module.show_faq(call.message, bot)
        try: bot.delete_message(chat_id=chat_id, message_id=message_id)
        except: pass
    elif call.data == "support_create_request":
        bot.answer_callback_query(call.id, "Приступаем к созданию запроса...")
        support_module.start_create_request_flow(call.message, bot)
        try: bot.delete_message(chat_id=chat_id, message_id=message_id)
        except: pass
    elif call.data == "support_check_status":
        bot.answer_callback_query(call.id, "Проверяю ваши запросы...")
        support_module.show_user_requests(call.message, bot)
        try: bot.delete_message(chat_id=chat_id, message_id=message_id)
        except: pass
    elif call.data == "back_to_support_menu":
        bot.answer_callback_query(call.id)
        bot.delete_message(chat_id=chat_id, message_id=message_id)
        bot.send_message(chat_id=chat_id, text="Выбери опцию техподдержки:", reply_markup=support_module.get_support_menu())
    
    elif call.data == "back_to_main":
        bot.answer_callback_query(call.id, "Возвращаюсь в главное меню")
        try: bot.delete_message(chat_id=chat_id, message_id=message_id)
        except: pass
        bot.send_message(chat_id, "Главное меню", reply_markup=get_main_menu_with_admin_button(admin_module.is_admin(user_id)))

    elif call.data.startswith("user_resolve_request_"):
        request_id = int(call.data.split('_')[-1])
        user_full_name = f"{call.from_user.first_name} {call.from_user.last_name or ''}".strip()
        
        db.update_support_request_status(request_id, "Решен")
        bot.answer_callback_query(call.id, "Запрос закрыт. Спасибо!")
        bot.edit_message_text(chat_id=chat_id, message_id=message_id, text=call.message.text + "\n\n✅ *Вы закрыли этот запрос.*", parse_mode="Markdown", reply_markup=None)
        support_module.notify_admin_of_status_change(bot, request_id, "Решен", user_full_name)

    elif call.data.startswith("user_reply_to_request_"):
        request_id = int(call.data.split('_')[-1])
        bot.answer_callback_query(call.id)
        bot.edit_message_reply_markup(chat_id=chat_id, message_id=message_id, reply_markup=None)
        support_module.start_reply_flow(call.message, bot, request_id)

    elif call.data == "user_confirm_delete_my_requests":
        markup = types.InlineKeyboardMarkup(row_width=2)
        btn_yes = types.InlineKeyboardButton("Да, удалить", callback_data="user_do_delete_my_requests")
        btn_no = types.InlineKeyboardButton("Нет, отмена", callback_data="support_check_status")
        markup.add(btn_yes, btn_no)
        bot.edit_message_text(chat_id=chat_id, message_id=message_id, text="Вы уверены, что хотите удалить все свои запросы? Это действие необратимо.", reply_markup=markup)

    elif call.data == "user_do_delete_my_requests":
        if db.delete_user_support_requests(user_id):
            bot.answer_callback_query(call.id, "Ваша история запросов очищена.")
            support_module.show_user_requests(call.message, bot)
            try: bot.delete_message(chat_id=chat_id, message_id=message_id)
            except: pass
        else:
            bot.answer_callback_query(call.id, "Произошла ошибка при удалении.")

    elif admin_module.is_admin(user_id):
        if call.data == "admin_back_to_main":
            bot.answer_callback_query(call.id, "Назад в админ-панель...")
            admin_module.show_admin_panel(bot, chat_id, message_id, user_id)
        
        elif call.data == "admin_manage_requests":
            bot.answer_callback_query(call.id, "Управление запросами...")
            bot.edit_message_text(chat_id=chat_id, message_id=message_id, text="Выберите действие:", reply_markup=admin_module.get_manage_requests_menu(), parse_mode="Markdown")
        elif call.data == "admin_view_new_requests":
            bot.answer_callback_query(call.id, "Показываю новые запросы...")
            admin_module.show_requests_list(call.message, bot, is_new_requests=True)
            try: bot.delete_message(chat_id=chat_id, message_id=message_id)
            except: pass
        elif call.data == "admin_view_all_requests":
            bot.answer_callback_query(call.id, "Показываю все запросы...")
            admin_module.show_requests_list(call.message, bot, is_new_requests=False)
            try: bot.delete_message(chat_id=chat_id, message_id=message_id)
            except: pass
        elif call.data.startswith("admin_view_request_details_"):
            request_id = int(call.data.split('_')[-1])
            bot.answer_callback_query(call.id, f"Просмотр запроса #{request_id}...")
            try: bot.delete_message(chat_id=chat_id, message_id=message_id)
            except: pass
            admin_module.show_request_details_for_admin(bot, chat_id, message_id, request_id)
            
        elif call.data.startswith("admin_change_status_"):
            parts = call.data.split('_')
            request_id_to_update = int(parts[-1]) 
            new_status = ' '.join(parts[3:-1])
            admin_module.change_request_status(bot, call.id, chat_id, message_id, request_id_to_update, new_status, user_id)
            
        elif call.data.startswith("admin_start_answer_"):
            request_id = int(call.data.split('_')[-1])
            bot.answer_callback_query(call.id, f"Подготовка ответа...")
            admin_module.start_answer_flow_from_details(call.message, bot, request_id)
        elif call.data == "admin_back_to_requests_list":
            bot.answer_callback_query(call.id, "Назад к списку запросов...")
            admin_module.show_requests_list(call.message, bot, is_new_requests=False)
            try: bot.delete_message(chat_id=chat_id, message_id=message_id)
            except: pass

        elif call.data == "admin_confirm_delete_all":
            markup = types.InlineKeyboardMarkup(row_width=2)
            btn_yes = types.InlineKeyboardButton("ДА, УДАЛИТЬ ВСЕ", callback_data="admin_do_delete_all")
            btn_no = types.InlineKeyboardButton("Отмена", callback_data="admin_manage_requests")
            markup.add(btn_yes, btn_no)
            bot.edit_message_text(chat_id=chat_id, message_id=message_id, text="⚠️ **ВНИМАНИЕ!**\nВы уверены, что хотите удалить **ВСЕ** запросы и историю переписки? Это действие необратимо.", reply_markup=markup, parse_mode="Markdown")

        elif call.data == "admin_do_delete_all":
            if db.delete_all_support_requests():
                bot.answer_callback_query(call.id, "Все запросы были удалены.", show_alert=True)
                bot.edit_message_text(chat_id=chat_id, message_id=message_id, text="Все запросы в техподдержку были удалены.", reply_markup=admin_module.get_manage_requests_menu())
            else:
                bot.answer_callback_query(call.id, "Произошла ошибка при удалении.", show_alert=True)
        
        elif call.data == "admin_delete_request_menu":
            bot.answer_callback_query(call.id)
            admin_module.show_deletable_requests_list(bot, chat_id, message_id)
            
        elif call.data.startswith("admin_confirm_delete_one_"):
            request_id = int(call.data.split('_')[-1])
            markup = types.InlineKeyboardMarkup(row_width=2)
            btn_yes = types.InlineKeyboardButton("Да, удалить", callback_data=f"admin_do_delete_one_{request_id}")
            btn_no = types.InlineKeyboardButton("Отмена", callback_data="admin_delete_request_menu")
            markup.add(btn_yes, btn_no)
            bot.edit_message_text(chat_id=chat_id, message_id=message_id, text=f"Вы уверены, что хотите удалить запрос #{request_id}?", reply_markup=markup)
            
        elif call.data.startswith("admin_do_delete_one_"):
            request_id = int(call.data.split('_')[-1])
            if db.delete_support_request_by_id(request_id):
                bot.answer_callback_query(call.id, f"Запрос #{request_id} удален.")
                admin_module.show_deletable_requests_list(bot, chat_id, message_id)
            else:
                bot.answer_callback_query(call.id, "Ошибка при удалении.", show_alert=True)

        elif call.data == "admin_manage_faq":
            bot.answer_callback_query(call.id, "Управление FAQ...")
            bot.edit_message_text(chat_id=chat_id, message_id=message_id, text="Выберите действие:", reply_markup=admin_module.get_manage_faq_menu(), parse_mode="Markdown")
        elif call.data == "admin_add_faq":
            bot.answer_callback_query(call.id, "Добавление FAQ (по одному)...")
            admin_module.start_add_faq_flow(call.message, bot)
            try: bot.delete_message(chat_id=chat_id, message_id=message_id)
            except: pass
        elif call.data == "admin_bulk_update_faq":
            bot.answer_callback_query(call.id, "Массовое обновление FAQ...")
            admin_module.start_bulk_faq_update_flow(bot, chat_id)
            try: bot.delete_message(chat_id=chat_id, message_id=message_id)
            except: pass
        elif call.data == "admin_confirm_delete_all_faq":
            bot.answer_callback_query(call.id)
            admin_module.confirm_delete_all_faq(bot, chat_id, message_id)
        elif call.data == "admin_do_delete_all_faq":
            if db.delete_all_faq_items():
                bot.answer_callback_query(call.id, "Все FAQ удалены.", show_alert=True)
                bot.edit_message_text(chat_id=chat_id, message_id=message_id, text="Все FAQ были удалены.", reply_markup=admin_module.get_manage_faq_menu())
            else:
                bot.answer_callback_query(call.id, "Ошибка при удалении FAQ.", show_alert=True)
        elif call.data == "support_faq_from_admin":
            bot.answer_callback_query(call.id, "Показываю FAQ...")
            support_module.show_faq(call.message, bot)
            try: bot.delete_message(chat_id=chat_id, message_id=message_id)
            except: pass
            
        elif call.data == "admin_manage_schedule":
            bot.answer_callback_query(call.id, "Управление расписанием...")
            schedule_module.show_manage_schedule_panel(bot, chat_id, message_id)
        elif call.data == "admin_schedule_update":
            bot.answer_callback_query(call.id)
            schedule_module.start_schedule_update_flow(bot, chat_id, admin_module.admin_states)
            try: bot.delete_message(chat_id=chat_id, message_id=message_id)
            except: pass

@bot.message_handler(func=lambda message: support_module.user_support_states.get(message.chat.id) == support_module.SUPPORT_STATE_AWAITING_DESCRIPTION)
def process_support_message(message):
    support_module.process_support_description(message, bot)

@bot.message_handler(func=lambda message: support_module.user_support_states.get(message.chat.id) == support_module.SUPPORT_STATE_AWAITING_REPLY)
def process_user_reply_message(message):
    support_module.process_user_reply(message, bot)

@bot.message_handler(func=lambda message: admin_module.is_admin(message.from_user.id) and admin_module.admin_states.get(message.chat.id) == admin_module.ADMIN_STATE_AWAITING_ANSWER_TEXT)
def process_admin_answer_text_message(message):
    admin_module.process_admin_answer(message, bot)

@bot.message_handler(func=lambda message: admin_module.is_admin(message.from_user.id) and admin_module.admin_states.get(message.chat.id) == admin_module.ADMIN_STATE_AWAITING_FAQ_QUESTION)
def process_admin_faq_question_message(message):
    admin_module.process_faq_question(message, bot)

@bot.message_handler(func=lambda message: admin_module.is_admin(message.from_user.id) and admin_module.admin_states.get(message.chat.id) == admin_module.ADMIN_STATE_AWAITING_FAQ_ANSWER)
def process_admin_faq_answer_message(message):
    admin_module.process_faq_answer(message, bot)

@bot.message_handler(func=lambda message: admin_module.is_admin(message.from_user.id) and admin_module.admin_states.get(message.chat.id) == admin_module.ADMIN_STATE_AWAITING_BULK_FAQ_TEXT)
def process_admin_bulk_faq_text_message(message):
    admin_module.process_bulk_faq_text(message, bot, admin_module.admin_states)

@bot.message_handler(func=lambda message: admin_module.is_admin(message.from_user.id) and admin_module.admin_states.get(message.chat.id) == schedule_module.ADMIN_STATE_AWAITING_SCHEDULE_TEXT)
def process_admin_schedule_text_message(message):
    schedule_module.process_schedule_update(message, bot, admin_module.admin_states)

@bot.message_handler(func=lambda message: True, content_types=['text'])
def echo_all(message):
    pass

if __name__ == '__main__':
    print("Бот запущен...")
    db.init_db()
    try:
        bot.polling(none_stop=True)
    except Exception as e:
        print(f"Произошла ошибка при запуске бота: {e}")
