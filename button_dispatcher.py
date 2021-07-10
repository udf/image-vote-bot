import struct
import logging

from telethon import events
from telethon.tl.types import KeyboardButtonCallback

from common import GROUP_ID

logger = logging.getLogger('btn_dis')
CALLBACKS = {}
CALLBACK_ID_ATTR = '_btn_cb_id'
CALLBACK_DATA_FMT = '!B'


def register(callback_id):
  if callback_id in CALLBACKS:
    raise ValueError(f'Duplicate callback ID: {callback_id}')
  def wrapper(func):
    setattr(func, CALLBACK_ID_ATTR, callback_id)
    func.get_button = lambda text, extra_data=b'': get_button(text, func, extra_data)
    CALLBACKS[callback_id] = func
    return func
  return wrapper


@register(0)
async def do_nothing(event):
  pass


def get_button(text, func, extra_data=b''):
  callback_id = getattr(func, CALLBACK_ID_ATTR, None)
  if callback_id is None:
    raise ValueError('Function is not a registered button callback!')
  data = struct.pack(CALLBACK_DATA_FMT, callback_id) + extra_data
  return KeyboardButtonCallback(text, data)


@events.register(events.CallbackQuery(chats=GROUP_ID))
async def dispatch(event):
  callback_id, = struct.unpack_from(CALLBACK_DATA_FMT, event.data)
  callback = CALLBACKS.get(callback_id, None)
  if not callback:
    logger.warning(f'Not handling unknown callback with data {event.data}')
    return
  await callback(event)
  await event.answer()