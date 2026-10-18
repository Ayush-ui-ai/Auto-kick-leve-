import logging
import os
import json
import asyncio
from datetime import datetime
from threading import Thread

from flask import Flask
from telegram import Update, InlineKeyboardButton, InlineKeyboardMarkup
from telegram.ext import (
    Application, CommandHandler, MessageHandler, filters, 
    ContextTypes, ChatMemberHandler, ConversationHandler, CallbackQueryHandler
)

# ==========================================
# 1. KEEP ALIVE SERVER (Render Sleep Fix)
# ==========================================
web_app = Flask('')

@web_app.route('/')
def home():
    return "Bot is alive and running!"

def run_web():
    # Render automatically PORT assign karta hai
    port = int(os.environ.get('PORT', 8080))
    web_app.run(host='0.0.0.0', port=port)

def keep_alive():
    t = Thread(target=run_web)
    t.daemon = True # Main thread band hone par yeh bhi band ho jayega
    t.start()

# ==========================================
# 2. BOT CONFIGURATION & DATABASE (JSON)
# ==========================================
logging.basicConfig(format='%(asctime)s - %(name)s - %(levelname)s - %(message)s', level=logging.INFO)
logger = logging.getLogger(__name__)

# ⚠️ APNI DETAILS YAHAN DAALEIN
BOT_TOKEN = os.environ.get("BOT_TOKEN", "8976056344:AAHIqxW6IaWAXfL4OF2z66FARhfQTLC3J_E")
SUPER_ADMIN_ID = int(os.environ.get("ADMIN_ID", 7364948540)) # Apna ID daalein

START_PHOTO_URL = "https://i.ibb.co/h6ChB2C/file-0000000039708210b504e1a3e82675be.png" 
DB_FILE = "bot_data.json"

# Default Empty Database
TRACKED_CHATS = set()
CHAT_ADMINS = {} 
BANNED_USERS_LIST = [] 

def load_data():
    """Render restart hone par data wapas load karega"""
    global TRACKED_CHATS, CHAT_ADMINS, BANNED_USERS_LIST
    if os.path.exists(DB_FILE):
        try:
            with open(DB_FILE, 'r') as f:
                data = json.load(f)
                TRACKED_CHATS = set(data.get("tracked_chats", []))
                CHAT_ADMINS = data.get("chat_admins", {})
                BANNED_USERS_LIST = data.get("banned_users", [])
            logger.info("Database loaded successfully.")
        except Exception as e:
            logger.error(f"Error loading DB: {e}")

def save_data():
    """Data ko file me save karega"""
    data = {
        "tracked_chats": list(TRACKED_CHATS),
        "chat_admins": CHAT_ADMINS,
        "banned_users": BANNED_USERS_LIST[-100:] # Sirf last 100 save karein
    }
    with open(DB_FILE, 'w') as f:
        json.dump(data, f)

# ==========================================
# 3. BOT COMMANDS & HANDLERS
# ==========================================
async def start_command(update: Update, context: ContextTypes.DEFAULT_TYPE):
    caption_text = (
        "🛡️ **𝗖𝗵𝗮𝗻𝗻𝗲𝗹 𝗚𝘂𝗮𝗿𝗱 — 𝗣𝗿𝗲𝗺𝗶𝘂𝗺 𝗣𝗿𝗼𝘁𝗲𝗰𝘁𝗶𝗼𝗻 𝗕𝗼𝘁**\n\n"
        "🕵️ Automatically secures your channel or group by banning members who leave, so they can't rejoin and re-farm invite links.\n\n"
        "⚙ **How to activate:**\n"
        "✅ 1. Add me as admin to your channel or group\n"
        "✅ 2. Use /unban100 anytime to reverse the last 100 auto-bans\n\n"
        "🍃 *Protection runs automatically in the background — no setup required.*"
    )
    
    keyboard = [
        [
            InlineKeyboardButton("🚨 Add Channel", url=f"https://t.me/{context.bot.username}?startchannel=true"),
            InlineKeyboardButton("🚨 Add Group", url=f"https://t.me/{context.bot.username}?startgroup=true")
        ],
        [InlineKeyboardButton("✅ Usage & Dashboard", callback_data="dashboard")]
    ]
    reply_markup = InlineKeyboardMarkup(keyboard)
    
    try:
        await update.message.reply_photo(photo=START_PHOTO_URL, caption=caption_text, reply_markup=reply_markup, parse_mode="Markdown")
    except Exception:
        await update.message.reply_text(caption_text, reply_markup=reply_markup, parse_mode="Markdown")

async def track_chats(update: Update, context: ContextTypes.DEFAULT_TYPE):
    result = extract_status_change(update.my_chat_member)
    if result is None: return
    was_member, is_member = result
    chat = update.effective_chat
    user = update.effective_user 
    
    if not was_member and is_member:
        TRACKED_CHATS.add(chat.id)
        CHAT_ADMINS[str(chat.id)] = user.id # String key JSON ke liye
        save_data() # Save to file
    elif was_member and not is_member:
        TRACKED_CHATS.discard(chat.id)
        CHAT_ADMINS.pop(str(chat.id), None)
        save_data() # Save to file

async def handle_user_left(update: Update, context: ContextTypes.DEFAULT_TYPE):
    chat_member_update = update.chat_member
    if chat_member_update is None: return
    
    old_status = chat_member_update.old_chat_member.status
    new_status = chat_member_update.new_chat_member.status
    
    if old_status in ['member', 'administrator', 'creator'] and new_status == 'left':
        user = chat_member_update.new_chat_member.user
        chat = chat_member_update.chat
        
        try:
            await context.bot.ban_chat_member(chat_id=chat.id, user_id=user.id)
            
            # Save to DB
            BANNED_USERS_LIST.append({"chat_id": chat.id, "user_id": user.id})
            save_data()

        except Exception as e:
            logger.error(f"Failed to ban {user.id}: {e}")
            return
            
        current_time = datetime.now().strftime("%Y-%m-%d | %H:%M:%S")
        user_name = f"{user.first_name} {user.last_name or ''}".strip()
        user_username = f"@{user.username}" if user.username else "No Username"
        chat_username = f"@{chat.username}" if chat.username else "Private Channel"
        
        notif_text = (
            f"🚫 <b>User Left & Automatically Banned</b>\n"
            f"• Time: {current_time}\n\n"
            f"👤 <b>User Details</b>\n"
            f"<blockquote>• Name: {user_name}\n"
            f"• Username: {user_username}\n"
            f"• ID: <code>{user.id}</code></blockquote>\n\n"
            f"📢 <b>Channel Details</b>\n"
            f"<blockquote>• Name: {chat.title}\n"
            f"• Username: {chat_username}\n"
            f"• ID: <code>{chat.id}</code></blockquote>\n\n"
            f"⚡ <i>User left & was automatically banned.</i>"
        )
        
        keyboard = [[InlineKeyboardButton("♻️ Remove User (Unban)", callback_data=f"unban|{chat.id}|{user.id}")]]
        reply_markup = InlineKeyboardMarkup(keyboard)
        
        admin_id = CHAT_ADMINS.get(str(chat.id))
        try:
            if admin_id:
                await context.bot.send_message(chat_id=admin_id, text=notif_text, reply_markup=reply_markup, parse_mode="HTML")
        except Exception as e:
            logger.error(f"Could not notify admin: {e}")

async def unban100_command(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if not BANNED_USERS_LIST:
        await update.message.reply_text("✅ No banned users found in history.")
        return
        
    msg = await update.message.reply_text("⏳ Unbanning last 100 users, please wait...")
    success = 0
    
    for item in list(BANNED_USERS_LIST):
        try:
            await context.bot.unban_chat_member(chat_id=item["chat_id"], user_id=item["user_id"])
            success += 1
            await asyncio.sleep(0.3)
        except Exception:
            pass
            
    BANNED_USERS_LIST.clear()
    save_data()
    await msg.edit_text(f"✅ Successfully unbanned {success} users!")

async def unban_button_callback(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    await query.answer()
    
    data = query.data.split("|")
    if len(data) != 3: return
    
    _, chat_id, user_id = data
    chat_id, user_id = int(chat_id), int(user_id)
    
    try:
        await context.bot.unban_chat_member(chat_id=chat_id, user_id=user_id)
        await query.edit_message_text(
            text=query.message.text_html + "\n\n✅ <b>User has been unbanned successfully.</b>",
            parse_mode="HTML"
        )
    except Exception as e:
        await query.answer("Error: Could not unban user.", show_alert=True)

def extract_status_change(chat_member_update):
    if chat_member_update is None: return None
    old_status = chat_member_update.old_chat_member.status
    new_status = chat_member_update.new_chat_member.status
    return (old_status in ['member', 'administrator', 'creator'], new_status in ['member', 'administrator', 'creator'])

# --- BROADCAST SYSTEM ---
WAITING_FOR_BROADCAST_TEXT = 1

async def admin_command(update: Update, context: ContextTypes.DEFAULT_TYPE):
    user_id = update.effective_user.id
    if user_id != SUPER_ADMIN_ID:
        await update.message.reply_text("⛔ Aap authorized admin nahi hain.")
        return ConversationHandler.END
    
    await update.message.reply_text(
        f"📢 **Broadcast Panel**\n\nTotal Channels/Groups: {len(TRACKED_CHATS)}\n\n"
        "Jis message ko sabko bhejna hai, wo type karke bhejein.\n"
        "Cancel karne ke liye /cancel bhejein.",
        parse_mode="Markdown"
    )
    return WAITING_FOR_BROADCAST_TEXT

async def broadcast_message(update: Update, context: ContextTypes.DEFAULT_TYPE):
    broadcast_text = update.message.text
    
    if not TRACKED_CHATS:
        await update.message.reply_text("❌ Broadcast fail! Bot kisi bhi channel/group me nahi hai. Pehle bot ko add karein.")
        return ConversationHandler.END

    status_msg = await update.message.reply_text(f"⏳ Broadcasting to {len(TRACKED_CHATS)} chats...")
    success_count, fail_count = 0, 0
    
    for chat_id in list(TRACKED_CHATS):
        try:
            await context.bot.send_message(
                chat_id=chat_id, 
                text=f"📢 **Announcement**\n\n{broadcast_text}",
                parse_mode="Markdown"
            )
            success_count += 1
        except Exception as e:
            logger.error(f"Broadcast failed for {chat_id}: {e}")
            fail_count += 1
            # Agar bot ko kisi channel se nikal diya gaya hai
            if "chat not found" in str(e).lower() or "kicked" in str(e).lower():
                TRACKED_CHATS.discard(chat_id)
                save_data()
            
    await status_msg.edit_text(
        f"✅ Broadcast Completed!\n\n"
        f"Success: {success_count}\n"
        f"Failed: {fail_count}"
    )
    return ConversationHandler.END

async def cancel_broadcast(update: Update, context: ContextTypes.DEFAULT_TYPE):
    await update.message.reply_text("❌ Broadcast cancelled.")
    return ConversationHandler.END

# ==========================================
# 4. MAIN APPLICATION RUNNER
# ==========================================
def main():
    # Start Web Server for Render
    keep_alive()
    
    # Load previous data
    load_data()
    
    application = Application.builder().token(BOT_TOKEN).build()

    application.add_handler(CommandHandler("start", start_command))
    application.add_handler(CommandHandler("unban100", unban100_command))
    application.add_handler(ChatMemberHandler(track_chats, ChatMemberHandler.MY_CHAT_MEMBER))
    application.add_handler(ChatMemberHandler(handle_user_left, ChatMemberHandler.CHAT_MEMBER))
    application.add_handler(CallbackQueryHandler(unban_button_callback, pattern="^unban\\|"))

    broadcast_conv = ConversationHandler(
        entry_points=[CommandHandler("admin", admin_command)],
        states={
            WAITING_FOR_BROADCAST_TEXT: [MessageHandler(filters.TEXT & ~filters.COMMAND, broadcast_message)]
        },
        fallbacks=[CommandHandler("cancel", cancel_broadcast)]
    )
    application.add_handler(broadcast_conv)

    logger.info(f"Bot Started! Super Admin ID: {SUPER_ADMIN_ID}")
    application.run_polling(allowed_updates=Update.ALL_TYPES)

if __name__ == '__main__':
    main()