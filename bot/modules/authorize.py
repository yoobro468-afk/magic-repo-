from pyrogram.filters import command
from pyrogram.handlers import MessageHandler
from pyrogram.types import Message
from time import time

from bot import bot, user_data
from bot.helper.ext_utils.bot_utils import update_user_ldata, new_task
from bot.helper.telegram_helper.bot_commands import BotCommands
from bot.helper.telegram_helper.filters import CustomFilters
from bot.helper.telegram_helper.message_utils import sendMessage, auto_delete_message


@new_task
async def authorize(_, message: Message):
    msg = message.text.split()
    if len(msg) > 1:
        id_ = int(msg[1].strip())
    elif reply_to := message.reply_to_message:
        id_ = reply_to.from_user.id if reply_to.from_user else reply_to.sender_chat.id
    else:
        id_ = message.chat.id
    if id_ in user_data and user_data.get(id_, {}).get('is_auth'):
        msg = 'Already Authorized'
    else:
        await update_user_ldata(id_, 'is_auth', True)
        msg = 'Authorized Successfully ✅️'
    msg = await sendMessage(msg, message)
    await auto_delete_message(message, msg)


@new_task
async def unauthorize(_, message: Message):
    msg = message.text.split()
    if len(msg) > 1:
        id_ = int(msg[1].strip())
    elif reply_to := message.reply_to_message:
        id_ = reply_to.from_user.id if reply_to.from_user else reply_to.sender_chat.id
    else:
        id_ = message.chat.id
    if id_ not in user_data or user_data.get(id_, {}).get('is_auth'):
        await update_user_ldata(id_, 'is_auth', False)
        msg = 'Unauthorized Successfully'
    else:
        msg = 'Already Unauthorized'
    msg = await sendMessage(msg, message)
    await auto_delete_message(message, msg)


@new_task
async def addSudo(_, message: Message):
    id_ = day = ''
    msg = message.text.split()
    if len(msg) > 1:
        id_ = int(msg[1].strip())
        if len(msg) > 2 and msg[2].isdigit():
            day = int(msg[2])
    elif reply_to := message.reply_to_message:
        id_ = reply_to.from_user.id if reply_to.from_user else reply_to.sender_chat.id
        if len(msg) > 1 and msg[1].isdigit():
            day = int(msg[1])
    if id_:
        if day:
            await update_user_ldata(id_, 'sudo_left', int(time() + (86400 * int(msg[2]))))
        if user_data.get(id_, {}).get('is_sudo'):
            msg = 'Already Sudo Bae!'
        else:
            await update_user_ldata(id_, 'is_sudo', True)
            msg = 'Promoted as Sudo'
    else:
        msg = 'Give ID or Reply To message of whom you want to Promote Bae.'
    msg = await sendMessage(msg, message)
    await auto_delete_message(message, msg)


@new_task
async def removeSudo(_, message: Message):
    id_ = ''
    msg = message.text.split()
    if len(msg) > 1:
        id_ = int(msg[1].strip())
    elif reply_to := message.reply_to_message:
        id_ = reply_to.from_user.id if reply_to.from_user else reply_to.sender_chat.id
    if id_:
        if user_data.get(id_, {}).get('is_sudo'):
            user_data[id_].pop('sudo_left', None)
            await update_user_ldata(id_, 'is_sudo', False)
            msg = 'Demoted Bae!'
        else:
            msg = 'Currently not sudo Bae!'
    else:
        msg = 'Give ID or Reply To message of whom you want to remove from Sudo Bae.'
    msg = await sendMessage(msg, message)
    await auto_delete_message(message, msg)


@new_task
async def setLimit(_, message: Message):
    msg = message.text.split()
    try:
        if len(msg) > 2:
            id_ = int(msg[1].strip())
            limit_val = int(msg[2].strip())
        elif reply_to := message.reply_to_message:
            id_ = reply_to.from_user.id if reply_to.from_user else reply_to.sender_chat.id
            if len(msg) > 1 and msg[1].isdigit():
                limit_val = int(msg[1].strip())
            else:
                msg = await sendMessage('Give limit with reply!', message)
                await auto_delete_message(message, msg)
                return
        else:
            msg = await sendMessage('Give ID and limit or Reply To message with limit', message)
            await auto_delete_message(message, msg)
            return
    except ValueError:
        msg = await sendMessage('Invalid ID or limit!', message)
        await auto_delete_message(message, msg)
        return

    await update_user_ldata(id_, 'user_task_limit', limit_val)
    msg = await sendMessage(f'User task limit set to {limit_val} for {id_}', message)
    await auto_delete_message(message, msg)


@new_task
async def resetLimit(_, message: Message):
    msg = message.text.split()
    if len(msg) == 1 and not message.reply_to_message:
        await limitedUsers(_, message)
        return
    try:
        if len(msg) > 1:
            id_ = int(msg[1].strip())
        elif reply_to := message.reply_to_message:
            id_ = reply_to.from_user.id if reply_to.from_user else reply_to.sender_chat.id
    except ValueError:
        msg = await sendMessage('Invalid ID!', message)
        await auto_delete_message(message, msg)
        return

    if id_ in user_data and 'user_task_limit' in user_data[id_]:
        del user_data[id_]['user_task_limit']
        await update_user_ldata(id_, 'user_task_limit', None)
        msg = f'User task limit reset for {id_}'
    else:
        msg = 'No specific limit set for this user'
    msg = await sendMessage(msg, message)
    await auto_delete_message(message, msg)


@new_task
async def limitedUsers(_, message: Message):
    msg = "<b>Users with Custom Task Limits:</b>\n\n"
    count = 0
    for id_, data in user_data.items():
        if 'user_task_limit' in data:
            count += 1
            limit = data['user_task_limit']
            user_name = data.get('user_name') or data.get('first_name') or "Unknown"
            msg += f"{count}. <b>Name:</b> {user_name}\n"
            msg += f"   <b>ID:</b> <code>{id_}</code>\n"
            msg += f"   <b>Limit:</b> {limit} tasks\n\n"

    if count == 0:
        msg = "<b>No users found with custom task limits.</b>"

    msg = await sendMessage(msg, message)
    await auto_delete_message(message, msg)


bot.add_handler(MessageHandler(authorize, filters=command(BotCommands.AuthorizeCommand) & CustomFilters.sudo))
bot.add_handler(MessageHandler(unauthorize, filters=command(BotCommands.UnAuthorizeCommand) & CustomFilters.sudo))
bot.add_handler(MessageHandler(addSudo, filters=command(BotCommands.AddSudoCommand) & CustomFilters.owner))
bot.add_handler(MessageHandler(removeSudo, filters=command(BotCommands.RmSudoCommand) & CustomFilters.owner))
bot.add_handler(MessageHandler(setLimit, filters=command(BotCommands.SetLimitCommand) & CustomFilters.sudo))
bot.add_handler(MessageHandler(resetLimit, filters=command(BotCommands.ResetLimitCommand) & CustomFilters.sudo))
bot.add_handler(MessageHandler(limitedUsers, filters=command(BotCommands.LimitedUsersCommand) & CustomFilters.sudo))
