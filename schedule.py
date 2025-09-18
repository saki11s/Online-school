from telebot import types
import re
import modules.database as db
import config

ADMIN_STATE_AWAITING_SCHEDULE_TEXT = 5

def get_manage_schedule_menu():
    """Возвращает меню управления расписанием для администратора."""
    markup = types.InlineKeyboardMarkup(row_width=1)
    btn_update_schedule = types.InlineKeyboardButton("Обновить/Задать расписание", callback_data="admin_schedule_update")
    btn_delete_schedule = types.InlineKeyboardButton("🗑️ Очистить расписание для группы", callback_data="admin_schedule_delete_confirm")
    btn_back_to_admin = types.InlineKeyboardButton("⬅️ Назад в Админ-панель", callback_data="admin_back_to_main")
    markup.add(btn_update_schedule, btn_delete_schedule, btn_back_to_admin)
    return markup

def show_manage_schedule_panel(bot, chat_id, message_id):
    """Показывает панель управления расписанием."""
    bot.edit_message_text(
        chat_id=chat_id,
        message_id=message_id,
        text="🗓️ **Управление расписанием**\n\nЗдесь вы можете задать или очистить расписание для конкретной группы.",
        reply_markup=get_manage_schedule_menu(),
        parse_mode="Markdown"
    )

def select_group_for_schedule_update(bot, chat_id):
    groups = db.get_all_groups_with_classes()
    if not groups:
        bot.send_message(chat_id, "Сначала нужно создать хотя бы одну группу в разделе 'Управление классами'.")
        return

    markup = types.InlineKeyboardMarkup(row_width=2)
    buttons = [types.InlineKeyboardButton(f"{class_num}{group_name}", callback_data=f"admin_set_schedule_for_group_{group_id}") for group_id, class_num, group_name in groups]
    markup.add(*buttons)
    markup.add(types.InlineKeyboardButton("⬅️ Назад", callback_data="admin_back_to_main"))
    bot.send_message(chat_id, "Выберите группу, для которой хотите задать расписание:", reply_markup=markup)


def start_schedule_update_flow(bot, chat_id, admin_states, group_id):
    """Начинает процесс обновления расписания для конкретной группы."""
    group_info = db.get_group_info(group_id)
    group_name_full = f"{group_info[2]}{group_info[1]}" if group_info else f"ID: {group_id}"

    template = (
        f"Пожалуйста, отправьте полное расписание на неделю для группы **{group_name_full}**.\n\n"
        "**Используйте строгий шаблон:**\n"
        "```\n"
        "Понедельник:\n"
        "10:00 - Предмет 1\n\n"
        "Вторник:\n"
        "11:00 - Предмет 2\n"
        "...\n"
        "```"
    )
    bot.send_message(chat_id, template, parse_mode="Markdown")
    admin_states[chat_id] = {'state': ADMIN_STATE_AWAITING_SCHEDULE_TEXT, 'group_id': group_id}

def process_schedule_update(message, bot, admin_states):
    """
    Обрабатывает, сохраняет новое расписание и уведомляет пользователей группы о конкретных изменениях.
    """
    chat_id = message.chat.id
    state_data = admin_states.get(chat_id)
    if not state_data or 'group_id' not in state_data:
        bot.send_message(chat_id, "Ошибка: не удалось определить группу. Попробуйте снова.")
        admin_states[chat_id] = 0
        return

    group_id = state_data['group_id']
    new_schedule_text = message.text
    
    old_schedule_text = db.get_schedule_for_group(group_id)

    old_schedule_dict = parse_schedule_to_dict(old_schedule_text)
    new_schedule_dict = parse_schedule_to_dict(new_schedule_text)

    changed_days = []
    all_days = sorted(list(set(old_schedule_dict.keys()) | set(new_schedule_dict.keys())), key=lambda x: ["Понедельник", "Вторник", "Среда", "Четверг", "Пятница", "Суббота", "Воскресенье"].index(x))

    for day in all_days:
        old_day_schedule = old_schedule_dict.get(day, "").strip()
        new_day_schedule = new_schedule_dict.get(day, "").strip()

        if old_day_schedule != new_day_schedule:
            changed_days.append(day)

    if db.update_schedule(group_id, new_schedule_text):
        bot.send_message(message.chat.id, "✅ Расписание успешно обновлено!")
        notify_group_users_about_schedule_update(bot, group_id, changed_days, is_major_update=(not old_schedule_text))
    else:
        bot.send_message(message.chat.id, "❌ Произошла ошибка при обновлении расписания.")
    
    admin_states[chat_id] = 0

def parse_schedule_to_dict(full_text):
    """Разбирает полный текст расписания в словарь."""
    if not full_text:
        return {}
    
    days = ["Понедельник", "Вторник", "Среда", "Четверг", "Пятница", "Суббота", "Воскресенье"]
    schedule_dict = {}
    
    pattern = re.compile(r'^\s*(' + '|'.join(days) + '):', re.MULTILINE | re.IGNORECASE)
    
    matches = list(pattern.finditer(full_text))
    
    if not matches:
        return {}

    for i, match in enumerate(matches):
        day_name = match.group(1).capitalize()
        start_pos = match.end()
        
        end_pos = matches[i+1].start() if i + 1 < len(matches) else len(full_text)
        
        schedule_content = full_text[start_pos:end_pos].strip()
        schedule_dict[day_name] = schedule_content

    return schedule_dict

def parse_schedule_for_day(full_text, day_name):
    """Получает расписание на конкретный день из полного текста."""
    if not full_text:
        return "Расписание еще не заполнено."
    
    schedule_by_days = parse_schedule_to_dict(full_text)
    
    schedule_for_day = schedule_by_days.get(day_name)
    
    if schedule_for_day:
        return schedule_for_day
    else:
        return "На этот день занятий не найдено."

def notify_group_users_about_schedule_update(bot, group_id, changed_days, is_major_update=False):
    """Отправляет пользователям конкретной группы уведомление об обновлении расписания."""
    
    if not changed_days and not is_major_update:
        print("Изменений в расписании не найдено, уведомления не отправляются.")
        return

    user_ids_in_group = db.get_user_ids_for_group(group_id)
    if not user_ids_in_group:
        print(f"Нет пользователей в группе {group_id} для уведомления.")
        return
        
    notification_text = ""
    if is_major_update:
        notification_text = "🔔 **Опубликовано новое расписание для вашего класса!**"
    elif len(changed_days) > 3:
        notification_text = "🔔 **Внимание, произошли значительные изменения в вашем расписании!**"
    else:
        days_str = "\n- ".join(changed_days)
        notification_text = f"🔔 **Внимание, изменения в вашем расписании!**\n\nОбновлено расписание на следующие дни:\n- {days_str}"

    markup = types.InlineKeyboardMarkup(row_width=1)
    btn_view_schedule = types.InlineKeyboardButton("🗓️ Посмотреть актуальное расписание", callback_data="schedule_week")
    markup.add(btn_view_schedule)

    for user_id in user_ids_in_group:
        try:
            bot.send_message(
                user_id,
                notification_text,
                parse_mode="Markdown",
                reply_markup=markup
            )
        except Exception as e:
            print(f"Не удалось отправить уведомление об обновлении расписания пользователю {user_id}: {e}")

def select_group_for_schedule_delete(bot, chat_id, message_id):
    groups = db.get_all_groups_with_classes()
    if not groups:
        bot.edit_message_text(chat_id, message_id, "Нет групп, для которых можно было бы удалить расписание.", reply_markup=types.InlineKeyboardMarkup().add(types.InlineKeyboardButton("⬅️ Назад", callback_data="admin_manage_schedule")))
        return

    markup = types.InlineKeyboardMarkup(row_width=2)
    buttons = [types.InlineKeyboardButton(f"🗑️ {class_num}{group_name}", callback_data=f"admin_confirm_delete_schedule_for_group_{group_id}") for group_id, class_num, group_name in groups]
    markup.add(*buttons)
    markup.add(types.InlineKeyboardButton("⬅️ Назад", callback_data="admin_manage_schedule"))
    bot.edit_message_text(chat_id, message_id, "Выберите группу, для которой хотите очистить расписание:", reply_markup=markup)

def confirm_schedule_delete_for_group(bot, chat_id, message_id, group_id):
    group_info = db.get_group_info(group_id)
    if not group_info: return
    group_name_full = f"{group_info[2]}{group_info[1]}"
    
    markup = types.InlineKeyboardMarkup(row_width=2)
    btn_yes = types.InlineKeyboardButton("Да, очистить", callback_data=f"admin_do_delete_schedule_for_group_{group_id}")
    btn_no = types.InlineKeyboardButton("Отмена", callback_data="admin_schedule_delete_confirm")
    markup.add(btn_yes, btn_no)
    bot.edit_message_text(chat_id, message_id, f"⚠️ Вы уверены, что хотите полностью очистить расписание для группы **{group_name_full}**?", reply_markup=markup, parse_mode="Markdown")