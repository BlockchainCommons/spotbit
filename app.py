# TODO(nochiel) Add tests 
# TODO(nochiel) - Standard error page/response for non-existent routes?

import asyncio
from datetime import datetime, timedelta
from http import HTTPStatus
import logging
import os
import pathlib 
import sys
import time

import ccxt

from fastapi import FastAPI, HTTPException
from pydantic import BaseModel, BaseSettings, validator

class ServerErrors:     # TODO(nochiel) Replace these with HTTPException
    NO_DATA = 'Spotbit did not find any data.'
    EXCHANGE_NOT_SUPPORTED = 'Spotbit is not configured to support the exchange.'
    BAD_DATE_FORMAT = 'Please use dates in YYYY-MM-DDTHH:mm:ss ISO8601 format or unix timestamps.'

class Error(BaseModel):
    code        : int
    reason      : str
    exchange    : str
    currency    : str

class Settings(BaseSettings):

    exchanges:              list[str] = []
    currencies:             list[str]

    onion:                  str | None = None
    debug:                  bool  = False

    @validator('currencies')
    def uppercase_currency_names(cls, v):
        assert v and len(v), 'no currencies'
        return [exchange.upper() for exchange in v]

    class Config:
        env_file = 'spotbit.config'

# TODO(nochiel) Write comprehensive tests for each exchange so that
# we can determine which ones shouldn't be supported i.e. populate
# this list with exchanges that fail tests.
_unsupported_exchanges = []     
_supported_exchanges: dict[str, ccxt.Exchange] =  {} 

def get_logger():

    import logging
    logger = logging.getLogger(__name__)
    if _settings.debug: logger.setLevel(logging.DEBUG)      

    formatter = logging.Formatter(
        '[%(asctime)s] %(levelname)s (thread %(thread)d):\t%(module)s.%(funcName)s: %(message)s')

    handler  = logging.StreamHandler()
    handler.setFormatter(formatter)
    logger.addHandler(handler)

    import logging.handlers
    handler = logging.handlers.RotatingFileHandler(
            filename    = 'spotbit.log',
            maxBytes    = 1 << 20,
            backupCount = 2,
            )
    handler.setFormatter(formatter)
    logger.addHandler(handler)

    return logger

_settings = Settings()

# TODO(nochiel) Move this to the settings class.
from enum import Enum
CurrencyName = Enum('CurrencyName', [(currency, currency) for currency in _settings.currencies])  

logger = get_logger()
assert logger

app = FastAPI(debug = _settings.debug)

logger.debug(f'Using currencies: {_settings.currencies}')
if not _settings.exchanges:
    logger.info('using all exchanges.')
    _settings.exchanges = list(ccxt.exchanges)

assert _settings.exchanges

logger.info('Initialising supported exchanges.')
for e in _settings.exchanges:
    if e in ccxt.exchanges and e not in _unsupported_exchanges:
        _supported_exchanges[e] = ccxt.__dict__[e]() 
        try:
            if app.debug is False: _supported_exchanges[e].load_markets()
        except Exception as e:
            logger.debug(f'Error loading markets for {e}.')

assert _supported_exchanges

ExchangeName = Enum('ExchangeName', [(id.upper(), id) for id in _supported_exchanges]) 

# Exchange data is sometimes returned as epoch milliseconds.
def is_ms(timestamp): return timestamp % 1e3 == 0

class Candle(BaseModel):
    timestamp   : datetime
    open        : float
    high        : float
    low         : float
    close       : float
    volume      : float

    @validator('timestamp')
    def time_in_seconds(cls, v):
        result = v

        if type(v) is int and is_ms(v): 
            result = int(v * 1e-3)

        return result

    class Config:
        json_encoders = {
                datetime: lambda v: v.isoformat()
                }

def get_supported_pair_for(currency: CurrencyName, exchange: ccxt.Exchange) -> str:
    assert exchange

    result = ''

    exchange.load_markets()
    market_ids = {f'BTC{currency.value}', f'XBT{currency.value}', f'BTC{currency.value}'.lower(), f'XBT{currency.value}'.lower()}
    market_ids_found = list((market_ids & exchange.markets_by_id.keys()))
    if market_ids_found:
        market_id = market_ids_found[0]
        market = exchange.markets_by_id[market_id]
        if market:
            result = market['symbol']
            logger.debug(f'Found market {market}, with symbol {result}')

    return result


# FIXME(nochiel) Redundancy: Merge this with get_history.
# TODO(nochiel) TEST Do we really need to check if fetchOHLCV exists in the exchange api? 
# TEST ccxt abstracts internally using fetch_trades so we don't have to use fetch_ticker ourselves.
def request_single(exchange: ccxt.Exchange, currency: CurrencyName) -> Candle | None:
    '''
    Make a single request, without having to loop through all exchanges and currency pairs.
    '''
    assert exchange and isinstance(exchange, ccxt.Exchange)
    assert currency

    exchange.load_markets()
    pair = get_supported_pair_for(currency, exchange)
    if not pair: return None

    result = None
    latest_candle = None
    dt = None


    if exchange.has['fetchOHLCV']:
        logger.debug('fetchOHLCV')

        timeframe = '1m'
        match exchange.id:
            case 'btcalpha' | 'hollaex':
                timeframe = '1h'
            case 'poloniex':
                timeframe = '5m'

        # Some exchanges have explicit limits on how many candles you can get at once
        # TODO(nochiel) Simplify this by checking for 2 canonical limits to use.
        limit = 1000
        match exchange.id:
            case 'bitstamp':
                limit = 1000
            case 'bybit':
                limit = 200
            case 'eterbase':
                limit = 1000000
            case 'exmo':
                limit = 3000
            case 'btcalpha':
                limit = 720

        since = round((datetime.now() - timedelta(hours=1)).timestamp() * 1e3)

        # TODO(nochiel) TEST other exchanges requiring special conditions: bitstamp, bitmart?
        params = []
        if exchange.id == 'bitfinex': 
            params = {
                    'limit':100,
                    'start': since,
                    'end':  round(datetime.now().timestamp() * 1e3)
                    }

        try:
            candles = exchange.fetchOHLCV(
                    symbol      = pair, 
                    timeframe   = timeframe, 
                    limit       = limit, 
                    since       = since, 
                    params      = params)

            latest_candle = candles[-1]   

        except Exception as e:
            logger.error(f'error requesting candle from {exchange.name}: {e}')

    else:       # TODO(nochiel) TEST 
        logger.debug(f'fetch_ticker: {pair}')

        candle = None
        try:
            candle = exchange.fetch_ticker(pair)
        except Exception as e:
            logger.error(f'error on {exchange} fetch_ticker: {e}')

        latest_candle = candle

    if latest_candle:
        result = Candle(
                timestamp   = latest_candle[OHLCV.timestamp],
                open        = latest_candle[OHLCV.open],
                high        = latest_candle[OHLCV.high],
                low         = latest_candle[OHLCV.low],
                close       = latest_candle[OHLCV.close],
                volume      = latest_candle[OHLCV.volume]
                )

    return result


# Routes
# TODO(nochiel) Add tests for routes.

# TODO(nochiel) Put the api behind an /api/v1 path.

# TODO(nochiel) Make this the Spotbit frontend.
@app.get('/')
def index():

    raise HTTPException(
            detail  =  'Not implemented.',
            status_code = 404
            )


@app.get('/api/status')
def status(): return "server is running"

# TODO(nochiel) FINDOUT Do we need to enable clients to change configuration? 
# If clients should be able to change configuration, use sessions.
@app.get('/api/configure')
def get_configuration():
    return {
            'currencies': _settings.currencies,
            'exchanges':  _settings.exchanges,
            }

def calculate_average_price(candles: list[Candle]) -> Candle:

    assert candles

    from statistics import mean 
    average_open     = mean(candle.open for candle in candles) 
    average_high     = mean(candle.high for candle in candles) 
    average_low      = mean(candle.low for candle in candles) 
    average_close    = mean(candle.close for candle in candles)
    average_volume   = mean(candle.volume for candle in candles)

    candle = Candle(
            timestamp = min(candle.timestamp for candle in candles),
            open    = average_open,
            high    = average_high,
            low     = average_low,
            close   = average_close,
            volume  = average_volume,
            )
    return candle

class ExchangeDetails(BaseModel):
    id: str
    name: str
    url : str
    countries: list[str]
    currencies: list[str]

@app.get('/api/exchanges', response_model = list[ExchangeDetails])
async def get_exchanges():
    # Ref. https://github.com/BlockchainCommons/spotbit/issues/54
    '''
    Get a list of exchanges that this instance of Spotbit has been configured to use.
    '''

    def get_supported_currencies(exchange: ccxt.Exchange) -> list[str] :

        required = set(_settings.currencies)
        given    = set(exchange.currencies.keys())

        return list(required & given)

    result: list[ExchangeDetails] = []

    assert _supported_exchanges

    def get_exchange_details(exchange: ccxt.Exchange) -> ExchangeDetails:

        result = None

        assert exchange
        exchange.load_markets()

        currencies = []
        if exchange.currencies: 
            currencies = [c for c in _settings.currencies 
                    if c in exchange.currencies]

        details = ExchangeDetails(
                id      = exchange.id,
                name    = exchange.name,
                url     = exchange.urls['www'],
                countries = exchange.countries,
                currencies = get_supported_currencies(exchange))    # TODO(nochiel) TEST

        result = details
        return result

    tasks = [asyncio.to_thread(get_exchange_details, exchange) 
            for exchange in _supported_exchanges.values()]
    details = await asyncio.gather(*tasks)

    result = list(details)

    return result

class PriceResponse(BaseModel):
    candle           : Candle
    exchanges_used   : list[str]
    failed_exchanges : list[str]

@app.get('/api/now/{currency}', response_model = PriceResponse)
async def now_average(currency: CurrencyName):
    '''
    Return an average price from the exchanges configured for the given currency.
    '''

    result = None

    logger.debug(f'currency: {currency}')

    def get_candle(exchange: ccxt.Exchange, currency: CurrencyName) -> tuple[ccxt.Exchange, Candle | None]:
        assert exchange
        assert currency

        result = (exchange, None)
        exchange.load_markets()
        if currency.value in exchange.currencies:
            try:
                candle = None
                candle = request_single(exchange, currency.value)
                if candle:
                    result = exchange, candle 
            except Exception as e:
                logger.error(f'error requesting data from exchange: {e}')

        return result

    tasks = [asyncio.to_thread(get_candle, exchange, currency)
            for exchange in _supported_exchanges.values()]
    task_results = await asyncio.gather(*tasks)
    logger.debug(f'task results: {task_results}')

    candles = []
    failed_exchanges = []
    for exchange, candle in task_results:
        if candle: 
            candles.append(candle)
        else:
            failed_exchanges.append(exchange.name)

    logger.debug(f'candles: {candles}')
    average_price_candle = None
    if len(candles):
        average_price_candle = calculate_average_price(candles)
    else:
        raise HTTPException(
                status_code = HTTPStatus.INTERNAL_SERVER_ERROR,
                detail      =  'Spotbit could get any candle data from the configured exchanges.')

    exchanges_used = [exchange.name for exchange in _supported_exchanges.values()
            if exchange.name not in failed_exchanges]

    result = PriceResponse(
            candle           = average_price_candle,
            exchanges_used   = exchanges_used,
            failed_exchanges = failed_exchanges,
            )

    return result

@app.get('/api/now/{currency}/{exchange}', response_model = Candle)
def now(currency: CurrencyName, exchange: ExchangeName):
    '''
    parameters:
        exchange: an exchange to use.
        currency: the symbol for the base currency to use e.g. USD, GBP, UST.
    '''

    if exchange.value not in _supported_exchanges:
        raise HTTPException(
                status_code = HTTPStatus.INTERNAL_SERVER_ERROR,
                detail      = f'Spotbit is not configured to use {exchange.value} exchange.')

    result      = None

    ccxt_exchange    = _supported_exchanges[exchange.value]
    assert ccxt_exchange
    ccxt_exchange.load_markets()

    if currency.value not in ccxt_exchange.currencies:
       raise HTTPException(
               status_code = HTTPStatus.INTERNAL_SERVER_ERROR,
               detail      = f'Spotbit does not support {currency.value} on {ccxt_exchange}.' ) 

    result = request_single(ccxt_exchange, currency)
    if not result:
        raise HTTPException(
                status_code = HTTPStatus.INTERNAL_SERVER_ERROR,
                detail = ServerErrors.NO_DATA
                )

    return result

from enum import IntEnum
class OHLCV(IntEnum):
    '''
    Indices for components ina candle list.
    '''
    timestamp   = 0
    open        = 1
    high        = 2
    low         = 3
    close       = 4
    volume      = 5

def get_history(*, 
        exchange: ccxt.Exchange, 
        since: datetime,
        limit: int,
        timeframe: str,
        pair: str) -> list[Candle] | None:

    assert exchange
    logger.debug(f'{exchange} {pair} {since}')

    result = None

    _since = round(since.timestamp() * 1e3)

    params = {}
    if exchange == "bitfinex":
        params = {'end' : round(end.timestamp() * 1e3)}

    candles = None
    try:
        wait = exchange.rateLimit * 1e-3
        while wait:
            try:
                candles = exchange.fetchOHLCV(
                        symbol      = pair, 
                        limit       = limit, 
                        timeframe   = timeframe, 
                        since       = _since, 
                        params      = params)

                wait = 0

            except ccxt.errors.RateLimitExceeded as e:
                logger.debug(f'{e}. Rate limit for {exchange} is {exchange.rateLimit}')
                time.sleep(wait)
                wait *= 2

    except Exception as e:
        logger.error(f'{exchange} candle request error: {e}')

    if candles:
        result = [Candle(
            timestamp   = candle[OHLCV.timestamp],
            open        = candle[OHLCV.open],
            high        = candle[OHLCV.high],
            low         = candle[OHLCV.low],
            close       = candle[OHLCV.close],
            volume      = candle[OHLCV.volume]
            )

            for candle in candles]

    return result

@app.get('/api/history/{currency}/{exchange}', response_model = list[Candle])
async def get_candles_in_range(
        currency:   CurrencyName, 
        exchange:   ExchangeName, 
        start:      datetime, 
        end:        datetime = datetime.now()):
    '''
    parameters:
        exchange(required): an exchange to use.
        currency(required): the symbol for the base currency to use e.g. USD, GBP, UST.
        start, end(required): datetime formatted as ISO8601 "YYYY-MM-DDTHH:mm:SS" or unix timestamp.
    '''

    ccxt_exchange = _supported_exchanges[exchange.value]
    ccxt_exchange.load_markets()
    assert ccxt_exchange.currencies
    assert ccxt_exchange.markets

    pair = get_supported_pair_for(currency, ccxt_exchange)
    if not pair:
        raise HTTPException(
                detail = f'Spotbit does not support the {pair} pair on {ccxt_exchange}',
                status_code = HTTPStatus.INTERNAL_SERVER_ERROR) 

    result = None

    start = start.astimezone(start.tzinfo)
    end = end.astimezone(end.tzinfo)

    (start, end) = (end, start) if end < start else (start, end)
    logger.debug(f'start: {start}, end: {end}')

    limit = 100
    candles = None
    periods = []

    dt = timedelta(hours = 1)
    params = None
    timeframe = '1h'

    if ccxt_exchange.timeframes:
        if '1h' in ccxt_exchange.timeframes:
            timeframe   = '1h' 
            dt          = timedelta(hours = 1)

        elif '30m' in ccxt_exchange.timeframes:
            timeframe = '30m'
            dt          = timedelta(minutes = 30)

    n_periods, remaining_frames_duration = divmod(end - start, dt * 100)
    remaining_frames = remaining_frames_duration // dt
    logger.debug(f'requesting #{n_periods + remaining_frames} periods')

    if n_periods == 0: 
        n_periods               = 1
        limit, remaining_frames = remaining_frames, 0
    for i in range(n_periods):
        periods.append(start + i * (dt * 100))

    logger.debug(f'requesting periods with {limit} limit: {periods}')

    tasks = []
    args = dict( exchange = ccxt_exchange, 
                limit = limit,
                timeframe = timeframe,
                pair = pair)

    for period in periods:
        args['since'] = period
        task = asyncio.to_thread(get_history,
                **args)
        tasks.append(task)

    if remaining_frames > 0:
        last_candle_time = periods[-1] + (dt * 100)
        assert last_candle_time < end
        logger.debug(f'remaining_frames: {remaining_frames}')

        args['since'] = last_candle_time   
        args['limit'] = remaining_frames
        task = asyncio.to_thread(get_history,
             **args) 
        tasks.append(task)

        new_last_candle_time = last_candle_time + (dt * remaining_frames ) 
        logger.debug(f'new_last_candle_time: {new_last_candle_time}')

    task_results = await asyncio.gather(*tasks)
    candles = []
    for result in task_results:   
        if result: candles.extend(result)

    expected_number_of_candles = (n_periods * limit) + remaining_frames
    received_number_of_candles = len(candles)
    if received_number_of_candles < expected_number_of_candles:
        logger.info(f'{ccxt_exchange} does not have data for the entire period. Expected {expected_number_of_candles} candles. Got {received_number_of_candles} candles')

    if candles is None or len(candles) == 0:
        raise HTTPException(
                detail  = f'Spotbit did not receive any candle history for the period {start} - {end} from {ccxt_exchange}',
                status_code = HTTPStatus.INTERNAL_SERVER_ERROR)

    logger.debug(f'got: {len(candles)} candles')
    logger.debug(f'candles: {candles[:10]} ... {candles[-10:]}')
    result = candles

    return result


# TODO(nochiel) If no exchange is given, test all supported exchanges until we get candles for all dates.
# Return all database rows within `tolerance` for each of the supplied dates
@app.post('/api/history/{currency}/{exchange}')
async def get_candles_at_dates(
        currency: CurrencyName, 
        exchange: ExchangeName,
        dates:    list[datetime]) -> list[Candle]:
    '''
    Dates should be provided in the body of the request as a json array of  dates formatted as ISO8601 "YYYY-MM-DDTHH:mm:SS".
    '''

    if exchange.value not in _supported_exchanges:
        raise HTTPException(
                detail      = ServerErrors.EXCHANGE_NOT_SUPPORTED,
                status_code = HTTPStatus.INTERNAL_SERVER_ERROR) 

    ccxt_exchange = _supported_exchanges[exchange.value]
    ccxt_exchange.load_markets()

    pair = get_supported_pair_for(currency, ccxt_exchange)
            
    # Different exchanges have different ticker formates
    if not pair:   
        raise HTTPException(
                detail = f'Spotbit does not support the BTC/{currency.value} pair on {exchange.value}',
                status_code = HTTPStatus.INTERNAL_SERVER_ERROR) 

    # FIXME(nochiel) Different exchanges return candle data at different resolutions.
    # I need to get candle data in the lowest possible resolution then filter out the dates needed.
    limit = 100
    timeframe = '1h'

    if ccxt_exchange.timeframes:
        if '1h' in ccxt_exchange.timeframes:
            timeframe   = '1h' 

        elif '30m' in ccxt_exchange.timeframes:
            timeframe = '30m'

    candles_found: tuple[list[Candle] | None] 
    args = [dict(exchange = ccxt_exchange, 
            limit = limit,
            timeframe = timeframe,
            pair = pair,

            since = date)
            for date in dates]
    tasks = [asyncio.to_thread(get_history, **arg) 
            for arg in args]
    candles_found = await asyncio.gather(*tasks)

    candles = []
    if candles_found: 
        result = [candles_at[0] for candles_at in candles_found if candles_at]

    return result

def tests():
    # Placeholder
    # Expected: validation errors or server errors or valid responses.

    import requests
    response = requests.get('http://[::1]:5000/api/now/FOOBAR')
    response = requests.get('http://[::1]:5000/api/now/usd')
    response = requests.get('http://[::1]:5000/api/now/USD')
    response = requests.get('http://[::1]:5000/api/now/JPY')

    response = requests.get('http://[::1]:5000/api/now/USD/Bitstamp')
    response = requests.get('http://[::1]:5000/api/now/USD/bitstamp')
    response = requests.get('http://[::1]:5000/api/now/usdt/bitstamp')  

    response = requests.get(
            'http://[::1]:5000/api/history/USD/bitstamp?start=2019-01-01T0000&end=1522641600'
            )

    response = requests.get(
            "http://[::1]:5000/api/history/USD/liquid?start=2022-01-01T00:00&end=2022-02-01T00:00"
            )

    response = requests.post('http://[::1]:5000/history/USDT/binance',
            json = ['2022-01-01T00:00', '2022-02-01T00:00', '2021-12-01T00:00']
            )

    response = requests.post(
            "http://[::1]:5000/api/history/JPY/liquid",
            json=["2022-01-01T00:00", "2022-02-01T00:00", "2021-12-01T00:00"],
            )

if __name__ == '__main__':
    import uvicorn

    assert logger
    logger.debug('Running in debug mode')
    logger.debug(f'app.debug: {app.debug}')
    uvicorn.run('app:app', 
            host ='::', 
            port = 5000, 
            debug = True,
            log_level = 'debug', 
            reload = True)
