import datetime as dt

import telegram
import yfinance as yf
import pytz
from croniter import croniter
from datetime import datetime
from datetime import timedelta
import asyncio
import time
import os
import bot_request
import sys


token = os.getenv('TELEGRAM_TOKEN')
chat_id = os.getenv('TELEGRAM_CHAT_ID')


def _is_xetra_holiday(d: dt.date):
    xetra_holidays = [dt.date(2020, 12, 24),
                      dt.date(2020, 12, 25),
                      dt.date(2020, 12, 31),
                      dt.date(2021, 1, 1),
                      dt.date(2021, 4, 2),
                      dt.date(2021, 4, 5),
                      dt.date(2021, 5, 24),
                      dt.date(2021, 12, 25),
                      dt.date(2021, 12, 31)]
    return d in xetra_holidays or d.isoweekday() > 5


def change(yesterday_close, today_close):
    ret = 100 * (today_close / yesterday_close - 1)
    ret_f = '%.2f' % ret
    today_close_f = '%.2f' % round(today_close, 2)
    sign = '+' if ret > 0 else ''
    return f'{today_close_f} ({sign}{ret_f}%)'


def extract_md(t):
    ticker = yf.Ticker(t)
    close_ts = ticker.history(period='1mo', rounding=False).Close
    yesterday_close, today_close = close_ts.iloc[-2:]
    return f'{t} ' + change(yesterday_close, today_close)


def db_market_data():
    if _is_xetra_holiday(dt.date.today()):
        raise Exception('today is a xetra holiday')
    return extract_md('DBK.DE')


async def send_to_telegram(text, bot, set_title=False):
    if set_title:
        print(f'setting telegram chat title to {text}')
        resp = await bot.set_chat_title(chat_id, text, write_timeout = 60, connect_timeout = 60)
        print(resp)
    else:
        print(f'sending to telegram chat {text}')
        resp = await bot.send_message(chat_id, text, write_timeout = 60, connect_timeout = 60)
        print(resp)


async def send_xetra(bot):
    text = db_market_data()
    await send_to_telegram(text, bot, set_title=True)
    return "xetra market data published"


async def send_lse(bot):
    text = extract_md('BARC.L')
    await send_to_telegram(text, bot, set_title=False)
    return "lse market data published"


async def send_nyse(bot):
    text = extract_md('C')
    await send_to_telegram(text, bot, set_title=False)
    text = extract_md('PHK')
    await send_to_telegram(text, bot, set_title=False)
    return "nyse market data published"


async def send_euronext(bot):
    text = extract_md('BNP.PA')
    await send_to_telegram(text, bot, set_title=False)
    return "euronext market data published"


async def market_data(exchange):
    bot = telegram.Bot(token=token, request = bot_request.MDHTTPXRequest())
    await bot.initialize()
    print(f"processing {exchange}")
    if (exchange == 'XETRA'):
        await send_xetra(bot)
    elif (exchange == 'NYSE'):
        await send_nyse(bot)
    elif (exchange == 'EURONEXT'):
        await send_euronext(bot)
    elif (exchange == 'LSE'):
        await send_lse(bot)
    else:
        print(f"unknown exchange: {exchange}")
    await bot.shutdown()



if __name__ == "__main__":
    current_unix_time = int(time.time())
    exchange = sys.argv[1] if len(sys.argv) > 1 else None
    asyncio.run(market_data(exchange))

    





