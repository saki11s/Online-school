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

admin_schedule_view_state = {}

def get_main_menu():
    markup = types.ReplyKeyboardMarkup(resize_keyboard=True, one_time_keyboard=False)
    btn_schedule = types.KeyboardButton("Расписание")
    btn_support = types.KeyboardButton("Техподдержка")
    markup.add(btn_schedule, btn_support)
    return markup

def get_schedule_menu():
    markup = types.InlineKeyboardMarkup(row_width=3)
    days = ["Пн", "Вт", "Ср", "Чт", "Пт", "Сб"]
    buttons = [types.InlineKeyboardButton(day, callback_data=f"schedule_day_{i}") for i, day in enumerate(days)]
    markup.add(*buttons)
    
    btn_today = types.InlineKeyboardButton("На сегодня", callback_data="schedule_today")
    btn_all_week = types.InlineKeyboardButton("На всю неделю", callback_data="schedule_week")
    markup.add(btn_today, btn_all_week)
    
    btn_back = types.InlineKeyboardButton("⬅️ Назад", callback_data="back_to_main_from_schedule")
    markup.add(btn_back)
    return markup

def get_admin_schedule_menu():
    markup = types.InlineKeyboardMarkup(row_width=3)
    days = ["Пн", "Вт", "Ср", "Чт", "Пт", "Сб"]
    buttons = [types.InlineKeyboardButton(day, callback_data=f"schedule_day_{i}") for i, day in enumerate(days)]
    markup.add(*buttons)
    
    btn_today = types.InlineKeyboardButton("На сегодня", callback_data="schedule_today")
    btn_all_week = types.InlineKeyboardButton("На всю неделю", callback_data="schedule_week")
    markup.add(btn_today, btn_all_week)
    
    btn_back_to_groups = types.InlineKeyboardButton("⬅️ Назад к выбору группы", callback_data="admin_back_to_group_select")
    markup.add(btn_back_to_groups)
    return markup

@bot.message_handler(commands=['start', 'help'])
def send_welcome(message):
    user_id = message.from_user.id
    user_name = message.from_user.first_name if message.from_user.first_name else "Пользователь"
    
    is_admin_user = (user_id in config.ADMIN_IDS)
    db.add_or_update_user(user_id, message.from_user.username, message.from_user.first_name, message.from_user.last_name, is_admin_user)

    user_group_id = db.get_user_group(user_id)
    if not user_group_id and not is_admin_user:
        bot.send_message(message.chat.id, f"Привет, {user_name}! 👋\nПрежде чем мы начнем, пожалуйста, выбери свой класс.", reply_markup=get_class_selection_menu())
        return

    welcome_text = (
        f"Привет, {user_name}! 👋\n"
        f"Я бот для онлайн-школы."
    )
    bot.send_message(message.chat.id, welcome_text, reply_markup=get_main_menu_with_admin_button(is_admin_user))

    if is_admin_user:
        if os.path.exists(ADMIN_DOC_PATH):
            try:
                with open(ADMIN_DOC_PATH, 'rb') as doc_file:
                    bot.send_document(message.chat.id, doc_file, caption="✅ Ваша документация администратора:", timeout=60)
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

def show_admin_group_selection_for_schedule(message):
    chat_id = message.chat.id
    groups = db.get_all_groups_with_classes()
    if not groups:
        bot.send_message(chat_id, "В системе еще не создано ни одной группы. Расписание смотреть некому.")
        return
        
    markup = types.InlineKeyboardMarkup(row_width=3)
    buttons = [types.InlineKeyboardButton(f"{class_num}{group_name}", callback_data=f"admin_view_schedule_for_group_{group_id}") for group_id, class_num, group_name in groups]
    markup.add(*buttons)
    bot.send_message(chat_id, "Выберите группу для просмотра расписания:", reply_markup=markup)

@bot.message_handler(func=lambda message: message.text == "Расписание")
def show_schedule_options(message):
    user_id = message.from_user.id
    is_admin_user = admin_module.is_admin(user_id)
    db.add_or_update_user(user_id, message.from_user.username, message.from_user.first_name, message.from_user.last_name, is_admin_user)
    
    if is_admin_user:
        show_admin_group_selection_for_schedule(message)
        return

    user_group_id = db.get_user_group(user_id)
    if not user_group_id:
        bot.send_message(message.chat.id, "Сначала нужно выбрать свой класс.", reply_markup=get_class_selection_menu())
        return

    bot.send_message(message.chat.id, "Что интересует по расписанию?", reply_markup=get_schedule_menu())

@bot.message_handler(func=lambda message: message.text == "Техподдержка")
def show_support_options(message):
    user_id = message.from_user.id
    is_admin_user = (user_id in config.ADMIN_IDS)
    db.add_or_update_user(user_id, message.from_user.username, message.from_user.first_name, message.from_user.last_name, is_admin_user)
    bot.send_message(message.chat.id, "Выбери опцию техподдержки:", reply_markup=support_module.get_support_menu())

@bot.message_handler(func=lambda message: message.text == "⚙️ Админ-панель" and admin_module.is_admin(message.from_user.id))
def show_admin_panel_entry(message):
    admin_module.show_admin_panel(bot, message.chat.id, message.message_id, message.from_user.id)

def get_class_selection_menu():
    classes = db.get_all_classes()
    markup = types.InlineKeyboardMarkup(row_width=4)
    if classes:
        buttons = [types.InlineKeyboardButton(str(c[1]), callback_data=f"select_class_{c[0]}") for c in classes]
        markup.add(*buttons)
    else:
        markup.add(types.InlineKeyboardButton("Нет доступных классов", callback_data="no_action"))
    return markup

def get_group_selection_menu(class_id):
    groups = db.get_groups_for_class(class_id)
    markup = types.InlineKeyboardMarkup(row_width=3)
    if groups:
        buttons = [types.InlineKeyboardButton(g[1], callback_data=f"select_group_{g[0]}") for g in groups]
        markup.add(*buttons)
    btn_back = types.InlineKeyboardButton("⬅️ Назад к выбору класса", callback_data="back_to_class_select")
    markup.add(btn_back)
    return markup

@bot.callback_query_handler(func=lambda call: True)
def callback_query(call):
    chat_id = call.message.chat.id
    user_id = call.from_user.id
    message_id = call.message.message_id
    is_admin_user = admin_module.is_admin(user_id)

    if call.data.startswith("select_class_"):
        class_id = int(call.data.split('_')[-1])
        bot.edit_message_text("Теперь выбери свою букву/группу:", chat_id, message_id, reply_markup=get_group_selection_menu(class_id))
    
    elif call.data == "back_to_class_select":
        bot.edit_message_text("Пожалуйста, выбери свой класс:", chat_id, message_id, reply_markup=get_class_selection_menu())

    elif call.data.startswith("select_group_"):
        group_id = int(call.data.split('_')[-1])
        db.set_user_group(user_id, group_id)
        group_info = db.get_group_info(group_id)
        class_name = group_info[2] if group_info else ""
        group_name = group_info[1] if group_info else ""

        bot.edit_message_text(
            chat_id=chat_id, 
            message_id=message_id, 
            text=f"Отлично! Я запомнил, что ты из {class_name}{group_name} класса.",
            reply_markup=None
        )
        bot.send_message(chat_id, "Теперь ты можешь посмотреть расписание или обратиться в техподдержку.", reply_markup=get_main_menu_with_admin_button(is_admin_user))

    elif call.data.startswith("admin_view_schedule_for_group_"):
        group_id = int(call.data.split('_')[-1])
        admin_schedule_view_state[user_id] = group_id
        group_info = db.get_group_info(group_id)
        group_name_full = f"{group_info[2]}{group_info[1]}" if group_info else f"ID: {group_id}"
        bot.edit_message_text(
            chat_id=chat_id,
            message_id=message_id,
            text=f"Что интересует по расписанию для группы **{group_name_full}**?",
            reply_markup=get_admin_schedule_menu(),
            parse_mode="Markdown"
        )
    
    elif call.data == "admin_back_to_group_select":
        show_admin_group_selection_for_schedule(call.message)
        bot.delete_message(chat_id, message_id)

    elif call.data == "schedule_today":
        bot.answer_callback_query(call.id, "Загружаю расписание...")
        
        group_id_to_show = None
        if is_admin_user and user_id in admin_schedule_view_state:
            group_id_to_show = admin_schedule_view_state[user_id]
        else:
            group_id_to_show = db.get_user_group(user_id)
        
        if not group_id_to_show:
            bot.send_message(chat_id, "Пожалуйста, сначала выбери свой класс.")
            return

        full_schedule = db.get_schedule_for_group(group_id_to_show)
        if not full_schedule:
            bot.send_message(chat_id, "Расписание для этой группы еще не заполнено.")
            return

        days_of_week_full = ["Понедельник", "Вторник", "Среда", "Четверг", "Пятница", "Суббота", "Воскресенье"]
        day_index = datetime.datetime.now().weekday()
        current_day_name = days_of_week_full[day_index]
        day_schedule = schedule_module.parse_schedule_for_day(full_schedule, current_day_name)
        
        markup = types.InlineKeyboardMarkup()
        btn_back = types.InlineKeyboardButton("⬅️ Назад к выбору дня", callback_data="back_to_schedule_menu")
        markup.add(btn_back)
        bot.send_message(chat_id, f"**Расписание на сегодня ({current_day_name}):**\n\n{day_schedule}", parse_mode="Markdown", reply_markup=markup)
        try: bot.delete_message(chat_id=chat_id, message_id=message_id)
        except: pass

    elif call.data.startswith("schedule_day_"):
        bot.answer_callback_query(call.id, "Загружаю расписание...")

        group_id_to_show = None
        if is_admin_user and user_id in admin_schedule_view_state:
            group_id_to_show = admin_schedule_view_state[user_id]
        else:
            group_id_to_show = db.get_user_group(user_id)
        
        if not group_id_to_show:
            bot.send_message(chat_id, "Пожалуйста, сначала выбери свой класс.")
            return

        full_schedule = db.get_schedule_for_group(group_id_to_show)
        if not full_schedule:
            bot.send_message(chat_id, "Расписание для этой группы еще не заполнено.")
            return

        days_of_week_full = ["Понедельник", "Вторник", "Среда", "Четверг", "Пятница", "Суббота", "Воскресенье"]
        day_index = int(call.data.split('_')[-1])
        current_day_name = days_of_week_full[day_index]
        day_schedule = schedule_module.parse_schedule_for_day(full_schedule, current_day_name)
        
        markup = types.InlineKeyboardMarkup()
        btn_back = types.InlineKeyboardButton("⬅️ Назад к выбору дня", callback_data="back_to_schedule_menu")
        markup.add(btn_back)
        bot.send_message(chat_id, f"**Расписание на {current_day_name}:**\n\n{day_schedule}", parse_mode="Markdown", reply_markup=markup)
        try: bot.delete_message(chat_id=chat_id, message_id=message_id)
        except: pass

    elif call.data == "schedule_week":
        bot.answer_callback_query(call.id, "Загружаю расписание...")

        group_id_to_show = None
        if is_admin_user and user_id in admin_schedule_view_state:
            group_id_to_show = admin_schedule_view_state[user_id]
        else:
            group_id_to_show = db.get_user_group(user_id)
        
        if not group_id_to_show:
            bot.send_message(chat_id, "Пожалуйста, сначала выбери свой класс.")
            return

        full_schedule = db.get_schedule_for_group(group_id_to_show)
        markup = types.InlineKeyboardMarkup()
        btn_back = types.InlineKeyboardButton("⬅️ Назад к выбору дня", callback_data="back_to_schedule_menu")
        markup.add(btn_back)
        if full_schedule:
            bot.send_message(chat_id, f"**Расписание на неделю:**\n\n{full_schedule}", parse_mode="Markdown", reply_markup=markup)
        else:
            bot.send_message(chat_id, "Расписание для этой группы еще не заполнено.", reply_markup=markup)
        try: bot.delete_message(chat_id=chat_id, message_id=message_id)
        except: pass
    
    elif call.data == "back_to_schedule_menu":
        bot.answer_callback_query(call.id)
        bot.delete_message(chat_id=chat_id, message_id=message_id)
        
        if is_admin_user:
             group_id = admin_schedule_view_state.get(user_id)
             group_info = db.get_group_info(group_id) if group_id else None
             group_name_full = f"{group_info[2]}{group_info[1]}" if group_info else "..."
             bot.send_message(
                chat_id,
                f"Что интересует по расписанию для группы **{group_name_full}**?",
                reply_markup=get_admin_schedule_menu(),
                parse_mode="Markdown"
            )
        else:
            bot.send_message(chat_id, "Что интересует по расписанию?", reply_markup=get_schedule_menu())
    
    elif call.data == "back_to_main_from_schedule":
        bot.answer_callback_query(call.id)
        bot.delete_message(chat_id=chat_id, message_id=message_id)
        bot.send_message(chat_id, "Главное меню", reply_markup=get_main_menu_with_admin_button(is_admin_user))

    # ... (остальной код без изменений) ...
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
    
    elif call.data == "faq_solved":
        bot.answer_callback_query(call.id, "Отлично!")
        bot.edit_message_text(chat_id=chat_id, message_id=message_id, text="Рад был помочь! Если возникнут другие вопросы, обращайся.", reply_markup=None)
    
    elif call.data == "faq_not_solved":
        bot.answer_callback_query(call.id, "Создаю запрос в техподдержку...")
        support_module.create_ticket_after_faq(call, bot)
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
        bot.send_message(chat_id, "Главное меню", reply_markup=get_main_menu_with_admin_button(is_admin_user))

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

    elif is_admin_user:
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
            requests = db.get_all_support_requests()
            if not requests:
                bot.answer_callback_query(call.id)
                markup = types.InlineKeyboardMarkup()
                btn_back = types.InlineKeyboardButton("⬅️ Назад", callback_data="admin_manage_requests")
                markup.add(btn_back)
                bot.edit_message_text(chat_id=chat_id, message_id=message_id, text="На данный момент нет запросов для удаления.", reply_markup=markup)
                return

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
        
        elif call.data == "admin_manage_classes":
            bot.answer_callback_query(call.id)
            admin_module.show_manage_classes_panel(bot, chat_id, message_id)
        elif call.data == "admin_add_group":
            bot.answer_callback_query(call.id)
            admin_module.start_add_group_flow(bot, chat_id)
            try: bot.delete_message(chat_id, message_id)
            except: pass
        elif call.data == "admin_delete_group":
            bot.answer_callback_query(call.id)
            admin_module.show_deletable_groups_list(bot, chat_id, message_id)
        elif call.data.startswith("admin_confirm_delete_group_"):
            group_id = int(call.data.split('_')[-1])
            admin_module.confirm_delete_group(bot, chat_id, message_id, group_id)
        elif call.data.startswith("admin_do_delete_group_"):
            group_id = int(call.data.split('_')[-1])
            admin_module.do_delete_group(bot, call, group_id)
            
        elif call.data == "admin_manage_schedule":
            bot.answer_callback_query(call.id, "Управление расписанием...")
            schedule_module.show_manage_schedule_panel(bot, chat_id, message_id)
        elif call.data == "admin_schedule_update":
            bot.answer_callback_query(call.id)
            schedule_module.select_group_for_schedule_update(bot, chat_id)
            try: bot.delete_message(chat_id, message_id)
            except: pass
        elif call.data.startswith("admin_set_schedule_for_group_"):
            group_id = int(call.data.split('_')[-1])
            schedule_module.start_schedule_update_flow(bot, chat_id, admin_module.admin_states, group_id)
            try: bot.delete_message(chat_id, message_id)
            except: pass
            
        elif call.data == "admin_schedule_delete_confirm":
             bot.answer_callback_query(call.id)
             schedule_module.select_group_for_schedule_delete(bot, chat_id, message_id)
        
        elif call.data.startswith("admin_confirm_delete_schedule_for_group_"):
            group_id = int(call.data.split('_')[-1])
            schedule_module.confirm_schedule_delete_for_group(bot, chat_id, message_id, group_id)

        elif call.data.startswith("admin_do_delete_schedule_for_group_"):
            group_id = int(call.data.split('_')[-1])
            if db.update_schedule(group_id, None):
                bot.answer_callback_query(call.id, "Расписание для группы очищено.", show_alert=True)
                schedule_module.show_manage_schedule_panel(bot, chat_id, message_id)
            else:
                bot.answer_callback_query(call.id, "Ошибка при очистке расписания.", show_alert=True)


@bot.message_handler(func=lambda message: support_module.user_support_states.get(message.chat.id, {}).get('state') == support_module.SUPPORT_STATE_AWAITING_DESCRIPTION)
def process_support_message(message):
    support_module.process_support_description(message, bot)

@bot.message_handler(func=lambda message: support_module.user_support_states.get(message.chat.id, {}).get('state') == support_module.SUPPORT_STATE_AWAITING_REPLY)
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

@bot.message_handler(func=lambda message: admin_module.is_admin(message.from_user.id) and admin_module.admin_states.get(message.chat.id) == admin_module.ADMIN_STATE_AWAITING_GROUP_NAME)
def process_admin_add_group_message(message):
    admin_module.process_add_group(message, bot)

@bot.message_handler(func=lambda message: admin_module.is_admin(message.from_user.id) and admin_module.admin_states.get(message.chat.id, {}).get('state') == schedule_module.ADMIN_STATE_AWAITING_SCHEDULE_TEXT)
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