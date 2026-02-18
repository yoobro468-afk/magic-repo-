from pyrogram.filters import command
from pyrogram.handlers import MessageHandler
from pyrogram.types import Message
from aiofiles import open as aiopen
from os import remove as os_remove, path as ospath

from bot import bot, config_dict, LOGGER
from bot.helper.ext_utils.bot_utils import new_task
from bot.helper.ext_utils.links_utils import is_url, get_url_name, get_link, is_media
from bot.helper.ext_utils.media_utils import post_media_info
from bot.helper.ext_utils.status_utils import get_readable_file_size
from bot.helper.stream_utils.file_properties import gen_link
from bot.helper.telegram_helper.bot_commands import BotCommands
from bot.helper.telegram_helper.button_build import ButtonMaker
from bot.helper.telegram_helper.filters import CustomFilters
from bot.helper.telegram_helper.message_utils import sendMessage, sendPhoto, editPhoto, copyMessage, deleteMessage
from bot.helper.video_utils.executor import get_metavideo


@new_task
async def medinfo(_, message: Message):
    link = get_link(message)
    cmsg, media = None, None
    msg_to_use = None
    
    reply_to = message.reply_to_message
    if reply_to and (media := is_media(reply_to)):
        if (chat_id := config_dict['LEECH_LOG']):
            cmsg = await copyMessage(chat_id, reply_to)
            msg_to_use = cmsg if cmsg and is_media(cmsg) else reply_to
            link = (await gen_link(msg_to_use))[1]
        else:
            msg_to_use = reply_to

    img = config_dict['IMAGE_MEDINFO']

    if link and is_url(link):
        msg = await sendPhoto('<i>Processing, please wait...</i>', message, img)
        if (size := int((await get_metavideo(link))[1].get('size', 0))) and (result := await post_media_info(link, size, is_link=True)):
            buttons = ButtonMaker()
            buttons.button_link('Media Info', result)
            if not media:
                buttons.button_link('Source', link)
            await editPhoto(f'<b>MEDIA INFO RESULT</b>\n<code>{get_url_name(link)}</code>\n<b>Size:</b> {get_readable_file_size(size)}',
                            msg, img, buttons.build_menu(1))
        else:
            await editPhoto('Error when getting info!', msg, img)
            
    elif msg_to_use:
        # Optimized: Download only first 3 chunks (~3MB) for instant metadata
        msg = await sendPhoto('<i>Reading file metadata...</i>', message, img)
        file_name = getattr(media, 'file_name', '') 
        if not file_name:
            file_name = 'unknown_video.mp4' if getattr(media, 'mime_type', '').startswith('video') else 'unknown_file'
        
        total_size = getattr(media, 'file_size', 0)
        temp_file = f'mediainfo_{message.id}_{file_name}'
        
        try:
            async with aiopen(temp_file, 'wb') as f:
                # limit=3 chunks (approx 3MB)
                async for chunk in bot.stream_media(msg_to_use, limit=3):
                    await f.write(chunk)
            
            # Note: post_media_info will see the truncated size (3MB). 
            # We pass total_size to it, but post_media_info uses mediainfo output for detailed text.
            # Ideally, post_media_info should be patched to override 'File size', but for now
            # we rely on the header message showing the correct size.
            
            if result := await post_media_info(temp_file, total_size, is_link=False):
                buttons = ButtonMaker()
                buttons.button_link('Media Info', result)
                # Ensure the caption shows the REAL total size
                await editPhoto(f'<b>MEDIA INFO RESULT</b>\n<code>{file_name}</code>\n<b>Size:</b> {get_readable_file_size(total_size)}',
                                msg, img, buttons.build_menu(1))
            else:
                await editPhoto('Error when getting info from file!', msg, img)
        except Exception as e:
            LOGGER.error(f'MediaInfo Error: {e}')
            await editPhoto(f'Error: {e}', msg, img)
        finally:
            if ospath.exists(temp_file):
                os_remove(temp_file)
                
    else:
        await sendMessage('Send command along with link or by reply to the link/media!', message)

    if cmsg:
        await deleteMessage(cmsg)


bot.add_handler(MessageHandler(medinfo, command(BotCommands.MediaInfoCommand) & CustomFilters.authorized))
