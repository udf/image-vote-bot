import asyncio
import os
import logging
import random
from datetime import timedelta

import telethon
from telethon import TelegramClient, events, tl, utils
from telethon.tl.types import KeyboardButtonCallback
from telethon.tl.functions.messages import GetScheduledHistoryRequest

from common import GROUP_ID, CHANNEL, timed_cache
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


@timed_cache(60 * 60)
async def get_username(id):
  e = await client.get_entity(id)
  return e.username


async def format_username_list(user_ids):
  usernames = []

  if not utils.is_list_like(user_ids):
    user_ids = (user_ids,)

  for id in user_ids:
    username = f'#{id}'
    try:
      username = '@' + await get_username(id)
    except ValueError:
      pass
    usernames.append(f'<a href="tg://user?id={id}">{username}</a>')

  return ', '.join(usernames)


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
async def on_delete(event, data):
  owner = event.extra_data
  if owner != event.query.user_id:
    await event.answer(message='Only the owner of the original message can delete!')
    return

  await event.answer(message='Message deleted')
  await event.delete()


@button_dispatcher.register(5)
async def on_vote_start(event):
  owner, message_id, submitter = event.extra_data
  if owner != event.query.user_id:
    await event.answer(message='Only the owner of the original message can start voting!')
    return

  data = MessageData()
  data.likes.add(owner)
  data.owner = owner
  data.submitter = submitter
  await update_message(event.edit, data)
  await client.delete_messages(GROUP_ID, [message_id])


@button_dispatcher.register(4)
@parse_data(get_callback_message)
async def on_post(event, data):
  m = await client_user.get_messages(GROUP_ID, ids=event.message_id)

  scheduled_hist = await client_user(GetScheduledHistoryRequest(
    peer=await client_user.get_input_entity(CHANNEL),
    hash=0
  ))
  schedule_time = timedelta(hours=random.randint(12, 24))
  if scheduled_hist.messages:
    schedule_time = scheduled_hist.messages[0].date + schedule_time

  await client_user.send_message(
    CHANNEL,
    file=m.media,
    schedule=schedule_time
  )
  submitter = data.submitter or data.owner
  submitted_via = ''
  if data.submitter:
    submitted_via = f' via {await format_username_list(data.owner)}'
  await event.edit(
    text=(
      f'Submitted by {await format_username_list(submitter)}{submitted_via}\n'
      f'👍: {await format_username_list(data.likes)}\n'
      f'👎: {await format_username_list(data.dislikes)}\n'
      f'#posted by {await format_username_list(event.query.user_id)}'
    ),
    parse_mode='HTML'
  )


@client.on(events.NewMessage(chats=GROUP_ID))
async def on_image(event):
  m = event.message
  if not isinstance(m.media, tl.types.MessageMediaPhoto):
    return
  submitter = None
  if m.forward:
    submitter = m.forward.sender_id
  if submitter == event.message.sender_id:
    submitter = None
  await event.respond(
    file=m.media,
    buttons=[[
      on_vote_start.get_button('👍', [event.message.sender_id, m.id, submitter]),
      on_delete.get_button('🗑', event.message.sender_id)
    ]]
  )


async def main():
  await client.start(bot_token=os.environ['TOKEN'])
  await client_user.start()
  client.add_event_handler(button_dispatcher.dispatch)
  await client.run_until_disconnected()


client.loop.run_until_complete(main())