# TODO(nochiel) Add tests / data validation.
# FIXME(nochiel) Fix crash when you make an API call that throws an exception.
# TODO(nochiel) Migrate to FastAPI
# TODO(nochiel) Give the client structured errors.
# TODO(nochiel) - Create a new exception type so that client receives structured errors as a response.
# TODO(nochiel) - If there is no data available for a response, provide a good error.

import asyncio
import logging
from datetime import datetime, timedelta
import time
import sys
import os
import pathlib 
import statistics 
from http import HTTPStatus

import ccxt

import flask
from flask import request


from pydantic import BaseModel, BaseSettings, validator

class ServerErrors:     # TODO(nochiel) Replace these with HTTPException
    NO_DATA = 'Spotbit did not find any data.'
    EXCHANGE_NOT_SUPPORTED = 'Spotbit is not configured to support the exchange.'


class Error(BaseModel):
    code        : int
    reason      : str
    exchange    : str
    currency    : str

class Settings(BaseSettings):

    exchanges:              list[str] = []
    currencies:             list[str] = []

    averaging_time:         int = 1

    onion:                  str | None = None

    @validator('currencies')
    def uppercase_currency_names(cls, v):
        assert v and len(v) > 0, 'no currencies'
        return [exchange.upper() for exchange in v]

    class Config:
        env_file = 'spotbit.config'

# TODO(nochiel) Write comprehensive tests for each exchange so that
# we can determine which ones shouldn't be supported i.e. populate
# this list with exchanges that fail tests.
_unsupported_exchanges = []     
_supported_exchanges: dict[str, ccxt.Exchange] =  {} # TODO(nochiel) Load these when self.exchanges is loaded.

app = flask.Flask(__name__)

# TODO(nochiel) TEST Ensure logging can tell us when and why the app crashes.
import logging.handlers
handler = logging.handlers.RotatingFileHandler(
        filename    = 'spotbit.log',
        maxBytes    = 1 << 20,
        backupCount = 2,
        )
handler.setLevel(logging.DEBUG)
formatter = logging.Formatter(
    '[%(asctime)s] %(levelname)s (thread %(thread)d):\t%(module)s.%(funcName)s: %(message)s')
handler.setFormatter(formatter)

from flask.logging import default_handler
default_handler.setFormatter(formatter)
app.logger.addHandler(handler)

_settings = Settings()
app.logger.debug(f'using currencies: {_settings.currencies}')
if len(_settings.exchanges) == 0:
    app.logger.info('using all exchanges.')
    _settings.exchanges = list(ccxt.exchanges)

assert _settings.exchanges

app.logger.info('Initialising supported exchanges.')
for e in _settings.exchanges:
    if e in ccxt.exchanges and e not in _unsupported_exchanges:
        _supported_exchanges[e] = ccxt.__dict__[e]() 
        if not app.debug: _supported_exchanges[e].load_markets()

assert _supported_exchanges

# FIXME(nochiel) Do we need this test? 
# Check if a timestamp has ms precision by modding by 1e3
def is_ms(timestamp): return timestamp % 1e3 == 0

class Candle(BaseModel):
    timestamp   : int   
    open        : float
    high        : float
    low         : float
    close       : float
    volume      : float
    
    class Config:
        json_encoders = {
                datetime: lambda v: v.isoformat()
                }

def request_single(exchange: ccxt.Exchange, currency: str) -> Candle | None:
    '''
    Make a single request, without having to loop through all exchanges and currency pairs.
    '''
    assert exchange and isinstance(exchange, ccxt.Exchange)
    assert str

    # TODO(nochiel) Add a type for result.
    result = None
    ticker = f'BTC/{currency}'
    dt = None

    if ticker not in exchange.markets:
        return None

    # TODO(nochiel) Check that exchange supports currency.
    if exchange.has['fetchOHLCV']:
        app.logger.debug('fetchOHLCV')

        timeframe = '1m'
        match exchange.id:
            case 'bleutrade' | 'btcalpha' | 'rightbtc' | 'hollaex':
                timeframe = '1h'
            case 'poloniex':
                timeframe = '5m'

        # some exchanges have explicit limits on how many candles you can get at once
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

        # TODO(nochiel) TEST other exchanges requiring special conditions: bitstamp, bitmart
        params = []
        if exchange.id == 'bitfinex': 
            params = {
                    'limit':100,
                    'start': since,
                    'end':  round(datetime.now().timestamp() * 1e3)
                    }

        try:
            candles = exchange.fetchOHLCV(
                    symbol      = ticker, 
                    timeframe   = timeframe, 
                    limit       = limit, 
                    since       = since, 
                    params      = params)

            latest_candle = candles[-1]   

            timestamp = latest_candle[OHLCV.timestamp]
            timestamp = timestamp * 1e-3 if is_ms(int(timestamp)) else timestamp

            result = Candle(
                    timestamp   = timestamp,
                    open        = latest_candle[OHLCV.open],
                    high        = latest_candle[OHLCV.high],
                    low         = latest_candle[OHLCV.low],
                    close       = latest_candle[OHLCV.close],
                    volume      = latest_candle[OHLCV.volume]
                    )
        except Exception as e:
            app.logger.error(f'error requesting candle from {exchange.name}: {e}')

    else:       # TODO(nochiel) TEST 
        app.logger.debug(f'fetch_ticker: {ticker}')

        candle = None
        try:
            candle = exchange.fetch_ticker(ticker)
        except Exception as e:
            app.logger.error(f'error on {exchange} fetch_ticker: {e}')

        if candle:
            app.logger.debug(f'{exchange} candle: {candle}')
            timestamp = candle[OHLCV.timestamp]
            timestamp = timestamp * 1e-3 if is_ms(timestamp) else timestamp

            result = candle

    return result

# Routes
# TODO(nochiel) Add tests for routes.

# TODO(nochiel) Add new route for the Spotbit UI.
# TODO(nochiel) Put the api behind an /api/v1 path.

@app.get('/')
def index():
    # FIXME(nochiel) 

    date_start = (datetime.now() - timedelta(days=5)).timestamp() * 1e3
    date_end = (datetime.now()).timestamp() * 1e3
    onion   =  _settings.onion
    f0 = f"{onion}/now/USD/coinbasepro"
    f1 = f"{onion}/now/USD"
    f2 = f"{onion}/hist/USD/coinbasepro/{date_start}/{date_end}"
    f3 = f"{onion}/configure"

    return flask.render_template('index.html', 
            fetch_0 = f0,
            fetch_1 = f1,
            fetch_2 = f2,
            fetch_3 = f3,
            date_start = date_start,
            date_end = date_end)

@app.get('/status')
def status(): return "server is running"

# TODO(nochiel) FINDOUT Do we need to enable clients to change configuration? 
# If clients should be able to change configuration, use sessions.
@app.get('/configure')
def get_configuration():
    return {
            'currencies':       _settings.currencies,
            'exchanges':        _settings.exchanges,
            }

def calculate_average_price(candles: list[Candle]) -> Candle:

    assert candles and len(candles) > 0

    mean = statistics.mean
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

def get_supported_currencies(exchange: ccxt.Exchange) -> list[str] :

    required = set(_settings.currencies)
    given    = set([c for c in exchange.currencies])

    return list(required & given)


@app.get('/exchanges')
async def get_exchanges():
    # Ref. https://github.com/BlockchainCommons/spotbit/issues/54
    # Expected: output that looks like:
    '''
     [
            {"id": "kraken", "name": "Kraken", "url": "https://www.kraken.com/", "country": "US", "currencies": ["USD"]},
            {"id": "ascendex", "name": "AscendEX", "url": "https://ascendex.com/", "country": "SG", "currencies": ["USD", "JPY", "GBP"]}
     ]
    '''
    ...

    class ExchangeResult(BaseModel):
        exchanges: list[ExchangeDetails]

    result: ExchangeResult | None = None

    assert _supported_exchanges

    async def get_exchange_details(exchange: ccxt.Exchange) -> ExchangeDetails:

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
                currencies = get_supported_currencies(exchange))

        result = details
        return result

    tasks = [get_exchange_details(exchange) 
            for exchange in _supported_exchanges.values()]
    details = await asyncio.gather(*tasks)
    result = ExchangeResult(exchanges = list(details))

    return result.dict()

@app.get('/now/<currency>')
async def now_average(currency: str):
    '''
    Return an average of the 5 curated exchanges for that currency.
    '''

    class PriceResponse(BaseModel):
        candle           : Candle
        exchanges_used   : list[str]
        failed_exchanges : list[str]

    result = None

    currency = currency.upper()
    averaging_time = _settings.averaging_time   

    async def get_candle(exchange: ccxt.Exchange, currency: str) -> tuple[ccxt.Exchange, Candle | None]:
        assert exchange
        assert currency

        result = (exchange, None)
        exchange.load_markets()
        if currency in exchange.currencies:
            try:
                candle = None
                candle = request_single(exchange, currency)
                if candle:
                    result = exchange, candle 
            except Exception as e:
                app.logger.error(f'error requesting data from exchange: {e}')

        return result

    tasks = [asyncio.create_task(get_candle(exchange, currency))
            for exchange in _supported_exchanges.values()]
    task_results = await asyncio.gather(*tasks)
    app.logger.debug(f'task results: {task_results}')

    candles = []
    failed_exchanges = []
    for exchange, candle in task_results:
        if candle: 
            candles.append(candle)
        else:
            failed_exchanges.append(exchange.name)

    app.logger.debug(f'candles: {candles}')
    if len(candles) > 0 :
        average_price_candle = calculate_average_price(candles)
    else:
        flask.abort(flask.Response(response = 'SpotBit could get any candle data from the configured exchanges.',
            status = HTTPStatus.INTERNAL_SERVER_ERROR))

    exchanges_used = [exchange.name for exchange in _supported_exchanges.values()
            if exchange.name not in failed_exchanges]

    result = PriceResponse(
            candle           = average_price_candle,
            exchanges_used   = exchanges_used,
            failed_exchanges = failed_exchanges,
            )

    return result.dict()   

@app.get('/now/<currency>/<exchange>')
def now(currency, exchange):
    '''
    parameters:
        exchange(required): an exchange to use.
        currency(required): the symbol for the base currency to use e.g. USD, GBP, UST.
    '''

    if exchange not in _supported_exchanges:
       flask.abort(flask.Response(response = f'SpotBit is not configured to use {exchange} exchange.',
           status = HTTPStatus.INTERNAL_SERVER_ERROR)) 

    result      = None
    currency    = currency.upper()
    exchange    = _supported_exchanges[exchange]
    exchange.load_markets()
    if currency not in exchange.currencies:
       flask.abort(flask.Response(response = f'Spotbit does not support the {currency} on {exchange}',
           status = HTTPStatus.INTERNAL_SERVER_ERROR)) 

    assert exchange
    assert currency

    # TODO(nochiel) Handle exception.
    result = request_single(exchange, currency)

    if not result:
       flask.abort(flask.Response(response = ServerErrors.NO_DATA,
           status = HTTPStatus.INTERNAL_SERVER_ERROR)) 

    return result.dict()

class OHLCV:
    '''
    Indices for components ina candle list.
    '''
    timestamp   = 0
    open        = 1
    high        = 2
    low         = 3
    close       = 4
    volume      = 5

# FIXME(nochiel) Use query parameters.
#   - exchange, currency, date_end are optional.
# FIXME(nochiel) Add parameter validation.
# TODO(nochiel) Write tests
@app.get('/history/<currency>/<exchange>/<date_start>/<date_end>')
async def get_candles_in_range(currency, exchange, date_start, date_end):
    '''
    parameters:
        exchange(required): an exchange to use.
        currency(required): the symbol for the base currency to use e.g. USD, GBP, UST.
        date_start, date_end(required): datetime formatted as ISO8601 "YYYY-MM-DDTHH:mm:SS".
    '''

    if exchange not in _supported_exchanges:
       flask.abort(flask.Response(response = f'SpotBit is not configured to use {exchange} exchange.',
           status = HTTPStatus.INTERNAL_SERVER_ERROR)) 

    exchange = _supported_exchanges[exchange]
    exchange.load_markets()
    assert exchange.currencies
    assert exchange.markets
    currency = currency.upper()
    if currency not in exchange.currencies:
       flask.abort(flask.Response(response = f'Spotbit does not support the {currency} on {exchange}',
           status = HTTPStatus.INTERNAL_SERVER_ERROR)) 

    pair = f'BTC/{currency}' 
    if exchange.id == 'bitmex':
        pair = f'BTC/{currency}:{currency}'
    if pair not in exchange.markets:
       flask.abort(flask.Response(response = f'Spotbit does not support the {pair} pair on {exchange}',
           status = HTTPStatus.INTERNAL_SERVER_ERROR)) 

    result = None
    try:
        # start  = round((datetime.fromisoformat(date_start)).timestamp() * 1e3)
        start   = datetime.fromisoformat(date_start)
        end      = datetime.fromisoformat(date_end)
        (start, end) = (end, start) if end < start else (start, end)
    except ValueError as e:
        flask.abort(flask.Response(response = f'Error: {e}. Please use dates in YYYY-MM-DDTHH:mm:ss ISO8601 format.',
            status = HTTPStatus.BAD_REQUEST))

    limit = 100

    candles = None
    periods = []

    # Consider enabling a backup historical candle feed e.g. coinmarketcap, coingecko, cryptowa.ch, graph or a dex?
    # Especially if there's a feed that allows you to filter by an exchange.
    if exchange.has['fetchOHLCV'] is not True:
        flask.abort(flask.Response(
            response = f'{exchange} does not support pagination of historical candles. Please try to use a different exchange.',
            status = HTTPStatus.BAD_REQUEST))

    dt = timedelta(0)
    params = None
    timeframe = ''
    if '1h' in exchange.timeframes:
        timeframe   = '1h' 
        dt          = timedelta(hours = 1)

    elif '30m' in exchange.timeframes:
        timeframe = '30m'
        dt          = timedelta(minutes = 30)

    n_periods, remaining_frames_duration = divmod(end - start, dt * 100)
    remaining_frames = remaining_frames_duration // dt
    app.logger.debug(f'requesting #{n_periods + remaining_frames} periods')

    if n_periods == 0: 
        n_periods               = 1
        limit, remaining_frames = remaining_frames, 0
    for i in range(n_periods):
        periods.append(start + i * (dt * 100))

    app.logger.debug(f'requesting periods with {limit} limit: {periods}')

    async def get_history(*, 
            exchange: ccxt.Exchange = exchange, 
            since: datetime,
            limit: int = limit,
            timeframe: str = timeframe):
        assert exchange

        app.logger.debug(f'{exchange} {pair} {since}')

        # FIXME(nochiel) Handle ccxt.base.errors.RateLimitExceeded
        rateLimit = exchange.rateLimit 
        _since = int(since.timestamp() * 1e3)

        params = {}
        if exchange == "bitfinex":
            params = { 'end' : round(end.timestamp() * 1e3) }

        candles = None
        try:
            candles = exchange.fetchOHLCV(
                symbol      = pair, 
                limit       = limit, 
                timeframe   = timeframe, 
                since       = _since, 
                params      = params)

        except Exception as e:
            app.logger.error(f'{exchange} candle request error: {e}')

        return candles

    tasks = []
    for p in periods:
        task = asyncio.create_task(get_history(
            exchange = exchange, 
            since = p)) 
        tasks.append(task)

    if remaining_frames > 0:
        last_candle_time = periods[-1] + (dt * 100)
        assert last_candle_time < end
        app.logger.debug(f'remaining_frames: {remaining_frames}')
        task = asyncio.create_task(get_history(
            since = last_candle_time,   
            limit = remaining_frames)) 
        tasks.append(task)
        
        new_last_candle_time = last_candle_time + (dt * remaining_frames ) 
        app.logger.debug(f'new_last_candle_time: {new_last_candle_time}')

    candles = await asyncio.gather(*tasks)
    _candles = []
    for c in candles:   # flatten candles
        _candles += c
    candles = _candles

    assert len(candles) == (n_periods * limit) + remaining_frames

    if candles is None or len(candles) == 0:
        flask.abort(flask.Response(response = f'Spotbit did not receive any candle history for the period {start} - {end} from {exchange}',
            status = HTTPStatus.INTERNAL_SERVER_ERROR))

    app.logger.debug(f'got: {len(candles)} candles')
    app.logger.debug(f'candles: {candles[:10]} ... {candles[-10:]}')

    # FIXME(nochiel) Make a type for this. Also is this the best way to return candle data?
    return flask.jsonify(candles)

tests_for_get_candles_at_dates = [
        '''curl http://localhost:5000/history/usdt/binance --header 'Content-Type:application/json' --data '[\"2022-01-01T00:00 \", \"2022-02-01T00:00\", \"2021-12-01T00:00\"]''',
        ]

# Return all database rows within `tolerance` for each of the supplied dates
@app.post('/history/<currency>/<exchange>')
async def get_candles_at_dates(currency, exchange):
    '''
    Parameters: 
        Dates should be provided in the body of the request as a json array of  dates formatted as ISO8601 "YYYY-MM-DDTHH:mm:SS".
    '''

    app.logger.debug(f'{request.get_data()}')

    if exchange not in _supported_exchanges:
        flask.abort(flask.Response(
            response = ServerErrors.EXCHANGE_NOT_SUPPORTED, 
            status   = HTTPStatus.INTERNAL_SERVER_ERROR
            ))
    exchange = _supported_exchanges[exchange]

    if exchange.has['fetchOHLCV'] is not True:
        flask.abort(flask.Response(
            response = f'{exchange} does not support pagination of historical candles. Please try to use a different exchange.',
            status = HTTPStatus.BAD_REQUEST))

    try: 
        app.logger.debug(f'request data: {request.get_data()}')
        dates = request.get_json()
        dates = [datetime.fromisoformat(date) for date in dates] if dates else None
        app.logger.debug(f'dates: {dates}')
    except Exception as e:
        flask.abort(flask.Response(
            response = f'error processing dates: {e}',
            status = HTTPStatus.INTERNAL_SERVER_ERROR))

    results = None
    exchange.load_markets()
    pair = f'BTC/{currency.upper()}'
    if pair not in exchange.markets:
        flask.abort(flask.Response(response = f'Spotbit does not support the {pair} pair on {exchange}',
            status = HTTPStatus.INTERNAL_SERVER_ERROR)) 

    limit = 1
    timeframe = '1h'
    if '1h' in exchange.timeframes:
        timeframe   = '1h' 

    elif '30m' in exchange.timeframes:
        timeframe = '30m'

    candles = {}
    params = {}
    async def get_candle(*,
            exchange: ccxt.Exchange = exchange, 
            since: datetime,
            limit: int = limit,
            timeframe: str = timeframe,
            pair: str = pair,
            ) -> Candle | None:

        assert exchange

        result = None
        candle, candles = None, None
        try:
            candles = exchange.fetchOHLCV(
                    symbol      = pair,
                    timeframe   = timeframe,
                    limit       = limit,
                    since       = int(since.timestamp() * 1e3),
                    params      = params)

        except Exception as e:
            app.logger.error(e)

        if candles and len(candles[0]) > 0:
            app.logger.debug(f'candle: {candle}')
            candle = candles[0]
            result = Candle(
                    timestamp = candle[OHLCV.timestamp],
                    open    = candle[OHLCV.open],
                    high    = candle[OHLCV.high],
                    low     = candle[OHLCV.low],
                    close   = candle[OHLCV.close],
                    volume  = candle[OHLCV.volume]
                    )

        return result

    assert dates
    tasks = [asyncio.create_task(get_candle(since = date)) 
            for date in dates]
    candles = await asyncio.gather(*tasks)
    candles = [candle for candle in candles if candle is not None]

    class CandleListResponse(BaseModel):
        pair: str
        candles: list[Candle]

    result = CandleListResponse(pair = pair,
            candles = candles)

    return result.dict()
