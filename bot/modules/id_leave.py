from pyrogram import Client
from pyrogram.filters import command
from pyrogram.handlers import MessageHandler
from pyrogram.types import Message

from bot import bot, LOGGER
from bot.helper.ext_utils.bot_utils import new_task
from bot.helper.telegram_helper.bot_commands import BotCommands
from bot.helper.telegram_helper.filters import CustomFilters
from bot.helper.telegram_helper.message_utils import sendMessage


@new_task
async def get_id(client: Client, message: Message):
    id_text = ""
    if reply_to := message.reply_to_message:
        if reply_to.forward_from:
            id_text = f"Forwarded from user ID: <code>{reply_to.forward_from.id}</code>"
        elif reply_to.forward_from_chat:
            id_text = f"Forwarded from chat ID: <code>{reply_to.forward_from_chat.id}</code>"
        elif reply_to.from_user:
            id_text = f"Replied user ID: <code>{reply_to.from_user.id}</code>"
        elif reply_to.sender_chat:
            id_text = f"Replied chat ID: <code>{reply_to.sender_chat.id}</code>"
    elif len(message.command) > 1:
        username = message.command[1]
        try:
            user = await client.get_users(username)
            id_text = f"User ID for {username}: <code>{user.id}</code>"
        except Exception as e:
            id_text = f"Error: {e}"
    else:
        id_text = f"Current Chat ID: <code>{message.chat.id}</code>"
        if message.from_user:
            id_text += f"\nYour ID: <code>{message.from_user.id}</code>"

    await sendMessage(id_text, message)


@new_task
async def leave_chat(client: Client, message: Message):
    chat_id = message.chat.id
    await sendMessage("Leaving this chat... Bye!", message)
    try:
        await client.leave_chat(chat_id)
    except Exception as e:
        LOGGER.error(f"Failed to leave chat {chat_id}: {e}")


bot.add_handler(MessageHandler(get_id, filters=command(BotCommands.IdCommand) & CustomFilters.authorized))
bot.add_handler(MessageHandler(leave_chat, filters=command(BotCommands.LeaveCommand) & CustomFilters.sudo))
