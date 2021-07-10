import time
import functools


GROUP_ID = 1146155787
CHANNEL = '@JapaneseSpirit'


def timed_cache(expiry_seconds):
  def wrapper(func):
    cache = {}
    @functools.wraps(func)
    async def wrapped(*args, **kwargs):
      now = time.time()
      key = functools._make_key(args, kwargs, False)
      if key in cache:
        expires, val = cache[key]
        if expires > now:
          return val
      val = await func(*args, **kwargs)
      cache[key] = (now + expiry_seconds, val)
      return val
    return wrapped
  return wrapper
