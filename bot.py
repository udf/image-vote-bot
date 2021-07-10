import asyncio
import os
import logging
import struct
from datetime import timedelta
from base64 import b85decode, b85encode

import cbor2
import telethon
from telethon import TelegramClient, events, tl
from telethon.tl.types import KeyboardButtonCallback

from common import GROUP_ID, CHANNEL
import button_dispatcher
from button_dispatcher import do_nothing

logging.basicConfig(level=logging.INFO)
client = TelegramClient('bot', 6, 'eb06d4abfb49dc3eeb1aeb98ae0f581e')


def get_badge(text, count):
  if count:
    return f'{text} {count}'
  return text


def decode_message_data(text):
  if not text:
    return {'u': set(), 'd': set()}
  return cbor2.loads(b85decode(text.encode('ascii')))


def encode_message_data(u=set(), d=set()):
  return b85encode(cbor2.dumps({'u': u, 'd': d}))


async def update_message(edit, buttons, data):
  second_row = []
  if len(data['u']) >= 2:
    second_row = [on_post.get_button('Post')]
  await edit(
    encode_message_data(**data),
    parse_mode=None,
    buttons=[
      [
        on_upvote.get_button(get_badge('👍', len(data['u']))),
        on_downvote.get_button(get_badge('👎', len(data['d']))),
      ],
      second_row
    ]
  )


@button_dispatcher.register(1)
async def on_upvote(event):
  m = await event.get_message()
  data = decode_message_data(m.raw_text)
  uid = event.query.user_id
  data['u'] = data['u'] ^ {uid}
  data['d'].discard(uid)
  await update_message(event.edit, m.buttons, data)


@button_dispatcher.register(2)
async def on_downvote(event):
  m = await event.get_message()
  data = decode_message_data(m.raw_text)
  uid = event.query.user_id
  data['d'] = data['d'] ^ {uid}
  data['u'].discard(uid)
  await update_message(event.edit, data)


@button_dispatcher.register(3)
async def on_delete(event, *, pending_confirms=set()):
  _, clicker_id = struct.unpack('!BQ', event.data)
  if clicker_id != event.query.user_id:
    await event.answer(message='Only the owner of the original message can delete!')
    return
  confirm_id = (event.message_id, event.chat_instance)
  if confirm_id not in pending_confirms:
    await event.answer(message='Are you sure? Tap delete again to confirm')
    pending_confirms.add(confirm_id)
    await asyncio.sleep(10)
    pending_confirms.discard(confirm_id)
    return

  pending_confirms.discard(confirm_id)
  await event.answer(message='Message deleted')
  await event.delete()


@button_dispatcher.register(4)
async def on_post(event):
  m = await event.get_message()
  await client.send_message(
    CHANNEL,
    file=m.media, schedule=timedelta(hours=12)
  )
  await m.edit(message='', buttons=[[
    do_nothing.get_button('Scheduled')
  ]])


@client.on(events.NewMessage(chats=GROUP_ID))
async def on_image(event):
  m = event.message
  if not isinstance(m.media, tl.types.MessageMediaPhoto):
    return
  await event.respond(file=m.media, buttons=[[
    on_upvote.get_button('👍'),
    on_downvote.get_button('👎'),
    on_delete.get_button('🗑', struct.pack('!Q', event.message.sender_id))
  ]])


async def main():
  await client.start(bot_token=os.environ['TOKEN'])
  client.add_event_handler(button_dispatcher.dispatch)
  await client.run_until_disconnected()


client.loop.run_until_complete(main())