import asyncio
import os
import logging
from datetime import timedelta

import telethon
from telethon import TelegramClient, events, tl
from telethon.tl.types import KeyboardButtonCallback

from common import GROUP_ID, CHANNEL
import button_dispatcher
from button_dispatcher import do_nothing
from message_data import parse_data, MessageData

logging.basicConfig(level=logging.INFO)
client = TelegramClient('bot', 6, 'eb06d4abfb49dc3eeb1aeb98ae0f581e')
client_user = TelegramClient('user', 6, 'eb06d4abfb49dc3eeb1aeb98ae0f581e')


def get_badge(text, count):
  if count:
    return f'{text} {count}'
  return text


async def update_message(edit, data):
  second_row = []
  if len(data.likes) >= 2:
    second_row = [on_post.get_button('Post')]
  await edit(
    data.encode(),
    parse_mode=None,
    buttons=[
      [
        on_upvote.get_button(get_badge('👍', len(data.likes))),
        on_downvote.get_button(get_badge('👎', len(data.dislikes))),
      ],
      second_row
    ]
  )


async def get_callback_message(event):
  m = await event.get_message()
  return m.raw_text


@button_dispatcher.register(1)
@parse_data(get_callback_message)
async def on_upvote(event, data):
  uid = event.query.user_id
  data.likes = data.likes ^ {uid}
  data.dislikes.discard(uid)
  await update_message(event.edit, data)


@button_dispatcher.register(2)
@parse_data(get_callback_message)
async def on_downvote(event, data):
  uid = event.query.user_id
  data.dislikes = data.dislikes ^ {uid}
  data.likes.discard(uid)
  await update_message(event.edit, data)


@button_dispatcher.register(3)
@parse_data(get_callback_message)
async def on_delete(event, data, *, pending_confirms=set()):
  if data.owner != event.query.user_id:
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
@parse_data(get_callback_message)
async def on_post(event, data):
  m = await client_user.get_messages(GROUP_ID, ids=event.message_id)

  await client_user.send_message(
    CHANNEL,
    file=m.media,
    schedule=timedelta(hours=12)
  )
  #TODO: format better
  await event.edit(text=(
    f'👍: {list(data.likes)}\n'
    f'👎: {list(data.dislikes)}\n'
    '#posted'
  ))


@client.on(events.NewMessage(chats=GROUP_ID))
async def on_image(event):
  m = event.message
  if not isinstance(m.media, tl.types.MessageMediaPhoto):
    return
  data = MessageData()
  data.owner = event.message.sender_id
  data.likes.add(event.message.sender_id)
  await event.respond(
    message=data.encode(),
    parse_mode=None,
    file=m.media,
    buttons=[[
      on_upvote.get_button('👍 1'),
      on_downvote.get_button('👎'),
      on_delete.get_button('🗑')
    ]]
  )


async def main():
  await client.start(bot_token=os.environ['TOKEN'])
  await client_user.start()
  client.add_event_handler(button_dispatcher.dispatch)
  await client.run_until_disconnected()


client.loop.run_until_complete(main())