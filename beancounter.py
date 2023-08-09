# Ref. https://beancount.github.io/docs/the_double_entry_counting_method.html
# Ref.https://beancount.github.io/docs/trading_with_beancount.html
# Given a descriptor, generate a beancount file for accounting purposes.
# For each address check what inputs it has received. Put these under income/debits.
# For each address check what outputs it has paid. Put these under expenses/credits.

# Ref. https://github.com/Blockstream/esplora/blob/master/API.md#block-format

# Output descriptors https://github.com/dgpv/miniscript-alloy-spec
# https://github.com/spesmilo/electrum/issues/5694
# https://github.com/petertodd/python-bitcoinlib/issues/235
# https://github.com/bitcoin/bitcoin/pull/17975

import asyncio
from dataclasses import dataclass, field
from datetime import datetime
import time

from fastapi import HTTPException
from pydantic import BaseModel
import requests

# bdk seems limited. Things I want to be able to do:
# - generate a descriptor from an extended key.
# - test if an address belongs to a HDkey
# - query Esplora or Electrum/Electrs using an agnostic API.
# - load utxo transaction history
# ref. https://raw.githubusercontent.com/bitcoin/bitcoin/master/doc/descriptors.md

import bdkpython as bdk

from lib import Candle

import logging

_GAP_SIZE = 100

class BDKIncompleteSyncError(Exception):
    pass

class TimedOutError(Exception):
    pass

class WalletCreationError(Exception):
    pass

def get_logger(verbose = False):

    import logging
    logger = logging.getLogger(__name__)
    logger.setLevel(logging.INFO)
    if verbose:
        logger.setLevel(logging.DEBUG)

    formatter = logging.Formatter(
        '[%(asctime)s] %(levelname)s (thread %(thread)d):\t%(module)s.%(funcName)s: %(message)s')

    handler  = logging.StreamHandler()
    handler.setFormatter(formatter)
    logger.addHandler(handler)

    import logging.handlers
    handler = logging.handlers.RotatingFileHandler(
            filename    = 'beancounter.log',
            maxBytes    = 1 << 20,
            backupCount = 2,
            )
    handler.setFormatter(formatter)
    logger.addHandler(handler)

    return logger

_logger = get_logger()

@dataclass
class Spotbit:
    url: str

    def get_candles_at_dates(self,
            currency: str,
            dates: list[datetime]):

        result = None

        request = f'{self.url}/api/history/{currency}?exchange=binance'
        body    = [dt.isoformat() for dt in dates]
        response = requests.post(request, json = body)
        if response.status_code == 200:
            result = [Candle(**data) for data in response.json()]
        else:
            detail = ''
            try:
                detail = response.json()
            except requests.exceptions.JSONDecodeError as e:
                detail = response.text
            raise HTTPException(detail = detail, status_code = response.status_code)

        return result

def get_electrum_api(network: bdk.Network) -> str:
    '''
    https://github.com/spesmilo/electrum/blob/master/electrum/servers.json
    '''
    result = f'ssl://electrum.blockstream.info:{(port := 50002 if network == bdk.Network.BITCOIN else 50001)}'
    return result

def get_esplora_api(network: bdk.Network) -> str:
    ESPLORA_API_MAINNET = 'https://blockstream.info/api/'
    ESPLORA_API_TESTNET = 'https://blockstream.info/testnet/api/'

    result = ESPLORA_API_MAINNET if network == bdk.Network.BITCOIN else ESPLORA_API_TESTNET
    return result

Descriptor = str
Address = str   # 'tb1qsjc5mvv2nexal0sltadgx36jdwk88tps0x3eyt'
Txid = str

class ScriptPub(BaseModel):
    scriptpubkey: str
    scriptpubkey_asm: str
    scriptpubkey_type: str
    scriptpubkey_address: Address
    value: int

class Transaction(BaseModel):

    class Vin(BaseModel):
        txid: Txid
        vout: int
        prevout: ScriptPub
        scriptsig: str
        scriptsig_asm: str

    class Vout(BaseModel):
        txid: Txid
        vout: int
        prevout: ScriptPub
        scriptsig: str
        sigasm: str

    class TransactionStatus(BaseModel):
        confirmed: bool
        block_height: int
        block_hash: str
        block_time: datetime

    txid: Txid
    version: int
    locktime: int
    vin: list[Vin]
    vout: list[ScriptPub]
    size: int
    weight: int
    fee: int
    status: TransactionStatus

async def get_transactions(
    addresses: list[bdk.AddressInfo],
    network:   bdk.Network
    ) ->list[Transaction]:
    # FIXME(nochiel) Receiving transactions can be obtained by using external/receiving addresses.
    # FIXME(nochiel) But how to we get spending transactions when bdkpython
    # doesn't allow us to see internal addresses?
    # TEST(nochiel) Check if any of the transactions we retrieve are receiving transactions.
    # My hypothesis is that none of them will ever be. If so then we have to figure out a way
    # to find out receiving transactions.

    result = []

    '''
    # Example of result:

     transactions = [[
         {
             'txid': '8668ded4e71c1e72a82b0746b075737e23975966ba67538ecb01c515cb5afbec',
             'version': 1,
             'locktime' : 0,
             'vin': [
                 {
                     'txid': '2189a075f7d1c53b8af1b58638c639ff4c0a85e72ebb0527aebbebff5d380127',
                     'vout': 1,
                     'prevout': {
                         'scriptpubkey': '001484b14db18a9e4ddfbe1f5f5a8347526bac73ac30',
                         'scriptpubkey_asm': 'OP_0 OP_PUSHBYTES_20 84b14db18a9e4ddfbe1f5f5a8347526bac73ac30',
                         'scriptpubkey_type': 'v0_p2wpkh',
                         'scriptpubkey_address': 'tb1qsjc5mvv2nexal0sltadgx36jdwk88tps0x3eyt',
                         'value': 21000
                         },
                     'scriptsig': '',
                     'scriptsig_asm': '',

                     'witness': ['3045022100c839c17d9aceecf47c7da9e1e3aeed02c0eea37d523d2cf3d6af47303286a87102205c402c5b596f76ed0f58ea64a1a209949d6c23d331edb19d23c31c4f3e966c7b01',
                         '03933ebadaaea3f4337a72213637b84acfa9162e9f00cf36d7bc477cc2d6b1efa7'],
                     'is_coinbase': False,
                     'sequence': 4294967295}],
                 'vout': [
                     {
                         'scriptpubkey': '00141dd1d071e262680535e87384fab9edbbf1ccdee0',
                         'scriptpubkey_asm': 'OP_0 OP_PUSHBYTES_20 1dd 1d071e262680535e87384fab9edbbf1ccdee0',
                         'scriptpubkey_type': 'v0_p2wpkh',
                         'scriptpubkey_address': 'tb1qrhgaqu0zvf5q2d0gwwz04w0dh0cuehhqwtcvz8',
                         'value': 8000
                         },
                     {
                         'scriptpubkey': '0014e3f594c8df944673bf7f9cfa2d473ce31f86dbeb',
                         'scriptpubkey_asm': 'OP_0 OP_PUSHBYTES_20 e3f594c8df944673bf7f9cfa2d473ce31f86dbeb',
                         'scriptpubkey_type': 'v0_p2wpkh',
                         'scriptpubkey_address': 'tb1qu06efjxlj3r880mlnnaz63euuv0cdklthjt87j',
                         'value': 12859}
                     ],
                 'size': 223,
                 'weight': 562,
                 'fee': 141,
                 'status': {'confirmed': True,
                     'block_height': 2140276,
                     'block_hash': '0000000000000032998e909cd91a11c4e540b0ef6c463c7ab41d834874f8f403',
                     'block_time': 1644374701}
                 }
         ]]
    '''

    def get_transactions_for(address: bdk.AddressInfo) -> list[Transaction]:
        # FIXME(nochiel) Don't include unconfirmed transactions.
        from pydantic import parse_obj_as
        _logger.debug(f'{address = }')

        result = []
        wait = 4
        while wait > 0:
            try:
                request = f'{get_esplora_api(network)}/address/{address.address}/txs'
                response = requests.get(request)
                wait = 0
                if response.status_code == 200:
                    _logger.debug(f'{response.json() = }')
                    if response.json():
                        _logger.debug(f'{address.address =}\n{response.json() = }')
                        data = parse_obj_as(list[Transaction], response.json())
                        result.extend(data)
                else:
                    raise HTTPException(status_code = response.status_code,
                                        detail = response.text)

            except (requests.exceptions.ConnectTimeout, requests.exceptions.ConnectionError) as e:
                _logger.debug(f'Rate limited on address: {address}')
                wait *= 2
                time.sleep(wait)

        return result

    tasks = [asyncio.to_thread(get_transactions_for, address)
            for address in addresses]

    transactions_found = await asyncio.gather(*tasks) if len(tasks) else []
    for transactions_for in transactions_found:
        result.extend(transactions_for)

    return result

class CSVFileTransaction(BaseModel):
    Date:    datetime
    Label:   str
    Value:   float
    Balance: float
    Txid:     str

@dataclass
class CSVTransaction:
    csvFileTransaction: CSVFileTransaction
    transaction:        Transaction

@dataclass
class TransactionDetails:
    transaction: bdk.TransactionDetails | CSVTransaction
    twap: float

    def __init__(self, *, transaction, twap):
        self.transaction = transaction
        self.twap = twap

    def id(self) -> str:
        result = '0xCAFEBABE'
        if isinstance(self.transaction, bdk.TransactionDetails):
            result = self.transaction.txid
        elif isinstance(self.transaction, CSVTransaction):
            result = self.transaction.csvFileTransaction.Txid
        return result

    def timestamp(self) -> datetime:
        result = datetime.today()
        if isinstance(self.transaction, bdk.TransactionDetails):
            result = datetime.fromtimestamp(self.transaction.confirmation_time.timestamp)
        elif isinstance(self.transaction, CSVTransaction):
            result = self.transaction.csvFileTransaction.Date

        return result

    def amount(self) -> float:
        '''
        Amount in BTC.
        '''
        result = 0.0
        if isinstance(self.transaction, bdk.TransactionDetails):
            result = self.transaction.received - self.transaction.sent
            result *= 1e-8
        elif isinstance(self.transaction, CSVTransaction):
            result = self.transaction.csvFileTransaction.Value

        return result

    def fees(self) -> float:
        result = 0.0
        if isinstance(self.transaction, bdk.TransactionDetails):
            result = self.transaction.fee
        elif isinstance(self.transaction, CSVTransaction):
            result = self.transaction.transaction.fee

        return result * 1e-8


async def make_transaction_details(
        transactions: list[bdk.TransactionDetails] | list[CSVTransaction],
        currency,
        spotbit: Spotbit
        ) -> list[TransactionDetails]:

    from statistics import mean

    result = []

    candles, dates = [], []
    if isinstance(transactions[0], bdk.TransactionDetails):
        dates = [datetime.fromtimestamp(t.confirmation_time.timestamp)
                 for t in transactions]
    elif isinstance(transactions[0], CSVTransaction):
        dates = [t.csvFileTransaction.Date for t in transactions]

    try:
        candles = spotbit.get_candles_at_dates(currency, dates)
    except HTTPException as e:
        raise Exception(e.detail)

    # FIXME(nochiel) Give the user a good error here.
    assert len(candles) == len(transactions), (
            f'Expected: {len(transactions) = }\tGot: {len(candles) = }')
    if candles:
        for i in range(len(transactions)):
            candle = candles[i]
            detail = TransactionDetails(
                    transaction = transactions[i],
                    twap = round(mean([candle.open, candle.high, candle.low, candle.close]), 2))

            result.append(detail)

    result.sort(key = lambda t: t.timestamp())
    return result


transaction_fees_account = 'Expenses:TransactionFees'
btc_account = 'Assets:Bitcoin'
fiat_account = 'Liabilities:Cash'
def make_records(wallet, descriptor, *,
                 account_name: str,
                 balance = None,
                 transaction_details: list[TransactionDetails],
                 currency: str
        ) -> str:

    # Ref. https://beancount.github.io/docs/beancount_language_syntax.html
    # Create a collection of entries and dump it to text file.
    # - Create accounts
    # - Create transactions
    # - Add postings to transactions.
    # - Dump the account to a file.

    memo    = f'; Transactions for {descriptor}\n'

    # Ref. beancount/realization.py
    type                = 'Assets'
    country             = ''
    institution         = ''
    btc_account_name    = 'Bitcoin'
    fiat_account_name   = currency
    subaccount_name     = ''

    from beancount.core import account

    components = [type.title(), country.title(), institution.title(), btc_account_name, subaccount_name]
    components = [c for c in components if c != '']
    btc_account = account.join(*components)
    assert account.is_valid(btc_account), f'Account name is not valid. Got: {btc_account}'

    # TODO FINDOUT We treat cash as a liability. Is this the best way?
    # Store the exchange rate at each transaction date.
    components = ['liabilities'.title(), 'Cash']
    components = [c for c in components if c != '']
    fiat_account = account.join(*components)
    assert account.is_valid(fiat_account), f'Account name is not valid. Got: {fiat_account}'

    # Loop through on-chain transactions and create transactions and relevant postings for each transaction.
    date_of_account_open = transaction_details[0].timestamp()
    _logger.debug(f'{date_of_account_open = }')

    # Commodity directive
    '''
    1867-07-01 commodity CAD
      name: "Canadian Dollar"
      asset-class: "cash"
    '''
    btc_commodity_directive = (
            ';  2008-10-31 commodity BTC\n'
            ';    name: "Bitcoin"\n'
            ';    asset-class: "cryptocurrency"\n'
            )

    # Account directive
    # e.g. YYYY-MM-DD open Account [ConstraintCurrency,...] ["BookingMethod"]
    account_directives = [
            f'; {date_of_account_open.date()} open {btc_account}\t\t\tBTC',
            f'; {date_of_account_open.date()} open {transaction_fees_account}\tBTC',
            f'; {date_of_account_open.date()} open {fiat_account}\t\t{currency}',
            ]

    balance = balance if balance else wallet.get_balance().confirmed
    # 2012-12-26 balance Liabilities:US:CreditCard   -3492.02 USD
    # FIXME(nochiel) This needs to be correct when we file taxes for a single financial year.
    # TODO(nochiel) If using a `main.bean´ file which includes separate yearly account files,
    # put the balance assertion in the ´main.bean´.
    balance_assertion    = f'{transaction_details[-1].timestamp().date()} balance {btc_account} {balance:.8f} BTC\n\n'

    # TODO(nochiel) For each date record a btc price. Is this necessary?
    # e.g. 2015-04-30 price AAPL 125.15 USD
    # btc_price_directive = ''

    # Transactions and entries. e.g.
    '''
    2014-05-05 * "Using my new credit card"
      Liabilities:CreditCard:CapitalOne         -37.45 USD
      Expenses:Restaurant

    2014-02-03 * "Initial deposit"
    Assets:US:BofA:Checking         100 USD
    Assets:Cash                    -100 USD
    '''
    # TODO Should I generate Expense accounts if there is an output address that's re-used?
    # TODO Create an Asset:BTC and Asset:Cash account
    # The Asset:Cash is equivalent to Asset:BTC but in USD exchange rates at the time of transaction.
    # Because BTC is volatile, we should list transaction time.

    transaction_directives = []
    for detail in transaction_details:
        # Create a beancount transaction for each transaction.
        # Then add beancount transaction entries for each payee/output that is not one of the user's addresses.

        ''' E.g.
        2014-07-11 * "Sold shares of S&P 500"
          Assets:ETrade:IVV               -10 IVV {183.07 USD} @ 197.90 USD
          Assets:ETrade:Cash          1979.90 USD
          Income:ETrade:CapitalGains
        '''

        meta = ''
        date = detail.timestamp().date()
        flag = '*'
        tags = []
        links = []

        payee = 'CUSTOMER' if detail.amount() < 0 else 'VENDOR'
        price_annotation = f' @ {detail.twap :.2f} {currency}\t\n'
        btc_amount_directive = f'\t{btc_account}\t{detail.amount() :.8f} BTC'
        btc_amount_directive += price_annotation

        # FIXME(nochiel) Add cost basis for a transaction posting if it becomes necessary/useful/possible.
        if detail.amount() < 0:
            btc_amount_directive += f'\t{transaction_fees_account}\t{detail.fees():.8f} BTC'
            btc_amount_directive += price_annotation

        transaction_title_directive = f'{date} * "{payee}" "NARRATION"\t; https://blockstream.info/tx/{detail.id()}'

        fiat_amount = detail.twap * detail.amount()
        # fiat_amount_directive = ( f'\t{fiat_account}\t'
        #         f'{-fiat_amount :.2f} {currency}\t')
        fiat_amount_directive = f'\t{fiat_account}\t' # Beancount will infer this entry.
        transaction_directive = transaction_title_directive + '\n'
        transaction_directive += btc_amount_directive
        transaction_directive += fiat_amount_directive + '\n'
        transaction_directives.append(transaction_directive)

    document = f'{memo}\n\n'
    document += btc_commodity_directive
    document += '\n'
    # document += balance_assertion + '\n'
    document += str.join('\n', account_directives)
    document += '\n\n'
    document += str.join('\n', transaction_directives)

    return document

# Parse multipath because BIP88 (Hierarchical Deterministic Path Templates) hasn't yet been accepted.
# https://github.com/bitcoin/bips/blob/master/bip-0088.mediawiki
# Ref. https://github.com/bitcoin/bitcoin/blob/master/doc/descriptors.md#Reference
from enum import Enum
class ScriptType(Enum):
    key     = 'key'     # FIXME(nochiel) Do we need this? We can instead check the type of 'data'.

    sh      = 'sh'
    wsh     = 'wsh'
    pk      = 'pk'
    pkh     = 'pkh'
    wpkh    = 'wpkh'
    combo   = 'combo'
    multi   = 'multi'
    sortedmulti = 'sortedmulti'
    multi_a  = 'multi_a'
    sortedmulti_a = 'sortedmulti_a'
    tr      = 'tr'
    addr    = 'addr'
    raw     = 'raw'

@dataclass
class Key:
    fingerprint: str
    paths:       list[str]

    def __repr__(self):
        result = ''
        data = ''
        for path in self.paths:
            data += path + '/'
        data = data[:len(data) - 1]

        if self.fingerprint:
            result = f'[{self.fingerprint}]'
        result += data
        return result


class Token:
    ...

@dataclass
class Script(Token):
    type: ScriptType
    data: Key | Token

    def __repr__(self):
        result = ''

        if self.type == ScriptType.key:
            result = f'{self.data}'
        else:
            result = f'{self.type.value}({self.data})'

        return result

def get_transactions_from_csv(filename: str, network: bdk.Network) -> tuple[list[Transaction], list[CSVTransaction]]:
    result = []

    def get_tx(txid: Txid) -> Transaction | None:
        result = None
        request = f'{get_esplora_api(network)}/tx/{txid}'
        response = requests.get(request)
        # TODO(nochiel) Merge this with the other transaction code.
        if response.status_code == 200:
            result = Transaction.parse_obj(response.json())
        return result

    import csv
    transactions = []
    with open(filename, 'r') as f:
        r = csv.DictReader(f)
        for row in r:
            tx = get_tx(row['Txid'])
            assert tx
            transactions.append(tx)
            csvTransaction = CSVTransaction(CSVFileTransaction.parse_obj(row), tx)
            result.append(csvTransaction)

    transactions.sort(key = lambda t: t.status.block_time)
    result.sort(key = lambda t: t.csvFileTransaction.Date)

    return transactions, result

async def make_beancount_file_for(*,
                                  spotbit:    Spotbit,
                                  descriptor: Descriptor,
                                  network:    bdk.Network,
                                  account_name: str = '',
                                  csv_filename: str = '',
                                  currency:   str = 'USD',
                                  years:     list[datetime]):

    transaction_details = []
    bdk_sync_was_incomplete = False

    parsed_descriptor = ParsedDescriptor(descriptor)
    _logger.debug(f'{parsed_descriptor = }')
    retry = True

    def new_wallet(descriptor = descriptor, parsed_descriptor = parsed_descriptor) -> bdk.Wallet | None:
        wallet = None
        try:
            wallet = bdk.Wallet(
                    descriptor = (str(parsed_descriptor.external_descriptor)
                        if parsed_descriptor.change_descriptor
                        else descriptor),
                    change_descriptor = (str(parsed_descriptor.change_descriptor)
                        if parsed_descriptor.change_descriptor
                        else descriptor),
                    network = network,
                    database_config = bdk.DatabaseConfig.MEMORY())

        except bdk.BdkError.Descriptor as e:
            if str(e) == 'Descriptor(InvalidDescriptorChecksum)':
                _logger.info('This descriptor has an invalid checksum. We will try to create a wallet without using the checksum provided.')
                assert '#' in descriptor, WalletCreationError(e)
                descriptor = descriptor.partition('#')[0]
                pased_descriptor = ParsedDescriptor(descriptor)
                wallet = new_wallet(descriptor, parsed_descriptor)
            else:
                raise WalletCreationError(e)

        return wallet

    wallet = new_wallet()
    if wallet:
        if not csv_filename:
            '''
            esplora = bdk.BlockchainConfig.ESPLORA(
                    bdk.EsploraConfig(
                        base_url = get_esplora_api(network),
                        proxy = None,
                        stop_gap = _GAP_SIZE,
                        concurrency = 8,
                        timeout = 500,))
            '''
            electrum = bdk.BlockchainConfig.ELECTRUM(
                    bdk.ElectrumConfig(
                        url = get_electrum_api(network),
                        socks5 = None,
                        retry = 5,
                        timeout = 100,
                        stop_gap = _GAP_SIZE))
            blockchain = bdk.Blockchain(electrum)

            while retry:
                try:
                    class Progress(bdk.Progress):
                        def update(self, progress, message):
                            _logger.info(f'Syncing wallet: {progress}, {message}')

                    _logger.info('Attempting to sync wallet.')
                    wallet.sync(blockchain, Progress())
                    _logger.info('Wallet sync completed.')

                    bdk_sync_was_incomplete = (wallet.list_transactions() and wallet.get_balance().confirmed == 0)
                    if bdk_sync_was_incomplete:
                        raise BDKIncompleteSyncError(f'{len(wallet.list_transactions()) = }, {wallet.get_balance().confirmed = }')

                    _logger.debug('Wallet sync successful.')
                    _logger.debug(f'{str(wallet.get_balance()) =}')

                    if not wallet.list_transactions():
                        if len(parsed_descriptor.keys[0].paths) == 1:
                            _logger.info('The descriptor has no paths. We will attempt to use a default path of "0/*" to create the wallet.')
                            retry = True
                            parsed_descriptor.keys[0].paths.extend(['0', '*'])
                            descriptor = str(parsed_descriptor.external_descriptor)
                            _logger.debug(f'{descriptor = }')
                            continue

                    retry = False

                except (bdk.BdkError.Esplora, bdk.BdkError.Electrum) as e:
                    # FIXME(nochiel) We don't need to handle this here.
                    # Esplora(Ureq(Transport(Transport { kind: Io, message: None, url: Some(Url { scheme: "https", cannot_be_a_base: false, username: "", password: None, host: Some(Domain("blockstream.info ")), port: None, path: "/testnet/api//blocks/tip/height", query: None, fragment: None }), source: Some(Custom { kind: TimedOut, error: Transport(Transport { kind: Io, message: Some("Error encountered in the status line"), url: None, source: Some(Os { code: 10060, kind: TimedOut, message: "A connection attempt failed because the connected party did not properly respond after a period of time, or established connection failed because connected host has failed to respond." }), response: None }) }), response: None })))
                    retry = False
                    if 'TimedOut' in str(e) or 'UnexpectedEof' in str(e):
                        _logger.error(e)
                        raise TimedOutError('Esplora/Electrum timed out. Wait a while then try again later.')
                    raise Exception('Error while syncing wallet.', e)

            assert wallet

            if not wallet.list_transactions():
                _logger.info(f'{descriptor} does not have any transactions within a gap size of {_GAP_SIZE}.')
                return

            if not csv_filename:
                _logger.debug('Making transaction details from wallet.')
                transaction_details  = await make_transaction_details(
                        transactions = wallet.list_transactions(),
                        currency     = currency,
                        spotbit      = spotbit)

    balance = wallet.get_balance().confirmed * 1e-8  if wallet else 0

    all_transaction_details = []
    if csv_filename:
        _logger.debug('Making transaction details from csv file.')
        # TODO(nochiel) allow the user to specify a csv exported from sparrow wallet from which to import transactions.
        transactions, csv_rows = get_transactions_from_csv(csv_filename, network)
        all_transaction_details = await make_transaction_details(csv_rows, currency, spotbit)
        balance = csv_rows[-1].csvFileTransaction.Balance

    @dataclass
    class BeanDocument:
        filename: str
        document: str

        def write(self):
            if self.document:
                from beancount.scripts import format
                formatted_document = format.align_beancount(self.document)
                with open(self.filename, mode = 'w') as file:
                    file.write(formatted_document)

        def validate(self):
            # Validate document
            from beancount import loader
            _, errors, _ = loader.load_string(self.document)
            if errors:
                _logger.error(f'---{len(errors)} Errors in "{self.filename}"---')
                for i, error in enumerate(errors):
                    _logger.error(f'{i}: {error}')
                    _logger.error('--')
                _logger.error('---End of errors in beancount file---')

    documents = []
    for year in years:
        transaction_details = list(filter(lambda td: td.timestamp().year == year.year,
                                          all_transaction_details))
        assert transaction_details, Exception('No transaction details.')

        _logger.debug('Making beancount file.')
        beancount_document = make_records(wallet, descriptor,
                account_name = account_name,
                transaction_details = transaction_details,
                currency            = currency,
                balance = balance)

        if not beancount_document:
            raise Exception('The beancount file was not generated')

        destination = 'reports/{year.year}'
        _logger.info(f'Writing beancount file to {destination = }')
        document = BeanDocument(f'destination/{format_filename(parsed_descriptor, account_name, year)}',
                                beancount_document)
        if document:
            document.write()
            documents.append(document)

    # TODO Put common headers in main file.
    main_file = '''option "title" "Blockchain Commons - Combined Journals"

; =================
; OPTIONS
; =================

; USD Currency related options

2019-01-01 commodity USD
  name: "United States Dollar"
  asset-class: "cash"

2008-10-31 commodity BTC
  name: "Bitcoin"
  asset-class: "cryptocurrency"

option "operating_currency" "USD"

option "inferred_tolerance_default" "USD:0.01"

; BTC Currency Related options

option "inferred_tolerance_default" "BTC:0.000000001"

option "booking_method" "LIFO"
2000-01-01 custom "fava-extension" "fava_investor" "{}"

'''

    def make_include_directives(documents):
        # E.g include "./2022/bc-2022-bitcoin-sponsors-7hramevw.bean"
        result = []
        for d in documents:
            result.append(f'include "{d.filename}"') # FIXME(nochiel)
        return result

    def make_main_headers():
        result = ''

        # Account directive
        # e.g. YYYY-MM-DD open Account [ConstraintCurrency,...] ["BookingMethod"]
        date_of_account_open = all_transaction_details[0].timestamp()
        account_directives = [
                f'{date_of_account_open.date()} open Assets:Bitcoin\t\tBTC',
                f'{date_of_account_open.date()} open {transaction_fees_account}\tBTC',
                f'{date_of_account_open.date()} open {fiat_account}\t\t{currency}',
                ]
        result = str.join('\n', account_directives) + '\n'

        return result

    main_file += make_main_headers()
    main_file += '\n'
    main_file += str.join('\n', make_include_directives(documents))
    main_document = BeanDocument('reports/main.bean', main_file)
    main_document.write()
    main_document.validate()


class DescriptorType(Enum):
    '''
    Ref. https://developer.bitcoin.org/devguide/transactions.html#standard-transactions
    '''
    UNKNOWN         = 0
    LEGACY          = 'legacy'
    LEGACY_MULTISIG = 'legacymultisig'
    # Ref. https://en.bitcoin.it/wiki/BIP_0141#Examples
    NESTED          = 'nested'
    NESTED_MULTISIG = 'nestedmultisig'
    SEGWIT          = 'segwit'
    SEGWIT_MULTISIG = 'segwitmultisig'
    TAPROOT         = 'taproot'

@dataclass(init = False)
class Account:
    # Ref. BIP44
    # m / purpose' / coin_type' / account' / change / address_index
    purpose:    int = field(default = 0)
    coin_type:  str = field(default = '')
    change:     int = field(default = 0)
    index:      int = field(default = 0)
    account:    str = field(default = '0h')

    def __init__(self, derivation_steps: str):
        ...

    def get_account_number(self):
        return self.account[:-1]

@dataclass(init = False)
class ParsedDescriptor:
    external_descriptor : Script | None = field(default = None)
    change_descriptor   : Script | None = field(default = None)
    fingerprint         : str = field(default = '')
    account             : Account = field(default = Account(''))    # TODO(nochiel)
    keys                : list[Key] = field(default_factory = list)           # 'multi', 'tr', have n+1 keys.
    type                : DescriptorType = field(default = DescriptorType.UNKNOWN)
    checksum            : str = field(default = '')

    LEGACY_PREFIXES = {'1', '5', 'K', 'L', 'M'}
    NESTED_SEGWIT_PREFIXES = {'3'}
    SEGWIT_PREFIXES = {'bc1', 'tb1'}
    BIP32_PREFIXES  = {'xpub', 'xprv', 'ypub', 'zpub', 'tpub', 'tprv'}

    def __init__(self, descriptor: Descriptor):
        '''
        Given a descriptor (maybe with a multipath template),
        parse it out into (descriptor, change_descriptor) pair.
        '''
        _logger.debug(f'{descriptor=}')

        def parse_keys(data: str) -> list[Key]:
            # Assumption: data has one key.
            # Assumption: data has a multipath descriptor in its path.
            _logger.debug(data)
            result = []

            self.fingerprint = ''
            cursor = 0
            if data[0] == '[':
                _logger.debug('Parsing fingerprint.')
                cursor = data.find(']')
                self.fingerprint = data[1 : cursor]
                # hierarchy = data[1 : cursor]
                # end_fingerprint = hierarchy.find('/')
                # self.fingerprint = hierarchy[: end_fingerprint]
                # self.account = Account(data[1 : cursor])
                cursor += 1

            key_data = data[cursor:] or None
            if key_data:
                _logger.debug(f'{key_data=}')
                main_key_paths, change_key_paths = [], []
                paths = key_data.split('/')
                has_change_path = False
                for path in paths[1:]:

                    if path[0] in {'{', '<'}: # multipath descriptor
                        has_change_path = True
                        temp = path[1 : len(path) - 1]
                        temp = temp.split(';')
                        # TODO(nochiel) TEST: Is this a valid assumption.
                        main_key_paths.append(temp[0])
                        change_key_paths.append(temp[1])
                    else:
                        main_key_paths.append(path)
                        change_key_paths.append(path)

                if has_change_path:
                    result.append(Key(self.fingerprint, [paths[0]] + main_key_paths))
                    result.append(Key(self.fingerprint, [paths[0]] + change_key_paths))
                else:
                    _logger.debug(f'{paths=}')
                    result.append(Key(self.fingerprint, paths))

            _logger.info(f'{result=}')
            return result

        def parse_script(
            # outer_script: Script|None = None,     # FIXME(nochiel) Unused.
            script: str = ''
            ) -> list[Script]:
            # TODO(nochiel) Parse 'multi' and 'sortedmulti' script keys.
            # TODO(nochiel) Parse 'tr' keys.
            _logger.debug(f'{script}')

            result          = []
            script_start    = 0
            script_end      = len(script)
            script_type     = ''

            i = script.find('(')
            if i == -1:
                _logger.debug('Parsing key.')
                self.keys   = parse_keys(script)
                result = [Script(ScriptType.key, key) for key in self.keys]
            else:
                script_type  = script[:i]
                script_start = i + 1
                script_end   = script.rfind(')')
                inner_script = script[script_start : script_end]
                result = [Script(ScriptType[script_type], script)
                    for script in parse_script(inner_script)]

            _logger.debug(f'{result = }')
            return result

        _logger.debug('Looking for checksum.')
        checksum_index = descriptor.find('#')
        script = descriptor
        checksum = ''
        if checksum_index != -1:
            _logger.debug('Checksum found.')
            script, self.checksum = descriptor.split('#')

        descriptors = parse_script(script)
        _logger.debug(f'{descriptors = }')
        if len(descriptors) == 1:
            [self.external_descriptor, self.change_descriptor] = descriptors[0], None
        else:
            [self.external_descriptor, self.change_descriptor] = descriptors
        _logger.debug(f'{self.external_descriptor = }')
        _logger.debug(f'{self.change_descriptor = }')

    def get_address_type(self) -> DescriptorType:
        # Ref. https://en.bitcoin.it/wiki/List_of_address_prefixes
        # Ref. https://shiftcrypto.ch/blog/what-are-bitcoin-address-types/
        # Determine type from:
        #   - type of key
        #   - 'purpose' field of descriptor. (corresponds to the bip.)
        #   - xpub/ypub/tpub

        result = DescriptorType.UNKNOWN
        script = self.external_descriptor
        if script:
            # TODO(nochiel) First check the account hierarchy for a purpose which specifies the BIP.
            # FINDOUT(nochiel) Does this matter?
            # BIP49 = Nested?
            # BIP84 = Segwit?

            key = self.keys[0].paths[0] # Assume we can use the first key as canonical.
            match script.type:
                case ScriptType.tr | ScriptType.multi_a | ScriptType.sortedmulti_a :
                    result = DescriptorType.TAPROOT

                case ScriptType.multi | ScriptType.sortedmulti:
                    # Multisig.
                    result = DescriptorType.LEGACY_MULTISIG
                    if key[:4] in ParsedDescriptor.BIP32_PREFIXES:
                        key = key[4:]

                    if key[:3] in ParsedDescriptor.SEGWIT_PREFIXES:
                        result = DescriptorType.SEGWIT_MULTISIG
                    elif key[0] in ParsedDescriptor.NESTED_SEGWIT_PREFIXES:
                        result = DescriptorType.NESTED_MULTISIG

                case ScriptType.pk | ScriptType.pkh | ScriptType.sh:
                    result = DescriptorType.LEGACY

                case ScriptType.wsh | ScriptType.wpkh:
                    result = DescriptorType.SEGWIT
                    # TODO(nochiel) Check all keys not just the first one.
                    if key[0] in ParsedDescriptor.NESTED_SEGWIT_PREFIXES:
                        result = DescriptorType.NESTED
        return result

def format_filename(descriptor: ParsedDescriptor, account_name: str, year: datetime) -> str:
    # TODO Format this according to BlockchainCommons standards.
    # Ref. https://github.com/BlockchainCommons/Research/blob/master/Investigation/Files.md
    # 'Seed Id - Key ID - HDKey from Seed Name - Type - [Master Fingprint _ Descriptor Type _ Account # _  Descriptor Checksum] - Format.filetype'

    result = ''

    # Seed ID — The first 7 digits of the SHA256 digest of the seed.
    seed_id = NotImplemented    # We don't have access to the seed when given a descriptor.

    # Key ID — The first 7 digits of the SHA256 digest of the key.
    key = descriptor.keys[0].paths[0]
    key_id = key[5:13] if key[:4] in ParsedDescriptor.BIP32_PREFIXES else key[:8]

    # Descriptor Type — A textual descriptor of the derivation path, currently: "legacy", "legacymultisig", "nested", "nestedmultisig", "segwit", "segwitmultisig", or "taproot".
    descriptor_type = descriptor.get_address_type().value

    account_number = descriptor.account.get_account_number() if descriptor.account else 0

    # HDKey from Seed Name — The prefix "HDKey from" prepended to randomly created or user-selected name for seed. Space separated.
    from random_username.generate import generate_username
    seedname = f'HDKey from {generate_username()[0]}'

    document_type = 'Output'

    # result = (
    #         f'{key_id}-'
    #         f'HDKey from {seedname}-'
    #         f'{document_type}-'
    #         f'[{descriptor.fingerprint}_{account_number}_{descriptor_type}_{descriptor.checksum}]'
    #         '.bean'
    #         )
    result = (
            f'{year.year}_'
            f'{account_name}_'
            f'{descriptor.checksum}'
            '.bean'
            )

    return result

###

import typer
from lib import Network

from typing import Optional

def beancount(
        descriptor:  Descriptor,
        spotbit_url: str = 'http://localhost:5000',     # 'http://spotbit.info',
        year:        list[datetime] = typer.Option([datetime(year = 2022, month = 1, day = 1)],
                                                     formats = ['%Y']),
        name:        Optional[str] = None, # TODO(nochiel) Document this.
        csv:         Optional[str] = None,
        network:     Network = Network.TESTNET,
        currency:    str = 'USD',
        verbose:     bool = False):
    '''
    Generate a beancount file using the transactions found by generating addresses from the bitcoin mainnet descriptor.

    Ref. https://beancount.github.io/docs/trading_with_beancount.html
    '''

    # _logger = get_logger(verbose)
    assert _logger, "A logger wasn't created."
    if verbose:
        _logger.setLevel(logging.DEBUG)

    spotbit = Spotbit(spotbit_url)
    import bdkpython as bdk
    bdk_network = bdk.Network[network.name.upper()]

    try:
       _logger.debug('Starting')
       _logger.debug(f'GAP_SIZE: {_GAP_SIZE}')

       result = asyncio.run(
               make_beancount_file_for(descriptor = descriptor,
                                       account_name = name if name else 'Tax report',
                                       csv_filename = csv if csv else '',
                                       years = year,
                                       currency = currency,
                                       network = bdk_network,
                                       spotbit = spotbit),
               # debug = True
               )
       result = result.result() if result else None
    except Exception as e:
        _logger.error(e)
        if e.__cause__: _logger.error(e.__cause__)
        typer.echo()
        typer.echo(f'---')
        typer.echo(f'An error occurred while generating a beancount file.')
        if str(e): typer.echo(e)
        typer.echo(f'---')
        if verbose:
            raise e

if __name__ == '__main__':
    typer.run(beancount)






