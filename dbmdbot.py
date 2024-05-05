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


def send_xetra(bot):
    text = db_market_data()
    send_to_telegram(text, bot, set_title=True)
    return "xetra market data published"


def send_lse(bot):
    text = extract_md('BARC.L')
    send_to_telegram(text, bot, set_title=False)
    return "lse market data published"


async def send_nyse(bot):
    text = extract_md('C')
    await send_to_telegram(text, bot, set_title=False)
    text = extract_md('PHK')
    await send_to_telegram(text, bot, set_title=False)
    return "nyse market data published"


def send_euronext(bot):
    text = extract_md('BNP.PA')
    send_to_telegram(text, bot, set_title=False)
    return "euronext market data published"


async def market_data(exchange, bot):
    print(f"processing {exchange}")
    if (exchange == 'XETRA'):
        return send_xetra(bot)
    elif (exchange == 'NYSE'):
        return await send_nyse(bot)
    elif (exchange == 'EURONEXT'):
        return send_euronext(bot)
    elif (exchange == 'LSE'):
        return send_lse(bot)
    else:
        return f"unknown exchange: {exchange}"


update_times = {
    'XETRA': {
        'time': '45 17 * * 1-5',
        'zone': 'Europe/Berlin'
    },
    'NYSE': {
        'time': '15 16 * * 1-5',
        'zone': 'America/New_York'
    },
    'LSE': {
        'time': '15 17 * * 1-5',
        'zone': 'Europe/London'
    },
    'EURONEXT': {
        'time': '15 17 * * 1-5',
        'zone': 'Europe/Amsterdam'
    }
}


def round_to_nearest_15_minutes(unix_time):
    dt = datetime.utcfromtimestamp(unix_time)
    dt = dt.replace(second=0, microsecond=0)
    minute = (dt.minute // 15) * 15
    return dt.replace(minute=minute)

async def check_exchanges(unix_time, bot):
    rounded_time = round_to_nearest_15_minutes(unix_time)
    time = datetime.utcfromtimestamp(unix_time)
    await bot.initialize()
    for ticker, data in update_times.items():
        tz = pytz.timezone(data['zone'])
        local_time = tz.normalize(time.replace(tzinfo=pytz.utc).astimezone(tz))
        local_rounded_time = tz.normalize(rounded_time.replace(tzinfo=pytz.utc).astimezone(tz))
        local_rounded_time_minus_one_minute = local_rounded_time - timedelta(minutes=1)
        cron = croniter(data['time'], local_rounded_time_minus_one_minute, ret_type=datetime, day_or=False)
        next_cron_time = cron.get_next(ret_type=datetime)
        if (next_cron_time < local_time and next_cron_time >= local_rounded_time):
            print(f"Cron expression triggered for {ticker} at {local_rounded_time} in {data['zone']} timezone")
            result = await market_data(ticker, bot)
            print(result)
    await bot.shutdown()



if __name__ == "__main__":
    token = os.getenv('TELEGRAM_TOKEN')
    chat_id = os.getenv('TELEGRAM_CHAT_ID')
    bot = telegram.Bot(token=token, request = bot_request.MDHTTPXRequest())
    current_unix_time = int(time.time())
    asyncio.run(check_exchanges(current_unix_time, bot))





