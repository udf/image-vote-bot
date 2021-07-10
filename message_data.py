import functools
from itertools import zip_longest
from base64 import b85decode, b85encode

import cbor2


class MessageData:
  prop_names = ['owner', 'likes', 'dislikes']
  prop_defaults = {
    'owner': lambda: 0,
    'likes': lambda: set(),
    'dislikes': lambda: set(),
  }

  def __init__(self, text=''):
    data = []
    if text:
      data = cbor2.loads(b85decode(text.encode('ascii')))
    for key, value in zip_longest(MessageData.prop_names, data):
      if value is None:
        value = MessageData.prop_defaults[key]()
      setattr(self, key, value)

  def encode(self):
    data = []
    for key in MessageData.prop_names:
      data.append(getattr(self, key))
    return b85encode(cbor2.dumps(data)).decode('ascii')


def parse_data(get_text):
  def wrapper(func):
    @functools.wraps(func)
    async def wrapped(*args, **kwargs):
      data = MessageData(await get_text(*args, **kwargs))
      return await func(*args, **kwargs, data=data)
    return wrapped
  return wrapper