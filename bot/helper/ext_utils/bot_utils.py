from aiohttp import ClientSession
from asyncio import create_subprocess_shell, create_subprocess_exec, run_coroutine_threadsafe, gather, sleep
from asyncio.subprocess import PIPE
from concurrent.futures import ThreadPoolExecutor
from functools import partial, wraps
from pyrogram.types import Message
from re import search as re_search, compile as re_compile, escape
from time import time
from os import path as ospath
import json
import html

from bot import bot, bot_loop, task_dict, task_dict_lock, user_data, config_dict, DATABASE_URL, LOGGER
from bot.helper.ext_utils.languages import LANG_MAP
from bot.helper.ext_utils.db_handler import DbManager
from bot.helper.telegram_helper.button_build import ButtonMaker
from bot.helper.ext_utils.status_utils import get_readable_file_size, get_readable_time

THREADPOOL = ThreadPoolExecutor(max_workers=1000)


class setInterval:
    def __init__(self, interval, action, *args, **kwargs):
        self.interval = interval
        self.action = action
        self.task = bot_loop.create_task(self._set_interval(*args, **kwargs))

    async def _set_interval(self, *args, **kwargs):
        while True:
            await sleep(self.interval)
            await self.action(*args, **kwargs)

    def cancel(self):
        self.task.cancel()


class UserDaily:
    def __init__(self, user_id):
        self._user_id = user_id

    async def get_daily_limit(self):
        await self._check_status()
        return user_data[self._user_id]['daily_limit'] >= config_dict['DAILY_LIMIT_SIZE'] * 1024**3

    async def set_daily_limit(self, size):
        await self._check_status()
        data = user_data[self._user_id]['daily_limit'] + size
        await update_user_ldata(self._user_id, 'daily_limit', data)

    async def _check_status(self):
        if not user_data.get(self._user_id, {}).get('daily_limit') or user_data.get(self._user_id, {}).get('reset_limit') - time() <= 0:
            await self._reset()

    async def _reset(self):
        await gather(update_user_ldata(self._user_id, 'daily_limit', 1), update_user_ldata(self._user_id, 'reset_limit', time() + 86400))


def bt_selection_buttons(id_: int):
    gid = id_[:12] if len(id_) > 20 else id_
    pincode = ''.join([n for n in id_ if n.isdigit()][:4])
    buttons = ButtonMaker()
    BASE_URL = config_dict['BASE_URL']
    if config_dict['WEB_PINCODE']:
        buttons.button_link('Select Files', f'{BASE_URL}/app/files/{id_}')
        buttons.button_data('Pincode', f'btsel pin {gid} {pincode}')
    else:
        buttons.button_link('Select Files', f'{BASE_URL}/app/files/{id_}?pin_code={pincode}')
    buttons.button_data('Done Selecting', f'btsel done {gid} {id_}')
    buttons.button_data('Cancel', f'btsel canc {gid} {id_}')
    return buttons.build_menu(2)


async def get_user_task(user_id: int):
    async with task_dict_lock:
        uid_count = sum(task.listener.user_id == user_id for task in task_dict.values())
    return uid_count


def presuf_remname_name(user_dict: int, name: str):
    if name:
        prename = user_dict.get('prename', '')
        sufname = user_dict.get('sufname', '')
        remname = user_dict.get('remname', '')
        LEECH_FILENAME_PREFIX = config_dict['LEECH_FILENAME_PREFIX']

        name = f'{prename} {name}'.strip()
        if sufname and '.' in name:
            fname, ext = name.rsplit('.', maxsplit=1)
            name = f'{fname} {sufname}.{ext}'

        name = f'{LEECH_FILENAME_PREFIX} {name}'.strip()
        if remname:
            remname_regex = re_compile('|'.join(map(escape, remname.split('|'))))
            name = remname_regex.sub('', name)

    return name


def is_premium_user(user_id: int):
    user_dict = user_data.get(user_id, {})
    return user_id == config_dict['OWNER_ID'] or (config_dict['PREMIUM_MODE'] and user_dict.get('is_premium')) or user_dict.get('is_sudo')


async def default_button(message: Message):
    try:
        message = await bot.get_messages(message.chat.id, message.id)
    except:
        pass
    else:
        del message.reply_markup.inline_keyboard[-1]

    return message.reply_markup if getattr(message.reply_markup, 'inline_keyboard', None) else None


def getSizeBytes(size):
    size = size.lower()
    unit_to_factor = {'mb': 1048576, 'gb': 1073741824}
    for unit, factor in unit_to_factor.items():
        if size.endswith(unit):
            size = float(size[:-len(unit)]) * factor
            return int(size)
    return 0


async def get_content_type(url):
    try:
        async with ClientSession() as session, session.get(url, allow_redirects=True, ssl=False) as response:
            return response.headers.get('Content-Type'), response.headers.get('Content-Length')
    except:
        return '', ''


def arg_parser(items, arg_base):
    if not items:
        return arg_base
    bool_arg_set = ['-b', '-e', '-z', '-s', '-j', '-d', '-gf', '-vt', '-sv', '-ss']
    i, t = 0, len(items)
    while i + 1 <= t:
        part = items[i].strip()
        if part in arg_base:
            if i + 1 == t and part in bool_arg_set or part in ['-s', '-j', '-gf', '-vt']:
                arg_base[part] = True
            else:
                sub_list = []
                for j in range(i + 1, t):
                    item = items[j].strip()
                    if item in arg_base:
                        if part in bool_arg_set and not sub_list:
                            arg_base[part] = True
                        break
                    sub_list.append(item.strip())
                    i += 1
                if sub_list:
                    arg_base[part] = ' '.join(sub_list)
        i += 1

    if items[0] not in arg_base:
        index_link = next((i for i, part in enumerate(items) if part in arg_base), len(items))
        link = items[:index_link] if index_link else items[:]
        link = ' '.join(link).strip()
        pattern = r'https?:\/\/(www.)?\S+\.?[a-z]{2,6}\b(\S*)|magnet:\?xt=urn:(btih|btmh):[-a-zA-Z0-9@:%_\+.~#?&//=]*\s*'
        if match := re_search(pattern, link):
            link = match.group()
        arg_base['link'] = link
    return arg_base


async def update_user_ldata(id_: int, key: str, value):
    user_data.setdefault(id_, {})[key] = value
    if DATABASE_URL and key not in ['thumb', 'rclone_config', 'token_pickle']:
        await DbManager().update_user_data(id_)


async def retry_function(attempt, func, *args, **kwargs):
    while attempt < 5:
        try:
            return await sync_to_async(func, *args, **kwargs)
        except:  # Consider specifying the exception if possible
            await sleep(0.3)
            attempt += 1
    raise Exception(f'Failed to execute {func.__name__}, reached max total attempts {attempt}x!')


async def cmd_exec(cmd, shell=False):
    if shell:
        proc = await create_subprocess_shell(cmd, stdout=PIPE, stderr=PIPE)
    else:
        proc = await create_subprocess_exec(*cmd, stdout=PIPE, stderr=PIPE)
    stdout, stderr = await proc.communicate()
    return stdout.decode().strip(), stderr.decode().strip(), proc.returncode


def new_task(func):
    @wraps(func)
    def wrapper(*args, **kwargs):
        return bot_loop.create_task(func(*args, **kwargs))
    return wrapper


async def sync_to_async(func, *args, wait=True, **kwargs):
    """Run sync function in async coroutine"""
    pfunc = partial(func, *args, **kwargs)
    future = bot_loop.run_in_executor(THREADPOOL, pfunc)
    return await future if wait else future


def async_to_sync(func, *args, wait=True, **kwargs):
    """Run Async function in sync"""
    future = run_coroutine_threadsafe(func(*args, **kwargs), bot_loop)
    return future.result() if wait else future


def get_seconds(time_str):
    if not time_str:
        return 0
    time_str = time_str.lower().replace('/', ' ')
    periods = [('days', 86400), ('day', 86400), ('d', 86400),
               ('hours', 3600), ('hour', 3600), ('h', 3600),
               ('minutes', 60), ('minute', 60), ('min', 60), ('m', 60),
               ('seconds', 1), ('second', 1), ('sec', 1), ('s', 1)]
    total_seconds = 0
    for period_name, period_seconds in periods:
        if match := re_search(f'(\d+)\s*{period_name}', time_str):
            total_seconds += int(match.group(1)) * period_seconds
            time_str = time_str.replace(match.group(0), '')
    return total_seconds


def new_thread(func):
    @wraps(func)
    def wrapper(*args, wait=False, **kwargs):
        future = run_coroutine_threadsafe(func(*args, **kwargs), bot_loop)
        return future.result() if wait else future
    return wrapper

# Caption Utils Logic
async def get_metadata(path):
    try:
        result = await cmd_exec(['ffprobe', '-hide_banner', '-loglevel', 'error', '-print_format', 'json', '-show_streams', '-show_format', path])
        if result[1]:
            LOGGER.warning(f'CapUtils FFprobe Warning: {result[1]}')

        if result[0]:
            return json.loads(result[0])
    except Exception as e:
        LOGGER.error(f'CapUtils FFprobe Error: {e}')
    return {}

def _get_quality(metadata):
    if not metadata.get('streams'):
        return 'Unknown'

    for stream in metadata['streams']:
        if stream.get('codec_type') == 'video':
            height = stream.get('height')
            if not height:
                continue

            if height <= 480: return '480p'
            elif height <= 576: return '576p'
            elif height <= 720: return '720p'
            elif height <= 1080: return '1080p'
            elif height <= 1440: return '2K'
            elif height <= 2160: return '4K'
            elif height <= 4320: return '8K'
            else: return f'{height}p'
    return 'Unknown'

def _get_languages(metadata, stream_type):
    """
    Returns languages in the SAME ORDER as streams appear in metadata
    Converts ISO codes to full language names
    """
    if not metadata.get('streams'):
        return 'Unknown'

    langs = []
    seen = set()

    for stream in metadata['streams']:
        if stream.get('codec_type') != stream_type:
            continue

        tags = stream.get('tags', {})
        lang = (tags.get('language') or tags.get('LANGUAGE') or '').lower()

        if not lang:
            continue

        full = LANG_MAP.get(lang, lang.capitalize())

        # Preserve order, remove duplicates
        if full not in seen:
            langs.append(full)
            seen.add(full)

    return ', '.join(langs) if langs else 'Unknown'

def _get_duration(metadata):
    if not metadata.get('format'):
        return 'Unknown'
    duration = float(metadata['format'].get('duration', 0))
    return get_readable_time(duration)

def _get_resolution(metadata):
    if not metadata.get('streams'):
        return 'Unknown'

    for stream in metadata['streams']:
        if stream.get('codec_type') == 'video':
            width = stream.get('width')
            height = stream.get('height')
            if width and height:
                return f'{width}x{height}'
    return 'Unknown'

def _get_codec(metadata, stream_type='video'):
    if not metadata.get('streams'):
        return 'Unknown'

    for stream in metadata['streams']:
        if stream.get('codec_type') == stream_type:
            codec_name = stream.get('codec_name')
            if codec_name:
                codec_map = {
                    'h264': 'AVC',
                    'hevc': 'HEVC',
                    'aac': 'AAC',
                    'ac3': 'AC3',
                    'eac3': 'EAC3',
                    'dts': 'DTS',
                    'truehd': 'TrueHD',
                    'flac': 'FLAC',
                    'mp3': 'MP3',
                    'opus': 'Opus',
                    'vorbis': 'Vorbis',
                    'av1': 'AV1',
                    'vp9': 'VP9',
                    'subrip': 'SRT',
                    'ass': 'ASS',
                }
                return codec_map.get(codec_name, codec_name)
    return 'Unknown'

async def replace_caption(caption_template, path, size_bytes):
    if not caption_template:
        return ''

    tags = ['{quality}', '{languages}', '{subtitles}', '{duration}', '{resolution}', '{codec}']
    metadata = {}
    if any(tag in caption_template for tag in tags):
        metadata = await get_metadata(path)

    filename = ospath.basename(path)
    size = get_readable_file_size(size_bytes)

    quality = _get_quality(metadata)
    languages = _get_languages(metadata, 'audio')
    subtitles = _get_languages(metadata, 'subtitle')
    duration = _get_duration(metadata)
    resolution = _get_resolution(metadata)
    codec = _get_codec(metadata, 'video')

    caption = caption_template.replace('{filename}', html.escape(filename))
    caption = caption.replace('{size}', html.escape(size))
    caption = caption.replace('{quality}', html.escape(quality))
    caption = caption.replace('{languages}', html.escape(languages))
    caption = caption.replace('{subtitles}', html.escape(subtitles))
    caption = caption.replace('{duration}', html.escape(duration))
    caption = caption.replace('{resolution}', html.escape(resolution))
    caption = caption.replace('{codec}', html.escape(codec))

    return caption
