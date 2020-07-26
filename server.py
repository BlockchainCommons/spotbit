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

#Config Settings
allowedFields = ["keepWeeks", "exchanges", "currencies", "interval"]
configPath = Path("~/.spotbit/spotbit.config").expanduser()
#Default values; these will be overwritten when the config file is read
exchanges = []
currencies = ["USD"]
currency="USD"
interval = 1 #time to wait between GET requests to servers, to avoid ratelimits
keepWeeks = 3 # add this to the config file
#Database
p = Path("~/.spotbit/sb.db").expanduser()
db = sqlite3.connect(p)
print("db opened in {}".format(p))
app = Flask(__name__)

# Create a dict that contains ccxt objects for every supported exchange. 
# The API will query a subset of these exchanges based on what the user has specified
# Unsupported exchanges: bitvaro phemex
# Future Plans:
# Hard coding supported exchanges is a bad practice. CCXT autogenerates code for each exchange and therefore at least in theory may frequently support new exchanges.
# Need to find a way to automatically create a list of exchange objects. 
# btctradeim doesn't want to work on raspberry pi
def init_supported_exchanges():
    objects = {"acx":ccxt.acx(), "anxpro":ccxt.anxpro(), "aofex":ccxt.aofex(), "bcex":ccxt.bcex(), "bequant":ccxt.bequant(), "bibox":ccxt.bibox(), "bigone":ccxt.bigone(), "binance":ccxt.binance(), "bit2c":ccxt.bit2c(), "bitbank":ccxt.bitbank(), "bitbay":ccxt.bitbay(), "bitfinex":ccxt.bitfinex(), "bitflyer":ccxt.bitflyer(), "bitforex":ccxt.bitforex(), "bithumb":ccxt.bithumb(), "bitkk":ccxt.bitkk(), "bitmart":ccxt.bitmart(), "bitmax":ccxt.bitmax(), "bitstamp":ccxt.bitstamp(), "bittrex":ccxt.bittrex(), "bitz":ccxt.bitz(), "bl3p":ccxt.bl3p(), "bleutrade":ccxt.bleutrade(), "braziliex":ccxt.braziliex(), "btcalpha":ccxt.btcalpha(), "btcbox":ccxt.btcbox(), "btcmarkets":ccxt.btcmarkets(), "btctradeua":ccxt.btctradeua(), "btcturk":ccxt.btcturk(), "buda":ccxt.buda(), "bw":ccxt.bw(), "bybit":ccxt.bybit(), "bytetrade":ccxt.bytetrade(), "cex":ccxt.cex(), "chilebit":ccxt.chilebit(), "coinbase":ccxt.coinbase(), "coincheck":ccxt.coincheck(), "coinegg":ccxt.coinegg(), "coinex":ccxt.coinex(), "coinfalcon":ccxt.coinfalcon(), "coinfloor":ccxt.coinfloor(), "coingi":ccxt.coingi(), "coinmarketcap":ccxt.coinmarketcap(), "coinmate":ccxt.coinmate(), "coinone":ccxt.coinone(), "coinspot":ccxt.coinspot(), "coolcoin":ccxt.coolcoin(), "coss":ccxt.coss(), "crex24":ccxt.crex24(), "currencycom":ccxt.currencycom(), "deribit":ccxt.deribit(), "digifinex":ccxt.digifinex(), "dsx":ccxt.dsx(), "eterbase":ccxt.eterbase(), "exmo":ccxt.exmo(), "exx":ccxt.exx(), "fcoin":ccxt.fcoin(), "fcoinjp":ccxt.fcoinjp, "flowbtc":ccxt.flowbtc(), "foxbit":ccxt.foxbit(), "ftx":ccxt.ftx(), "fybse":ccxt.fybse(), "gateio":ccxt.gateio(), "gemini":ccxt.gemini(), "hbtc":ccxt.hbtc(), "hitbtc":ccxt.hitbtc(), "hollaex":ccxt.hollaex(), "huobipro":ccxt.huobipro(), "ice3x":ccxt.ice3x(), "idex":ccxt.idex(), "independentreserve":ccxt.independentreserve(), "indodax":ccxt.indodax(), "itbit":ccxt.itbit(), "kraken":ccxt.kraken(), "kucoin":ccxt.kucoin(), "kuna":ccxt.kuna(), "lakebtc":ccxt.lakebtc(), "latoken":ccxt.latoken(), "lbank":ccxt.lbank(), "liquid":ccxt.liquid(), "livecoin":ccxt.livecoin(), "luno":ccxt.luno(), "lykke":ccxt.lykke(), "mercado":ccxt.mercado(), "mixcoins":ccxt.mixcoins(), "oceanex":ccxt.oceanex(), "okcoin":ccxt.okcoin(), "okex":ccxt.okex(), "paymium":ccxt.paymium(), "poloniex":ccxt.poloniex(), "probit":ccxt.probit(), "qtrade":ccxt.qtrade(), "rightbtc":ccxt.rightbtc(), "southxchange":ccxt.southxchange(), "stex":ccxt.stex(), "stronghold":ccxt.stronghold(), "surbitcoin":ccxt.surbitcoin(), "therock":ccxt.therock(), "tidebit":ccxt.tidebit(), "tidex":ccxt.tidex(), "upbit":ccxt.upbit(), "vaultoro":ccxt.vaultoro(), "vbtc":ccxt.vbtc(), "wavesexchange":ccxt.wavesexchange(), "whitebit":ccxt.whitebit(), "xbtce":ccxt.xbtce(), "yobit":ccxt.yobit(), "zaif":ccxt.zaif(), "zb":ccxt.zb()}
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
    except Exception:
        return False

# We create a list of all exchanges to do error checking on user input
ex_objs = init_supported_exchanges()
print("created list of {} exchanges".format(len(ex_objs)))

# TODO: create an html page to render here
@app.route('/status')
def status():
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
    if flaskRequest.method == 'POST':
        #return the config settings TODO: error check so that the user doesn't have to submit everything at once. Also implement a form here.
        keepWeeks = flaskRequest.json("keepWeeks")
        exchanges = flaskRequest.json("exchanges")
        currencies = flaskRequest.json("currencies")
        interval = flaskRequest.json("interval")
        return {'updated settings?':'yes', 'keepWeeks':keepWeeks, 'currencies':currencies, 'exchanges':exchanges, 'interval':interval}
    else:
        return {'updated settings?':'no', keepWeeks:'keepWeeks', 'currencies':currencies, 'exchanges':exchanges, 'interval':interval}
        

# Get the latest price entry in the database.
# Currency: the three letter base currency desired. Must be a currency you are already collecting data for
# Exchange: the exchange to query data for from the local database. Must be an exchange you are already caching data for (for now)
@app.route('/now/<currency>/<exchange>')
def now(currency, exchange):
    db_n = sqlite3.connect(p)
    if exchange in exchanges:
        #if the exchange is already in the config file
        ticker = "BTC-{}".format(currency.upper())
        statement = "SELECT * FROM {} WHERE pair = '{}' AND timestamp = (SELECT MAX(timestamp) FROM {});".format(exchange, ticker, exchange)
        cursor = db_n.execute(statement)
        res = cursor.fetchone()
        if res != None:
            db_n.close()
            return {'id':res[0], 'timestamp':res[1], 'datetime':res[2], 'currency_pair':res[3], 'open':res[4], 'high':res[5], 'low':res[6], 'close':res[7], 'vol':res[8]} 
        else:
            db_n.close()
            return {'id': res}
    else:
        #make a direct request
        res = request_single(exchange, currency)
        db_n.close()
        if res != None:
            return res
        else:
            return {'id': res}

# Get data from local storage inside of a certain range.
# Parameters: 
#   Currency: the fiat base currency to fetch data for. Should be a three letter currency code in lowercase.
#   Exchange: the exchange to get data from.
#   date_start and date_end: date_start is the oldest time value in the range desired. It can be provided as a millisecond timestamp or as a datetime formatted as "YYYY-MM-DDTHH:mm:SS".
@app.route('/hist/<currency>/<exchange>/<date_start>/<date_end>', methods=['GET'])
def hist(currency, exchange, date_start, date_end):
    db_n = sqlite3.connect(p)
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
            return "malformed dates. Use YYYY-MM-DDTHH:mm:SS or millisecond timestamps. Provide both dates in the same format"
    statement = "SELECT * FROM {} WHERE timestamp > {} AND timestamp < {};".format(exchange, date_s, date_e)
    cursor = db_n.execute(statement)
    res = cursor.fetchall()
    db_n.close()
    return {'columns': ['id', 'timestamp', 'datetime', 'currency_pair', 'open', 'high', 'low', 'close', 'close', 'vol'], 'data':res}


# Make a single request, without having to loop through all exchanges and currency pairs.
# This is intended for when the user requests an exchange in /now that is not present in the database.
# It will probably not be used for /hist because of the length of time getting arbitrary amounts of historical data can be
def request_single(exchange, currency):
    if not is_supported(exchange):
        return "{} is not supported by CCXT".format(exchange)
    obj = ex_objs[exchange]
    ticker = "BTC/{}".format(currency.upper())
    if obj.has['fetchOHLCV']:
        result = None
        if exchange == "bitfinex":
            params = {'limit':100, 'start':(round((datetime.now()-timedelta(hours=1)).timestamp()*1000)), 'end':round(datetime.now().timestamp()*1000)}
            try:
                result = ex_objs[exchange].fetch_ohlcv(symbol=ticker, timeframe='1m', since=None, params=params)
            except Exception as e:
                print("got ratelimited on {}".format(exchange))
        else:
            try:
                result = obj.fetch_ohlcv(ticker, timeframe='1m')
            except Exception as e:
                print("got ratelimited on {}".format(e))
    else:
        try:
            result = obj.fetch_ticker(ticker)
        except Exception as e:
            print("got ratelimited on {}".format(e))
    return {'data': result[-1]}


# Make an HTTP GET request to exchanges via the ccxt API
# TODO: add error checking for if an exchange supports ohlc data. If not, default to regular price data. (done)
# Loop through all chosen exchanges, check if they are supported, loop through all chosen currencies, for each make request to ohlc endpoint if supported, else price ticker. Write data to local storage.
# Bitfinex special rule: bitfinex returns candles from the beginning of time, not the most recent. This is a behavior of the API itself and has nothing to do with this code or ccxt. Therefore we must specify the timeframe desired in the optional params field of the function call with a dictionary of available options.
def request(exchanges,currency,interval,db_n):
    for e in exchanges:
        if is_supported(e):
            for curr in currencies:
                    ticker = "BTC/{}".format(curr)
                    success = True
                    if ex_objs[e].has['fetchOHLCV']:
                        candle = None
                        if e == "bitfinex":
                            params = {'limit':100, 'start':(round((datetime.now()-timedelta(hours=1)).timestamp()*1000)), 'end':round(datetime.now().timestamp()*1000)}
                            try:
                                candle = ex_objs[e].fetch_ohlcv(symbol=ticker, timeframe='1m', since=None, params=params)
                            except Exception as err: #figure out this error type
                                #the point so far is to gracefully handle the error, but waiting for the next cycle should be good enough
                                print("error (fetching candle (bitfinex)): {}".format(err))
                                success = False
                        else:
                            try:
                                candle = ex_objs[e].fetch_ohlcv(ticker, '1m') #'ticker' was listed as 'symbol' before | interval should be determined in the config file 
                            except Exception as err:
                                print("error (fetching candle): {}".format(err))
                                success = False
                        if success:
                            for line in candle:
                                ts = datetime.fromtimestamp(line[0]/1e3) #check here if we have a ms timestamp or not
                                for l in line:
                                    if l == None:
                                        l = 0
                                #this is another error check condition for when null values slip into the data.
                                statement = "INSERT INTO {} (timestamp, datetime, pair, open, high, low, close, volume) VALUES ({}, '{}', '{}', {}, {}, {}, {}, {});".format(e, line[0], ts, ticker.replace("/", "-"), line[1], line[2], line[3], line[4], line[5])
                                db_n.execute(statement)
                                db_n.commit()
                            print("inserted into {} {} {} times".format(e, curr, len(candle)))
                    else:
                        try:
                            price = ex_objs[e].fetch_ticker(ticker)
                        except Exception as err:
                            print("error (fetching ticker): {}".format(err))
                            success = False
                        if success:
                            ts = datetime.fromtimestamp(price['timestamp']/1e3)
                            statement = "INSERT INTO {} (timestamp, datetime, pair, open, high, low, close, volume) VALUES ({}, '{}', '{}', {}, {}, {}, {}, {});".format(e, price['timestamp'], ts, ticker.replace("/", "-"), 0.0, 0.0, 0.0, price['last'], 0.0)
                            db_n.execute(statement)
                            db_n.commit()
                    time.sleep(interval)

# Thread method. Makes requests every interval seconds. 
# Adding this method here to make request more versatile while maintaining the same behavior
def request_periodically(exchanges, currency, interval):
    db_n = sqlite3.connect(p)
    while True:
        request(exchanges, currency, interval,db_n)

# Read the values stored in the config file and store them in memory.
# Run during install and at every run of the server.
# Returns void
def read_config():
    global exchanges
    global interval
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
                print("invalid config setting {}".format(setting_line[0]))
            elif setting_line[0] == "keepWeeks":
                try:
                    keepWeeks = int(setting_line[1])
                except Exception as e:
                    print("could not read keepWeeks field. Using default setting of {} weeks. Error: {}".format(e, keepWeeks))
            elif setting_line[0] == "exchanges":
                exs = setting_line[1].split(" ")
                for e in exs:
                    if e.replace("\n", "") == "all":
                        exchanges = list(ex_objs.keys())
                        break
                    if is_supported(e) == False:
                        print("{} is not supported by ccxt!".format(e))
                    e_formatted = e.replace("\n", "")
                    if e_formatted not in exchanges:
                        exchanges.append(e_formatted)
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
            else:
                return
    #print statement for debugging
    print(" Settings read:\n keepWeeks: {}\n exchanges: {}\n currencies: {}\n interval: {}".format(keepWeeks, exchanges, currencies, interval))

# This method is called at the first run.
# It sets up the required tables inside of a local sqlite3 database. There is one table for each exchange.
# Tables are only created if they do not already exist. Install will attempt to create tables for every listed exchange at once when called.
def install():
    read_config()
    #create the sqlite db
    print("creating tables for {} exchanges if they do not exist already.".format(len(exchanges)))
    for exchange in exchanges:
        #change this to f-strings
        sql = "CREATE TABLE IF NOT EXISTS {} (id INTEGER PRIMARY KEY AUTOINCREMENT, timestamp INTEGER, datetime TEXT, pair TEXT, open REAL, high REAL, low REAL, close REAL, volume REAL)".format(exchange)
        print("created table for {}".format(exchange))
        db.execute(sql)
        db.commit()
    db.close()

# Remove every entry older than now-keepWeeks from all tables in the database
# if there is nothing to prune then nothing will be pruned.
def prune(keepWeeks):
    # prune checks will run continuously and check every 60k seconds right now.
    db_n = sqlite3.connect(p)
    while True:
        for exchange in exchanges:
            #count = ((db.execute("SELECT Count(*) FROM {}".format(exchange))).fetchone())[0]
            cutoff = (datetime.now()-timedelta(weeks=keepWeeks)).timestamp()*1000
            statement = "DELETE FROM {} WHERE timestamp < {};".format(exchange, cutoff)
            db_n.execute(statement)
            db_n.commit()
        time.sleep(60000)
    

if __name__ == "__main__":
    install() #install will call read_config
    prices_thread = Thread(target=request_periodically, args=(exchanges, currency, interval))
    pruning_thread = Thread(target=prune, args=[keepWeeks])
    prices_thread.start()
    pruning_thread.start()
    app.run()
    db.close()


