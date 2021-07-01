from flask import Flask, request as flaskRequest, jsonify, render_template
import requests
import json
import time
from  datetime import datetime, timedelta
import sqlite3
import sys
import ccxt
import os
from threading import Thread
from pathlib import Path
import logging

#setup the logging module for file output
log = logging.getLogger('spotbit')
log.setLevel(logging.DEBUG)
logFileHandler = logging.FileHandler('/home/spotbit/.spotbit/spotbit.log')
logFileHandler.setLevel(logging.DEBUG)
log.addHandler(logFileHandler)
#Config Settings
allowedFields = ["keepWeeks", "exchanges", "currencies", "interval", "exchange_limit", "averaging_time", "historicalExchanges", "historyEnd"]
configPath = Path("/home/spotbit/.spotbit/spotbit.config")
#Default values; these will be overwritten when the config file is read
exchanges = []
historicalExchanges = [] # exchanges that we want the history of
currencies = []
interval = 10 #time to wait between GET requests to servers, to avoid ratelimits
keepWeeks = 3 # add this to the config file
exchange_limit = 200 #when there are more exchanges than this multithreading is ideal
performance_mode = False
averaging_time = 1 # the number of hours that we should average information over
historyEnd = 0
on_demand = False # whether or not we are caching data
score = 0 #the current percent of empty tables
#the information regarding the current thread
threadResults = None
# curated exchange lists for creating averages
curated_exchanges = {'USD': ['coinbasepro', 'okcoin', 'bitfinex', 'kraken', 'bitstamp'], 'GBP': ['coinbasepro', 'coinsbank', 'bitstamp', 'kraken', 'cexio'], 'EUR': ['kraken', 'coinbasepro', 'bitstamp', 'bitfinex', 'indoex'], 'JPY': ['bitflyer', 'liquid', 'coincheck', 'bitbank', 'zaif'], 'USDT': ['binance', 'okex', 'huobipro', 'bitmax', 'gateio']}
curated_exchanges_list = ['gemini', 'bitstamp', 'okcoin', 'coinsbit', 'coinbasepro', 'coinsbank', 'kraken', 'cexio', 'bitfinex', 'indoex', 'bitflyer', 'liquid', 'coincheck', 'bitbank', 'zaif', 'hitbtc', 'binance', 'okex', 'gateio', 'bitmax']
curated_currencies = ['USD', 'GBP', 'EUR', 'JPY', 'AUD', 'USDT']


p = Path("/home/spotbit/.spotbit/sb.db")
db = sqlite3.connect(p)
print(f"db opened in {p}")
log.debug(f"db opened in {p}")
ONION = ""
try:
    ONION = os.environ["ONION"] #get this value from the path
    print(f"spotbit is running at {ONION}")
except Exception as e:
    print(f"cant find ONION in PATH {e}")
    
# Database configuration
# We need to have the database opened manually once so that systemd can access it
def configure_db():
    p = Path("/home/spotbit/.spotbit/sb.db")
    db = sqlite3.connect(p)
    print(f"db opened in {p}")
    log.debug(f"db opened in {p}")
app = Flask(__name__)

# split up the number of exchanges per chunk based on how many cpu cores are available
# cpuOffset: the number of cores you want to try and utilize.
def optimize_chunks(cpuOffset):
    return int(len(exchanges) / (os.cpu_count()-cpuOffset))

# Create a dict that contains ccxt objects for every supported exchange.
# The API will query a subset of these exchanges based on what the user has specified
# Unsupported exchanges: bitvaro phemex vaultoro
# Future Plans:
# Hard coding supported exchanges is a bad practice. CCXT autogenerates code for each exchange and therefore at least in theory may frequently support new exchanges.
# Need to find a way to automatically create a list of exchange objects.
# btctradeim doesn't want to work on raspberry pi
def init_supported_exchanges():
    objects = {"acx":ccxt.acx(), "aofex":ccxt.aofex(), "bequant":ccxt.bequant(), "bibox":ccxt.bibox(), "bigone":ccxt.bigone(), "binance":ccxt.binance(), "bitbank":ccxt.bitbank(), "bitbay":ccxt.bitbay(), "bitfinex":ccxt.bitfinex(), "bitflyer":ccxt.bitflyer(), "bitforex":ccxt.bitforex(), "bithumb":ccxt.bithumb(), "bitkk":ccxt.bitkk(), "bitmax":ccxt.bitmax(), "bitstamp":ccxt.bitstamp(), "bittrex":ccxt.bittrex(), "bitz":ccxt.bitz(), "bl3p":ccxt.bl3p(), "bleutrade":ccxt.bleutrade(), "braziliex":ccxt.braziliex(), "btcalpha":ccxt.btcalpha(), "btcbox":ccxt.btcbox(), "btcmarkets":ccxt.btcmarkets(), "btctradeua":ccxt.btctradeua(), "bw":ccxt.bw(), "bybit":ccxt.bybit(), "bytetrade":ccxt.bytetrade(), "cex":ccxt.cex(), "chilebit":ccxt.chilebit(), "coinbase":ccxt.coinbase(), "coinbasepro":ccxt.coinbasepro(), "coincheck":ccxt.coincheck(), "coinegg":ccxt.coinegg(), "coinex":ccxt.coinex(), "coinfalcon":ccxt.coinfalcon(), "coinfloor":ccxt.coinfloor(), "coinmate":ccxt.coinmate(), "coinone":ccxt.coinone(), "crex24":ccxt.crex24(), "currencycom":ccxt.currencycom(), "digifinex":ccxt.digifinex(), "dsx":ccxt.dsx(), "eterbase":ccxt.eterbase(), "exmo":ccxt.exmo(), "exx":ccxt.exx(), "foxbit":ccxt.foxbit(), "ftx":ccxt.ftx(), "gateio":ccxt.gateio(), "gemini":ccxt.gemini(), "hbtc":ccxt.hbtc(), "hitbtc":ccxt.hitbtc(), "hollaex":ccxt.hollaex(), "huobipro":ccxt.huobipro(), "ice3x":ccxt.ice3x(), "independentreserve":ccxt.independentreserve(), "indodax":ccxt.indodax(), "itbit":ccxt.itbit(), "kraken":ccxt.kraken(), "kucoin":ccxt.kucoin(), "lakebtc":ccxt.lakebtc(), "latoken":ccxt.latoken(), "lbank":ccxt.lbank(), "liquid":ccxt.liquid(), "luno":ccxt.luno(), "lykke":ccxt.lykke(), "mercado":ccxt.mercado(), "oceanex":ccxt.oceanex(), "okcoin":ccxt.okcoin(), "okex":ccxt.okex(), "paymium":ccxt.paymium(), "poloniex":ccxt.poloniex(), "probit":ccxt.probit(), "southxchange":ccxt.southxchange(), "stex":ccxt.stex(), "surbitcoin":ccxt.surbitcoin(), "therock":ccxt.therock(), "tidebit":ccxt.tidebit(), "tidex":ccxt.tidex(), "upbit":ccxt.upbit(), "vbtc":ccxt.vbtc(), "wavesexchange":ccxt.wavesexchange(), "whitebit":ccxt.whitebit(), "yobit":ccxt.yobit(), "zaif":ccxt.zaif(), "zb":ccxt.zb()}
    return objects

# Check if a given exchange is in the list of supported exchanges.
# Currently, the list of supported exchanges is all those supported by ccxt aside from a small handful that did not seem to work properly. May be bug in ccxt or just a typo in their code / docs
def is_supported(exchange):
    try:
        obj = ex_objs[exchange]
        if obj != None:
            return True
        else:
            return False
    except Exception as e:
        print(f"caught an error: {e}")
        log.error(f"caught an error {e}")
        return False

# Check if a timestamp has ms precision by modding by 1000
def is_ms(timestamp):
    if timestamp % 1000 == 0:
        return True
    return False

# We create a list of all exchanges to do error checking on user input
ex_objs = init_supported_exchanges()
num_exchanges = len(ex_objs)
print(f"created list of {num_exchanges}")
log.info(f"created list of {num_exchanges}")

@app.route('/')
def index():
    date_start = (datetime.now() - timedelta(days=5)).timestamp()*1e3
    date_end = (datetime.now()).timestamp()*1e3
    f0 = f"{ONION}/now/USD/coinbasepro"
    f1 = f"{ONION}/now/USD"
    f2 = f"{ONION}/hist/USD/coinbasepro/{date_start}/{date_end}"
    f3 = f"{ONION}/configure"
    return render_template('index.html', fetch_0=f0,fetch_1=f1,fetch_2=f2,fetch_3=f3,date_start=date_start,date_end=date_end)

# TODO: create an html page to render here
@app.route('/status')
def status():
    global score
    global threadResults
    if performance_mode:
        l = len(threadResults)
        content = f"Threads: {l}"
        for chunk, thread in threadResults:
            html += f"{chunk} at memory address: {thread}"
        return f"<html><p>{content}</p></html>"
    else:
        return "server is running"

# configure the settings of Spotbit while the server is still running
# send a GET request to this route to view current settings
# send a POST request to this route with settings fields stored in JSON to update settings
# TODO: make the updates persistant by also writing them to file.
@app.route('/configure', methods=['GET', 'POST'])
def configure():
    # seems like this needs to be done in order to reference global vars inside of the flask server thread
    global keepWeeks
    global currencies
    global exchanges
    global interval
    global on_demand
    if flaskRequest.method == 'POST':
        #return the config settings TODO: error check so that the user doesn't have to submit everything at once. Also implement a form here.
        keepWeeks = flaskRequest.json("keepWeeks")
        exchanges = flaskRequest.json("exchanges")
        currencies = flaskRequest.json("currencies")
        interval = flaskRequest.json("interval")
        return {'updated settings?':'yes', 'keepWeeks':keepWeeks, 'currencies':currencies, 'exchanges':exchanges, 'interval':interval}
    else:
        return {'updated settings?':'no', 'keepWeeks':keepWeeks, 'currencies':currencies, 'on demand exchanges':list(ex_objs.keys()), 'cached exchanges': exchanges, 'interval':interval}

# return averages in a list of tuples
# find the oldest timestamp in the list of tuples
def average_price_value(tuple_list, tuple_length, ticker):
    running_sums = [0] * tuple_length
    oldest_timestamp = 1e13
    for tup in tuple_list:
        if tup != None and tup[1] < oldest_timestamp:
            oldest_timestamp = tup[1]
        for i in range(0,tuple_length):
            if i > 3:
                running_sums[i] += tup[i]
    list_len = len(tuple_list)
    return {'id': 'average_value', 'timestamp': (datetime.now()).timestamp()*1e3, 'datetime': datetime.now(), 'oldest_timestamp': oldest_timestamp, 'currency_pair': ticker, 'open': running_sums[4]/list_len, 'high': running_sums[5]/list_len, 'low': running_sums[6]/list_len, 'close': running_sums[7]/list_len, 'volume': running_sums[8]/list_len}

# route for when a call is made without specifying an exchange.
# return an average of the 5 curated exchanges for that currency
@app.route('/now/<currency>')
def now_noex(currency):
    global averaging_time
    db_n = sqlite3.connect(p, timeout=30)
    currency = currency.upper()
    ticker = f"BTC-{currency}"
    # only calculate averages if a list has been curated already
    if currency in curated_currencies:
        components = curated_exchanges[currency]
        failed_exchanges = []
        components_list = []
        for exchange in components:
            ms_check = f"SELECT timestamp FROM {exchange} LIMIT 1;"
            cursor = db_n.execute(ms_check)
            res = cursor.fetchone()
            # only take values from within 15 min of present
            ts_delta = (datetime.now() - timedelta(hours=averaging_time)).timestamp()
            if res!= None and is_ms(int(res[0])):
                ts_delta *= 1e3
            statement = f"SELECT * FROM {exchange} WHERE pair = '{ticker}' AND timestamp > {ts_delta} ORDER BY timestamp DESC LIMIT 1;"
            cursor = db_n.execute(statement)
            res = cursor.fetchone()
            if res != None:
                components_list.append(res)
            else:
                # if there is no data in the table yet, then try a direct request.
                res = fallback_to_direct(exchange, currency, db_n)
                if len(res) < 2:
                    log.error(f"could not get data from {exchange}")
                    failed_exchanges.append(exchange)
                else:
                    components_list.append(res)
        result = average_price_value(components_list, 9, ticker)
        result['exchanges'] = components
        result['failed_exchanges'] = failed_exchanges
        return result

# Get the latest price entry in the database.
# Currency: the three letter base currency desired. Must be a currency you are already collecting data for
# Exchange: the exchange to query data for from the local database.
@app.route('/now/<currency>/<exchange>')
def now(currency, exchange):
    db_n = sqlite3.connect(p, timeout=30)
    ticker = "BTC-{}".format(currency.upper())
    if exchange in exchanges:
        #if the exchange is already in the config file
        #statement = "SELECT * FROM {} WHERE pair = '{}' AND timestamp = (SELECT MAX(timestamp) FROM {});".format(exchange, ticker, exchange)
        statement = f"SELECT * FROM {exchange} WHERE pair = '{ticker}' ORDER BY timestamp DESC LIMIT 1;"
        try:
            cursor = db_n.execute(statement)
            res = cursor.fetchone()
        except sqlite3.OperationalError:
            print("database is locked. Cannot access it")
            log.error("database is locked. Cannot access it")
            return {'err': 'database locked'}
        if res != None:
            db_n.close()
            return {'id':res[0], 'timestamp':res[1], 'datetime':res[2], 'currency_pair':res[3], 'open':res[4], 'high':res[5], 'low':res[6], 'close':res[7], 'vol':res[8]}
        else:
            db_n.close()
            return fallback_to_direct(exchange, currency, db_n)
    elif exchange == "all": #if all is selected then we select from all exchanges and average the latest close
        result_set = []
        for e in exchanges:
            ts_cutoff = (datetime.now() - timedelta(hours=averaging_time)).timestamp()
            check_ms = f"SELECT timestamp FROM {e} LIMIT 1;"
            cursor = db_n.execute(check_ms)
            db_n.commit()
            ts = cursor.fetchone()
            if ts != None and is_ms(int(ts[0])):
                print(f"using millisecond precision for {e}")
                logging.info(f"using millisecond precision for {e}")
                ts_cutoff *= 1e3
            statement = f"SELECT timestamp, close FROM {e} WHERE timestamp > {ts_cutoff} AND pair = '{ticker}' ORDER BY timestamp LIMIT 1;"
            cursor = db_n.execute(statement)
            db_n.commit()
            result = cursor.fetchone()
            if result != None:
                result_set.append(result[1])
        return {'ticker': list_mean(result_set)}
    else:
        return fallback_to_direct(exchange, currency, db_n)

# This method will directly request an exchange that is supported but who's table is also empty
def fallback_to_direct(exchange, currency, db_n):
    #make a direct request
    ticker = "BTC-{}".format(currency.upper())
    res = request_single(exchange, currency)
    #db_n.close()
    if res != None:
        return res
    else:
        return {'id': res}

# Find the mean of a list of two-value tuples
def list_mean(input_list):
    avg = 0.0
    for l in input_list:
        avg += l
    return avg/len(input_list)

# Get data from local storage inside of a certain range.
# Parameters:
#   Currency: the fiat base currency to fetch data for. Should be a three letter currency code in lowercase.
#   Exchange: the exchange to get data from.
#   date_start and date_end: date_start is the oldest time value in the range desired. It can be provided as a millisecond timestamp or as a datetime formatted as "YYYY-MM-DDTHH:mm:SS".
@app.route('/hist/<currency>/<exchange>/<date_start>/<date_end>', methods=['GET'])
def hist(currency, exchange, date_start, date_end):
    db_n = sqlite3.connect(p, timeout=10)
    ticker = "BTC-{}".format(currency.upper())
    #check what format of dates we have
    if (str(date_start)).isdigit():
        date_s = int(date_start)
        date_e = int(date_end)
    else:
        #error checking for malformed dates
        try:
            date_s = (datetime.fromisoformat(date_start.replace("T", " "))).timestamp()*1000
            date_e = (datetime.fromisoformat(date_end.replace("T", " "))).timestamp()*1000
        except Exception:
            return "malformed dates. Provide both dates in the same format: use YYYY-MM-DDTHH:mm:SS or millisecond timestamps"
    # check the table we want to select from to see the precision of it
    check = f"SELECT timestamp FROM {exchange} ORDER BY timestamp DESC LIMIT 1;"
    cursor = db_n.execute(check)
    statement = ""
    ts = cursor.fetchone()
    if ts != None and is_ms(int(ts[0])):
        statement = f"SELECT * FROM {exchange} WHERE timestamp > {date_s} AND timestamp < {date_e} AND pair = '{ticker}';"
    else:
        # for some exchanges we cannot use ms precision timestamps (such as coinbase)
        date_s /= 1e3
        date_e /= 1e3
        statement = f"SELECT * FROM {exchange} WHERE timestamp > {date_s} AND timestamp < {date_e} AND pair = '{ticker}';"
    # keep trying in case of database locked error
    while True:
        try:
            cursor = db_n.execute(statement)
            break
        except sqlite3.OperationalError as oe:
            time.sleep(5)
        
    res = cursor.fetchall()
    db_n.close()
    return {'columns': ['id', 'timestamp', 'datetime', 'currency_pair', 'open', 'high', 'low', 'close', 'vol'], 'data':res}

# Return all database rows within `tolerance` for each of the supplied dates
# Dates should be provided as millisecond timestamps separated by hyphens
@app.route('/hist/<currency>/<exchange>/<dates>')
def hist_single_dates(currency, exchange, dates):
    db_n = sqlite3.connect(p, timeout=10)
    ticker = "BTC-{}".format(currency.upper())
    dates_list = dates.split("-")
    # the number of minutes away from a given date that is considered acceptable
    tolerance = 30
    results = {}
    check_ms = f"SELECT timestamp FROM {exchange} LIMIT 1;"
    cursor = db_n.execute(check_ms)
    ts = cursor.fetchone()
    ms_precision = True
    if ts != None and is_ms(int(ts[0])) != True:
        ms_precision = False
    for d in dates_list:
        try:
            ts = int(d)
        except Exception:
            return f"malformed date {d}"
        dt = datetime.fromtimestamp(ts/1e3)
        lower_bound = (dt - timedelta(minutes=tolerance)).timestamp()*1e3
        upper_bound = (dt + timedelta(minutes=tolerance)).timestamp()*1e3
        if ms_precision == False:
            ts /= 1e3
        statement = f"SELECT * FROM {exchange} WHERE pair = '{ticker}' AND timestamp > {lower_bound} AND timestamp > {upper_bound} ORDER BY timestamp ASC;"
        # right now we return everything
        while True:
            try:
                cursor = db_n.execute(statement)
                res = cursor.fetchall()[0]
                break
            except sqlite3.OperationalError:
                time.sleep(2)
        if res != None:
            results[f"{d}"] = {'id':res[0], 'timestamp':res[1], 'datetime':res[2], 'pair':res[3], 'open':res[4], 'high':res[5], 'low':res[6], 'close':res[7], 'vol':res[8]}
        else:
            results[f"{d}"] = None
    return results
# Make a single request, without having to loop through all exchanges and currency pairs.
# This is intended for when the user requests an exchange in /now that is not present in the database.
# It will probably not be used for /hist because of the length of time getting arbitrary amounts of historical data can be
def request_single(exchange, currency):
    if not is_supported(exchange):
        return f"{exchange} is not supported by CCXT"
    obj = ex_objs[exchange]
    ticker = "BTC/{}".format(currency.upper())
    dt = None
    if obj.has['fetchOHLCV']:
        tframe = '1m'
        # drop all this in a separate method
        lim = 1000
        if exchange == "bleutrade" or exchange == "btcalpha" or exchange == "rightbtc" or exchange == "hollaex":
            tframe = '1h'
        if exchange == "poloniex":
            tframe = '5m'
        # some exchanges have explicit limits on how many candles you can get at once
        if exchange == "bitstamp":
            lim = 1000
        if exchange == "bybit":
            lim = 200
        if exchange == "eterbase":
            lim = 1000000
        if exchange == "exmo":
            lim = 3000
        if exchange == "btcalpha":
            lim = 720
        result = None
        if exchange == "bitfinex": #other exchanges requiring special conditions: bitstamp, bitmart
            params = {'limit':100, 'start':(round((datetime.now()-timedelta(hours=1)).timestamp()*1000)), 'end':round(datetime.now().timestamp()*1000)}
            try:
                result = ex_objs[exchange].fetch_ohlcv(symbol=ticker, timeframe=tframe, since=None, params=params)
            except Exception as e:
                print(f"got an error requesting info from {exchange}: {e}")
                logging.error(f"got an error requesting info frm {exchange}: {e}")
        else:
            try:
                result = obj.fetch_ohlcv(symbol=ticker, timeframe=tframe, since=None, limit=lim)
            except Exception as e:
                print(f"got an error requesting info from {exchange}: {e}")
                logging.error(f"got an error requesting info from {exchange}: {e}")
    else:
        try:
            result = obj.fetch_ticker(ticker)
            if result != None and is_ms(result['timestamp']) == False:
                dt = datetime.fromtimestamp(result['timestamp'])
            else:
                dt = datetime.fromtimestamp(result['timestamp'] / 1e3)
            if result != None:
                return {'close': result['close'], 'symbol': ticker, 'timestamp': result['timestamp'], 'datetime': dt, 'volume': result['bidVolume'], 'id': 'on_demand'}
        except Exception as e:
            print(f"got ratelimited on {e}")
            logging.error(f"got ratelimited on {e}")
    if result != None:
        res = result[-1]
        if is_ms(res[0]):
            dt = datetime.fromtimestamp(res[0]/1e3)
        else:
            dt = datetime.fromtimestamp(res[0])
        return {'id': 'on_demand', 'timestamp': res[0], 'datetime': dt, 'currency_pair': ticker, 'open': res[1], 'high': res[2], 'low': res[3], 'close': res[4], 'vol': res[5]}
    else:
        return "no data"


# Make an HTTP GET request to exchanges via the ccxt API
# TODO: add error checking for if an exchange supports ohlc data. If not, default to regular price data. (done)
# Loop through all chosen exchanges, check if they are supported, loop through all chosen currencies, for each make request to ohlc endpoint if supported, else price ticker. Write data to local storage.
# Bitfinex special rule: bitfinex returns candles from the beginning of time, not the most recent. This is a behavior of the API itself and has nothing to do with this code or ccxt. Therefore we must specify the timeframe desired in the optional params field of the function call with a dictionary of available options.
def request(exchanges,interval,db_n):
    global currencies
    for e in exchanges:
        for curr in currencies:
                ticker = "BTC/{}".format(curr)
                success = True
                if ex_objs[e].has['fetchOHLCV']:
                    candle = None
                    tframe = '1m'
                    lim = 1000
                    if e == "bleutrade" or e == "btcalpha" or e == "rightbtc" or e == "hollaex":
                        tframe = '1h'
                    if e == "poloniex":
                        tframe = '5m'
                    # some exchanges have explicit limits on how many candles you can get at once
                    if e == "bitstamp":
                        lim = 1000
                    if e == "bybit":
                        lim = 200
                    if e == "eterbase":
                        lim = 1000000
                    if e == "exmo":
                        lim = 3000
                    if e == "btcalpha":
                        lim = 720
                    if e == "bitfinex":
                        params = {'limit':100, 'start':(round((datetime.now()-timedelta(hours=1)).timestamp()*1000)), 'end':round(datetime.now().timestamp()*1000)}
                        try:
                            candle = ex_objs[e].fetch_ohlcv(symbol=ticker, timeframe=tframe, since=None, params=params)
                            if candle == None:
                                raise Exception(f"candle from {e} is null")
                        except Exception as err: #figure out this error type
                            #the point so far is to gracefully handle the error, but waiting for the next cycle should be good enough
                            if "does not have" not in str(err):
                                print(f"error fetching candle: {e} {curr} {err}")
                                log.error(f"error fetching candle: {e} {curr} {err}")
                            success = False
                    else:
                        try:
                            candle = ex_objs[e].fetch_ohlcv(symbol=ticker, timeframe=tframe, since=None, limit=lim) #'ticker' was listed as 'symbol' before | interval should be determined in the config file
                            if candle == None:
                                raise Exception(f"candle from {e} is nulll")
                        except Exception as err:
                            if "does not have" not in str(err):
                                print(f"error fetching candle: {e} {curr} {err}")
                                log.error(f"error fetching candle: {e} {curr} {err}")
                            success = False
                    if success:
                        times_inserted = 0
                        for line in candle:
                            ts = datetime.fromtimestamp(line[0]/1e3) #check here if we have a ms timestamp or not
                            for l in line:
                                if l == None:
                                    l = 0
                            #this is another error check condition for when null values slip into the data.
                            statement = "INSERT INTO {} (timestamp, datetime, pair, open, high, low, close, volume) VALUES ({}, '{}', '{}', {}, {}, {}, {}, {});".format(e, line[0], ts, ticker.replace("/", "-"), line[1], line[2], line[3], line[4], line[5])
                            try:
                                db_n.execute(statement)
                                db_n.commit()
                                times_inserted += len(candle)
                            except sqlite3.OperationalError as op:
                                nulls = []
                                c = 0
                                # identify where the null value is
                                for l in line:
                                    if l == None:
                                        nulls.append(c)
                                        c += 1
                                print(f"exchange: {e} currency: {curr}\nsql statement: {statement}\nerror: {op}(moving on)")
                                log.error(f"exchange: {e} currency: {curr} sql statement: {statement} error: {op}")
                        now = datetime.now()
                        print(f"[{now}] | inserted into {e} {curr} {times_inserted} times")
                        log.info(f"[{now}] | inserted into {e} {curr} {times_inserted} times")
                else:
                    try:
                        price = ex_objs[e].fetch_ticker(ticker)
                    except Exception as err:
                        print(f"error fetching ticker: {err}")
                        log.error(f"error fetching ticker: {err}")
                        success = False
                    if success:
                        ts = None
                        try:
                            if is_ms(int(price['timestamp'])):
                                ts = datetime.fromtimestamp(int(price['timestamp'])/1e3)
                            else:
                                ts = datetime.fromtimestamp(int(price['timestamp']))
                        except OverflowError as oe:
                            print(f"{oe} caused by {ts}")
                        ticker = ticker.replace("/", "-")
                        statement = f"INSERT INTO {e} (timestamp, datetime, pair, open, high, low, close, volume) VALUES ({price['timestamp']}, '{ts}', '{ticker}', 0.0, 0.0, 0.0, {price['last']}, 0.0);"
                        db_n.execute(statement)
                        db_n.commit()
                        now = datetime.now()
                        print(f"[{now}] | inserted into {e} {curr} VALUE: {price['last']}")
                        log.info(f"[{now}] | inserted into {e} {curr} VALUE: {price['last']}")
                time.sleep(interval)

# Thread method. Makes requests every interval seconds.
# Adding this method here to make request more versatile while maintaining the same behavior
def request_periodically(exchanges, interval):
    db_n = sqlite3.connect(p, timeout=30)
    while True:
        request(exchanges,interval,db_n)

# Split the list of exchanges into chunks up to size chunk_size.
# Create a thread for each chunk and start it, then add the thread to a list.
# Return a list of tuples that contain the list of whats in each chunk and a list of the actual thread objects.
def request_fast(exchanges,interval, chunk_size):
    count = 0
    chunks = []
    threads = []
    current_chunk = []
    # split up the list of exchanges
    for e in exchanges:
        if count < chunk_size:
            current_chunk.append(e)
            count += 1
        else:
            count = 0
            chunks.append(current_chunk)
            current_chunk = []
    # Start a thread for each chunk
    for chunk in chunks:
        print(f"creating thread for chunk {chunk}")
        log.info(f"creating thread for chunk {chunk}")
        cThread = Thread(target=request_periodically, args=(chunk,interval))
        cThread.start()
        threads.append(cThread)
    return (chunks, threads)

# Fetch the complete historical data for an exchange for a given time interval in milliseconds
# start_date is the oldest date
# end_date is the newest date
def request_history(exchange, currency, start_date, end_date):
    global interval
    db_n = sqlite3.connect(p, timeout=10)
    ticker = f"BTC/{currency}"
    while start_date < end_date:
        #params = {'limit': 10000, 'start': start_date, 'end': int((datetime.fromtimestamp(start_date/1e3) + timedelta(hours=2)).timestamp()*1e3)}
        params = {'start': start_date, 'end': end_date}
        tick = ex_objs[exchange].fetch_ohlcv(symbol=ticker, timeframe='1m', params=params)
        for line in tick:
            dt = None
            symbol = ticker.replace("/", "-")
            try:
                if is_ms(int(line['timestamp'])):
                    dt = datetime.fromtimestamp(line['timestamp'] / 1e3)
                else:
                    dt = datetime.fromtimestamp(line['timestamp'])
                statement = f"INSERT INTO {exchange} (timestamp, datetime, pair, open, high, low, close, volume) VALUES ({line['timestamp']}, '{dt}', '{symbol}', 0.0, 0.0, 0.0, {line['last']}, 0.0);"
            except TypeError:
                if line[0] % 1000 == 0:
                    dt = datetime.fromtimestamp(line[0] / 1e3)
                else:
                    dt = datetime.fromtimestamp(line[0])
                statement = f"INSERT INTO {exchange} (timestamp, datetime, pair, open, high, low, close, volume) VALUES ({line[0]}, '{dt}', '{symbol}', {line[1]}, {line[2]}, {line[3]}, {line[4]}, {line[5]});"
            db_n.execute(statement)
            db_n.commit()
        l = len(tick)
        print(f"table: {exchange} period: {start_date} to {end_date} rows inserted: {l}")
        log.info(f"table: {exchange} period: {start_date} to {end_date} rows inserted: {l}")
        start_date += 1e4 #leaving this hardcoded for now
        start_date = int(start_date)
        time.sleep(interval)

# Create a thread for each exchange that needs history.
def request_history_periodically(histExchanges, currencies, start_date):
    history_threads = []
    for h in histExchanges:
        hThread = Thread(target=request_history, args=(h, "USD", historyEnd, datetime.now().timestamp()*1e3))
        hThread.start()
        history_threads.append(hThread)
        print(f"started thread for {h}")
        log.info(f"started thread for {h}")
    return history_threads

# Read the values stored in the config file and store them in memory.
# Run during install and at every run of the server.
# Returns void
def read_config():
    global exchanges
    global interval
    global performance_mode
    global averaging_time
    global exchange_limit
    global historicalExchanges
    global historyEnd
    global keepWeeks
    global on_demand
    with open(configPath, "r") as f:
        lines = f.readlines()
        #read each line in the file
        for line in lines:
            #split the current line
            setting_line = line.split("=")
            #if there are invalid lines in the file ignore them
            if "#" in setting_line[0]:
                pass #ignore comments
            elif setting_line[0] not in allowedFields and "#" not in setting_line[0]:
                print(f"invalid config setting {setting_line[0]}")
                log.error(f"invalid config setting {setting_line[0]}")
            elif setting_line[0] == "keepWeeks":
                try:
                    keepWeeks = int(setting_line[1])
                except Exception as e:
                    print(f"could not read keepWeeks field. Using default setting of {keepWeeks} weeks. Error: {e}")
                    log.error(f"could not read keepWeeks field. Using default setting of {keepWeeks} weeks. Error: {e}")
            elif setting_line[0] == "exchanges":
                exs = setting_line[1].split(" ")
                for e in exs:
                    e = e.replace("\n", "")
                    if e == "all":
                        exchanges = list(ex_objs.keys())
                        on_demand = True
                        break
                    if e not in exchanges and is_supported(e) == True:
                        exchanges.append(e)
                    else:
                        print(f"{e} is not supported by CCXT!")
                        log.error(f"{e} is not supported by CCXT!")
            elif setting_line[0] == "currencies":
                currs = setting_line[1].split(" ")
                for c in currs:
                    #need to make sure currency codes are all caps and have newlines dropped off
                    c_formatted = (c.replace("\n", "")).upper()
                    if c_formatted not in currencies:
                        if "\n" in c:
                            currencies.append(c_formatted)
                        else:
                            currencies.append(c_formatted)
            elif setting_line[0] == "interval":
                interval = int(setting_line[1])
            elif setting_line[0] == "exchange_limit":
                try:
                    exchange_limit = int((setting_line[1].replace("\n", "")))
                except TypeError:
                    print("invalid value in exchange_limit field. Must be an integer")
                    log.error("invalid value in exchange_limit field. Must be an integer")
            elif setting_line[0] == "averaging_time":
                try:
                    averaging_time = int((setting_line[1]).replace("\n", ""))
                except TypeError:
                    print("invalid value in averaging_time field. Must be an integer (number of hours)")
                    log.error("invalid value in averaging_time field. Must be an integer (number of hours)")
            elif setting_line[0] == "historicalExchanges":
                hists = setting_line[1].split(" ")
                for h in hists:
                    h = (h.replace("\n", ""))
                    historicalExchanges.append(h)
                print(f"collecting history for {historicalExchanges}")
                log.error(f"collecting history for {historicalExchanges}")
            elif setting_line[0] == "historyEnd":
                try:
                    historyEnd = int((setting_line[1]).replace("\n", ""))
                except TypeError:
                    print("invalid value in historyEnd. Must be millisecond timestamp (integer)")
                    log.error("invalid value in historyEnd. Must be millisecond timestamp (integer)")
            else:
                return
    #print statement for debugging
    len_exchanges = len(exchanges)
    if len_exchanges > exchange_limit:
        print(f"{len_exchanges} exchanges detected. Using performance mode (multithreading)")
        log.info(f"{len_exchanges} exchanges detected. Using performance mode (multithreading)")
        performance_mode = True

    print(f" Settings read:\n keepWeeks: {keepWeeks}\n exchanges: {exchanges}\n currencies: {currencies}\n interval: {interval}\n exchange_limit: {exchange_limit}\n averaging_time: {averaging_time}\n historicalExchanges: {historicalExchanges}\n historyEnd: {historyEnd}")
    log.info(f" Settings read:\n keepWeeks: {keepWeeks}\n exchanges: {exchanges}\n currencies: {currencies}\n interval: {interval}\n exchange_limit: {exchange_limit}\n averaging_time: {averaging_time}\n historicalExchanges: {historicalExchanges}\n historyEnd: {historyEnd}")

# Check for empty tables in the database
def poke_db(exchanges):
    global score
    db_n = sqlite3.connect(p)
    empties = 0
    for e in exchanges:
        statement = f"SELECT * FROM {e} ORDER BY timestamp DESC LIMIT 1;"
        c = db_n.execute(statement)
        db_n.commit()
        res = c.fetchone()
        if res == None:
            print(f"{e} table is empty!")
            log.info(f"{e} table is empty!")
    score = (empties / len(exchanges))*100
    print(f"{score}% of tables are empty")
    return score

# Find gaps in an exchanges database back to historyEnd and create a list of those gaps as tuples
def find_gaps(exchange, currency):
    global historyEnd
    db_n = sqlite3.connect(p)
    currency = currency.upper()
    ticker = f"BTC-{currency}"
    statement = f"SELECT timestamp FROM {exchange} LIMIT 1;"
    c = db_n.execute(statement)
    res = c.fetchone()
    if res != None and is_ms(int(res[0])):
        statement = f"SELECT timestamp,datetime FROM {exchange} WHERE pair = '{ticker}' AND timestamp > {historyEnd} ORDER BY timestamp;"
    else:
        statement = f"SELECT timestamp, datetime FROM {exchange} WHERE pair = '{ticker}' AND timestamp > {historyEnd / 1e3} ORDER BY timestamp;"
    c = db_n.execute(statement)
    res = c.fetchall()
    report = {}
    # later in time is higer ids
    i = 0
    key = 0
    stop = len(res)
    #make the time gap a configurable param
    while i < stop-1:
        if res[i+1][0] > res[i][0]+1000000:
            #report.append((res[i], res[i+1]))
            report[key] = f"{res[i][0]}-{res[i+1][0]}"
            key +=1
        i += 1
    return report

# Fill gaps in a table via request_history
def backfill(report, exchange, currency):
    for key in report:
        print(f"filling gap {key}")
        rang = report[key].split("-")
        start = int(rang[0])
        end = int(rang[1])
        request_history(exchange, currency, start, end)

# This method is called at the first run.
# It sets up the required tables inside of a local sqlite3 database. There is one table for each exchange.
# Tables are only created if they do not already exist. Install will attempt to create tables for every listed exchange at once when called.
def install():
    read_config()
    #create the sqlite db
    len_exchanges = len(exchanges)
    print(f"creating tables for {len_exchanges} exchanges if they do not exist already.")
    log.info(f"creating tables for {len_exchanges} exchanges if they do not exist already.")
    for exchange in exchanges:
        sql = f"CREATE TABLE IF NOT EXISTS {exchange} (id INTEGER PRIMARY KEY AUTOINCREMENT, timestamp INTEGER, datetime TEXT, pair TEXT, open REAL, high REAL, low REAL, close REAL, volume REAL)"
        print(f"created table for {exchange}")
        log.info(f"created table for {exchange}")
        db.execute(sql)
        db.commit()
    db.close()

# Remove every entry older than now-keepWeeks from all tables in the database
# if there is nothing to prune then nothing will be pruned.
def prune(keepWeeks):
    # prune checks will run continuously and check every 60k seconds right now.
    db_n = sqlite3.connect(p, timeout=10)
    while True:
        for exchange in exchanges:
            #count = ((db.execute("SELECT Count(*) FROM {}".format(exchange))).fetchone())[0]
            if exchange not in historicalExchanges:
                check = f"SELECT MAX(timestamp) FROM {exchange};"
                cursor = db_n.execute(check)
                check_ts = cursor.fetchone()
                statement = ""
                if check_ts[0] is not None:
                    try:
                        if is_ms(int(check_ts[0])):
                            cutoff = (datetime.now()-timedelta(weeks=keepWeeks)).timestamp()*1000
                            statement = f"DELETE FROM {exchange} WHERE timestamp < {cutoff};"
                        else:
                            cutoff = (datetime.now()-timedelta(weeks=keepWeeks)).timestamp()
                            statement = f"DELETE FROM {exchange} WHERE timestamp < {cutoff};"
                        while True:
                            try:
                                db_n.execute(statement)
                                break
                            except sqlite3.OperationalError as op:
                                log.error(f"{op}. Trying again in one hour...")
                                print(f"{op}. Trying again in one hour...")
                                time.sleep(3600)
                        db_n.commit()
                    except TypeError as te:
                        log.error(f"too early to prune {te}")
        time.sleep(60000)


if __name__ == "__main__":
    install() #install will call read_config
    chunk_size = optimize_chunks(cpuOffset=0)
    threadResults = None
    # spin up many threads if there is a lot of exchanges present in the config file
    if performance_mode:
        # request_fast will create and start the threads automatically
        print("performance mode is ON")
        log.info("performance mode is ON")
        threadResults = request_fast(exchanges, interval, chunk_size)
    else:
        print("performance mode is OFF")
        log.info("performance mode is OFF")
        prices_thread = Thread(target=request_periodically, args=(exchanges,interval))
        prices_thread.start()
    request_history_periodically(historicalExchanges, currencies, historyEnd)
    pruning_thread = Thread(target=prune, args=[keepWeeks])
    pruning_thread.start()
    app.run()
    db.close()
