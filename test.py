import base64
import dbmdbot
import os


data = base64.b64encode("XETRA".encode('utf-8'))
dbmdbot.market_data({
    'data': data
}, None)

data = base64.b64encode("NYSE".encode('utf-8'))
dbmdbot.market_data({
    'data': data
}, None)

data = base64.b64encode("NASDAQGS".encode('utf-8'))
dbmdbot.market_data({
    'data': data
}, None)
