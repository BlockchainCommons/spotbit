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

def get_logger(verbose = False):

    import logging
    logger = logging.getLogger(__name__)
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

        request = f'{self.url}/api/history/{currency}'
        body    = [dt.isoformat() for dt in dates]
        response = requests.post(request, json = body)
        if response.status_code == 200:
            result = [Candle(**data) for data in response.json()]

        return result

def get_esplora_api(network: bdk.Network) -> str:
    ESPLORA_API_MAINNET = 'https://blockstream.info/api/'
    ESPLORA_API_TESTNET = 'https://blockstream.info/testnet/api/'

    result = ''
    match network:
        case bdk.Network.BITCOIN:
            result = ESPLORA_API_MAINNET
        case bdk.Network.TESTNET:
            result = ESPLORA_API_TESTNET
    return result

_GAP_SIZE = 1_000    

Descriptor = str
Address = str
Transactions = list[dict]

async def get_transactions(
    addresses: list[Address],
    network:   bdk.Network
    ) -> dict[Address, Transactions]:

    result = []

    '''
    # Example of result: 

     transactions = [[{'txid': '8668ded4e71c1e72a82b0746b075737e23975966ba67538ecb01c515cb5afbec',
         'version': 1,
         'locktime' : 0,
         'vin': [{'txid': '2189a075f7d1c53b8af1b58638c639ff4c0a85e72ebb0527aebbebff5d380127',
             'vout': 1,
             'prevout': {'scriptpubkey': '001484b14db18a9e4ddfbe1f5f5a8347526bac73ac30',
                 'scriptpubkey_asm': 'OP_0 OP_PUSHBYTES_20 84b14db18a9e4ddfbe1f5f5a8347526bac73ac30',
                 'scriptpubkey_type': 'v0_p2wpkh',
                 'scriptpubkey_address': 'tb1qsjc5mvv2nexal0sltadgx36jdwk88tps0x3eyt',
                 'value': 21000},
             'scriptsig': '',
             'scriptsig_asm': '',

             'witness': ['3045022100c839c17d9aceecf47c7da9e1e3aeed02c0eea37d523d2cf3d6af47303286a87102205c402c5b596f76ed0f58ea64a1a209949d6c23d331edb19d23c31c4f3e966c7b01',
                 '03933ebadaaea3f4337a72213637b84acfa9162e9f00cf36d7bc477cc2d6b1efa7'],
             'is_coinbase': False,
             'sequence': 4294967295}],
         'v out': [{'scriptpubkey': '00141dd1d071e262680535e87384fab9edbbf1ccdee0',
             'scriptpubkey_asm': 'OP_0 OP_PUSHBYTES_20 1dd 1d071e262680535e87384fab9edbbf1ccdee0',
             'scriptpubkey_type': 'v0_p2wpkh',
             'scriptpubkey_address': 'tb1qrhgaqu0zvf5q2d0gwwz04w0dh0cuehhqwtcvz8',
             'value': 8000},
             {'scriptpubkey': '0014e3f594c8df944673bf7f9cfa2d473ce31f86dbeb',
                 'scriptpubkey_asm': 'OP_0 OP_PUSHBYTES_20 e3f594c8df944673bf7f9cfa2d473ce31f86dbeb',
                 'scriptpubkey_type': 'v0_p2wpkh',
                 'scriptpubkey_address': 'tb1qu06efjxlj3r880mlnnaz63euuv0cdklthjt87j',
                 'value': 12859}],
             'size': 223,
             'weight': 562,
             'fee': 141,
             'status': {'confirmed': True,
                 'block_height': 2140276,
                 'block_hash': '0000000000000032998e909cd91a11c4e540b0ef6c463c7ab41d834874f8f403',
                 'block_time': 1644374701}}]]
        '''

    def get_transactions_for(address: Address) -> dict[Address, Transactions]:
        # FIXME(nochiel) Don't include unconfirmed transactions.

        # _logger.debug(address)

        result = {address: []}

        wait = 4
        while wait > 0:

            try:
                request = f'{get_esplora_api(network)}/address/{address}/txs'
                response = requests.get(request)
                wait = 0
                if response.status_code == 200: 
                    result[address] = response.json()
                    # _logger.debug(result)
                else:
                    _logger.error(response.status_code)
                    _logger.error(response.text)
                    _logger.error(f'Using: {request}')
                    raise HTTPException(status_code = response.status_code,
                                        detail = response.text)

            except (requests.exceptions.ConnectTimeout, requests.exceptions.ConnectionError) as e:
                _logger.debug(f'rate limited on address: {address}')
                wait *= 2
                time.sleep(wait)

        return result

    # _logger.debug(f'Getting transactions for: {addresses[0]}')
    tasks = [asyncio.to_thread(get_transactions_for, address)
            for address in addresses]

    transactions_found = await asyncio.gather(*tasks) if len(tasks) else []
    result = {address : transactions
            for address_transactions in transactions_found
            for address, transactions in address_transactions.items() }

    # _logger.debug(f'result {result}')
    return result

class TransactionDetails():
    timestamp: datetime 
    hash: str 
    is_input: bool 
    twap: float

    def __init__(self, *, timestamp = None, hash = None, is_input = None, twap = None):
        self.timestamp   = timestamp
        self.hash        = hash
        self.is_input    = is_input
        self.twap        = twap

TransactionDetailsForAddresses = dict[Address, list[TransactionDetails]] 
async def make_transaction_details(
        transactions: dict[Address, Transactions],
        currency,
        spotbit: Spotbit
        ) -> TransactionDetailsForAddresses:

    from statistics import mean

    addresses = transactions.keys()
    result = {address: [] for address in addresses}

    def get_transaction_details_for(address: str, 
            transactions: Transactions, 
            ) -> TransactionDetailsForAddresses:

        assert transactions 

        result = {address: []}
        
        timestamps_to_get = [datetime.fromtimestamp(transaction['status']['block_time'])
                for transaction in transactions]
    
        assert len(timestamps_to_get)

        candles = []
        try:
            assert spotbit, 'The Spotbit client has not been initialised.'
            candles = spotbit.get_candles_at_dates(
                    currency = currency,
                    dates = timestamps_to_get)

        except HTTPException as e:
            raise Exception(e.detail) from e

        if candles:
            assert len(candles) == len(transactions), (
                    f'Expected: len(transactions): {len(transactions)}\tGot: len(candles): {len(candles)}')
            _logger.debug(f'candles: {candles}')
            for i in range(len(transactions)):
                transaction = transactions[i]
                inputs = transaction['vin']
                is_input = False
                for input in inputs:
                    prevout = input['prevout']
                    is_input = (prevout['scriptpubkey_address'] == address)
                    if is_input: break

                timestamp = datetime.fromtimestamp(transaction['status']['block_time'])
                candle    = candles[i]

                detail = TransactionDetails(
                        timestamp = timestamp,
                        hash = transaction['txid'],
                        is_input = is_input,
                        twap = round(mean([candle.open, candle.high, candle.low, candle.close]), 2))
                result[address].append(detail)

        return result

    tasks = []
    for address, transactions_for in transactions.items():
        if len(transactions_for):
            tasks.append(asyncio.to_thread(get_transaction_details_for, 
                address = address, transactions = transactions_for))


    if tasks:
        transaction_details = await asyncio.gather(*tasks)

        for details_for in transaction_details:
            for address, details in details_for.items():
                result[address].extend(details)

    return result

def make_records(descriptor, *, 
        transaction_details: TransactionDetailsForAddresses, 
        transactions: dict[Address, Transactions],
        currency: str
        ) -> str:

    # Ref. https://beancount.github.io/docs/beancount_language_syntax.html
    # Create a collection of entries and dump it to text file.
    # - Create accounts
    # - Create transactions 
    # - Add postings to transactions.
    # - Dump the account to a file.

    memo = f'# Transactions for {descriptor}'
    # Ref. beancount/realization.py
    type                = 'Assets'
    country             = ''
    institution         = ''
    btc_account_name    = 'BTC'
    fiat_account_name   = currency
    subaccount_name     = ''

    from beancount.core import account

    components = [type.title(), country.title(), institution.title(), btc_account_name, subaccount_name]
    components = [c for c in components if c != '']
    btc_account = account.join(*components)
    assert account.is_valid(btc_account), f'Account name is not valid. Got: {btc_account}'

    # TODO FINDOUT We treat cash as a liability. Is this the best way?
    # Store the exchange rate at each transaction date.
    components = ['liabilities'.title(), 'Cash', fiat_account_name, subaccount_name]
    components = [c for c in components if c != '']
    fiat_account = account.join(*components)
    assert account.is_valid(fiat_account), f'Account name is not valid. Got: {fiat_account}'

    # Loop through on-chain transactions and create transactions and relevant postings for each transaction.

    def get_earliest_blocktime(transactions: dict[Address, Transactions] = transactions) -> datetime:

        result = datetime.now()
        txs = list(transactions.values())[0]
        _logger.debug(txs)
        if txs[0]:
            result = datetime.fromtimestamp(txs[0]['status']['block_time'])

        for transactions_for in transactions.values():
            if transactions_for:
                for transaction in transactions_for:
                    timestamp = datetime.fromtimestamp(transaction['status']['block_time'])
                    result = timestamp if timestamp < result else result

        return result

    date_of_account_open = get_earliest_blocktime().date()
    _logger.debug(f'date_of_account_open: {date_of_account_open }')

    # Commodity directive
    '''
    1867-07-01 commodity CAD
      name: "Canadian Dollar"
      asset-class: "cash"
    '''
    btc_commodity_directive = (
            '2008-10-31 commodity BTC\n'
            '  name: "Bitcoin"\n'
            '  asset-class: "cryptocurrency"\n'
            )

    # Account directive
    # e.g. YYYY-MM-DD open Account [ConstraintCurrency,...] ["BookingMethod"]
    account_directives = [
            f'{date_of_account_open} open {btc_account}\tBTC',
            f'{date_of_account_open} open {fiat_account}\t{currency}',
            ]

    transactions_by_hash = {tx['txid'] : tx 
            for for_address in transactions.values()
            for tx in for_address}

    # TODO(nochiel) Order transactions by date. For each date record a btc price.
    # e.g. 2015-04-30 price AAPL 125.15 USD
    btc_price_directive = ''

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

    class Payee:
        def __init__(self, address: str, amount: int):
            self.address = address
            self.amount = amount    # satoshis

    Transaction = dict

    def get_payees(
            transaction: Transaction,
           ) -> list[Payee]:

        assert Transaction

        result = []

        outputs = transaction['vout']
        result = [Payee(address = output['scriptpubkey_address'], amount = output['value']) 
                for output in outputs]

        return result

    assert transaction_details
    # _logger.debug(f'transaction_details: {transaction_details}')

    transaction_directives = []
    addresses = transactions.keys()
    for address in addresses:

        details = transaction_details[address]
        # Post transactions in chronological order. Esplora gives us reverse-chronological order
        details.reverse()   

        for detail in details:

            # Create a beancount transaction for each transaction.
            # Then add beancount transaction entries for each payee/output that is not one of the user's addresses.

                ''' E.g. 
                2014-07-11 * "Sold shares of S&P 500"
                  Assets:ETrade:IVV               -10 IVV {183.07 USD} @ 197.90 USD
                  Assets:ETrade:Cash          1979.90 USD
                  Income:ETrade:CapitalGains
                '''
                meta = '' 
                date = detail.timestamp.date()
                flag = '*'
                payees = get_payees(transactions_by_hash[detail.hash])
                if not detail.is_input:
                    payees_in_descriptor = filter(lambda payee: payee.address in addresses, payees)
                    payees = list(payees_in_descriptor)

                tags = [] 
                links = []

                # Should a payee posting use the output address as a subaccount?
                # Each payee is a transaction
                # If not is_input put our receiving transactions first.
                for payee in payees:
                    transaction_directive = f'{date} * "{payee.address}" "Transaction hash: {detail.hash}"'

                    btc_payee_transaction_directive = f'\t{btc_account}\t{"-" if detail.is_input else ""}{payee.amount * 1e-8 : .8f} BTC' 

                    transaction_fiat_amount = detail.twap * payee.amount * 1e-8
                    if not detail.is_input:
                        btc_payee_transaction_directive += f' {{{detail.twap : .2f} {currency} }}' 
                    if detail.is_input: 
                        btc_payee_transaction_directive += f' @ {detail.twap : .2f} {currency}\t' 
                    fiat_payee_transaction_directive = (f'\t{fiat_account}\t{"-" if not detail.is_input else ""}' 
                            + f'{transaction_fiat_amount : .2f} {currency}\t')

                    payee_transaction_directive = btc_payee_transaction_directive
                    payee_transaction_directive += '\n'
                    payee_transaction_directive += fiat_payee_transaction_directive

                    transaction_directive += '\n'
                    transaction_directive += payee_transaction_directive
                    transaction_directive += '\n'
                    transaction_directives.append(transaction_directive)

    document = f'{memo}\n\n'
    document += btc_commodity_directive
    document += '\n'
    document += str.join('\n', account_directives)
    document += '\n\n'
    document += str.join('\n', transaction_directives)

    # Validate document
    from beancount import loader
    _, errors, _ = loader.load_string(document)
    if errors:
        _logger.error(f'---{len(errors)} Errors in the generated beancount file---')
        for i, error in enumerate(errors):
            _logger.error(f'{i}: {error}')
            _logger.error('--')
        _logger.error('---End of errors in beancount file---')

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
        data = ''
        for path in self.paths:
            data += path + '/'
        data = data[:len(data) - 1]
        return f'[{self.fingerprint}]{data}'

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

async def make_beancount_file_for(
    descriptor: Descriptor, 
    currency:   str, 
    network:    bdk.Network,
    spotbit:    Spotbit):

    parsed_descriptor = ParsedDescriptor(descriptor)
    _logger.debug(f'{parsed_descriptor=}')

    config  =  bdk.DatabaseConfig.MEMORY('')
    esplora = bdk.BlockchainConfig.ESPLORA(
            bdk.EsploraConfig(
                base_url = get_esplora_api(network),
                stop_gap = 100,
                proxy = None,
                timeout_read = 5,
                timeout_write = 5,
                )
            )

    wallet = None
    try:
        wallet = bdk.Wallet(
                descriptor = descriptor,
                change_descriptor = None,   
                network = network,
                database_config = config,
                blockchain_config = esplora
                )

    except bdk.BdkError.Descriptor as e:
        _logger.error(f'Error creating wallet: {e}')
        _logger.debug('Attempting to use descriptor as multipath descriptor.')
        assert parsed_descriptor.change_descriptor
        _logger.debug(f'Initialising wallet with:\n'
                     f'descriptor: {parsed_descriptor.external_descriptor}\n'
                     f'change_descriptor: {parsed_descriptor.change_descriptor}')
        wallet = bdk.Wallet(
                descriptor = str(parsed_descriptor.external_descriptor),
                change_descriptor = str(parsed_descriptor.change_descriptor),   
                network = network,
                database_config = config,
                blockchain_config = esplora
                )

    assert wallet
    _logger.debug(f'wallet.balance: {wallet.get_balance()}')
    _logger.debug(f'wallet.transactions: {wallet.get_transactions()}')

    transactions = {}
    addresses = []
    addresses_to_check = [wallet.get_new_address() for _ in range(_GAP_SIZE)]
    while addresses_to_check:
        _logger.debug(f'Wallet addresses generated:\n\t' +
                    '\n\t'.join(addresses_to_check[:10]) + 
                    f'\n...{len(addresses_to_check[11:])} more...')

        transactions_to_check = await get_transactions(addresses_to_check, network)    
        # _logger.debug(f'transactions_to_check: {transactions_to_check }')
        transactions_found = False
        for address, transactions_for in transactions_to_check.items():
            if transactions_for: transactions_found = True 

        if not transactions_found: break

        transactions.update(transactions_to_check)
        addresses_to_check = [address for address, transactions_for in transactions_to_check.items() if transactions_for]
        addresses.extend(addresses_to_check)
        addresses_to_check = [wallet.get_new_address() for _ in range(_GAP_SIZE)]

    # _logger.debug('---transactions--')
    # _logger.debug(transactions)
    number_of_transactions_found = sum([len(ts) for ts in transactions.values()])
    _logger.debug(f'Number of transactions found: {number_of_transactions_found }')
    if number_of_transactions_found  == 0:
        _logger.info(f'{descriptor} does not have any transactions within a gap size of {_GAP_SIZE}.')
        return

    _logger.debug('Making transaction details.')
    transaction_details = await make_transaction_details(
            transactions = transactions,
            currency     = currency,
            spotbit      = spotbit)

    if not transaction_details:
        raise Exception('No transaction details')

    # _logger.debug(f'transaction_details: {transaction_details}')

    _logger.debug('Making beancount file.')
    beancount_document = make_records(descriptor, 
            transaction_details = transaction_details, 
            transactions        = transactions,
            currency            = currency)

    if not beancount_document:
        raise Exception('The beancountfile was not generated')

    _logger.debug('Writing beancount file.')
    if beancount_document:
        from beancount.scripts import format
        formatted_document = format.align_beancount(beancount_document)
        filename  = format_filename(parsed_descriptor)   # TODO(nochiel)
        assert filename
        _logger.info(f'Writing beancount report to: {filename}')
        with open(filename, mode = 'w') as file:
            file.write(formatted_document)

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
                hierarchy = data[1 : cursor]
                end_fingerprint = hierarchy.find('/')
                self.fingerprint = hierarchy[: end_fingerprint]
                self.account = Account(data[1 : cursor])
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

            _logger.debug(f'{result=}')
            return result

        _logger.debug('Looking for checksum.')
        checksum_index = descriptor.find('#')
        script = descriptor
        checksum = ''
        if checksum_index != -1:
            _logger.debug('Checksum found.')
            script, self.checksum = descriptor.split('#')

        descriptors = parse_script(script)
        _logger.debug(f'{descriptors=}')
        if len(descriptors) == 1: 
            [self.external_descriptor, self.change_descriptor] = descriptors[0], None
        else:
            [self.external_descriptor, self.change_descriptor] = descriptors
        _logger.debug(f'{self.external_descriptor=}')
        _logger.debug(f'{self.change_descriptor=}')

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

def format_filename(descriptor: ParsedDescriptor) -> str:
    # TODO Format this according to BlockchainCommons standards.
    # Ref. https://github.com/BlockchainCommons/Research/blob/master/Investigation/Files.md
    # 'Seed Id - Key ID - HDKey from Seed Name - Type - [Master Fingprint _ Descriptor Type _ Account # _  Descriptor Checksum] - Format.filetype'

    result = ''

    # Seed ID — The first 7 digits of the SHA256 digest of the seed.
    seed_id = NotImplemented    # We don't have access to the seed when given a descriptor.

    # Key ID — The first 7 digits of the SHA256 digest of the key.
    key = descriptor.keys[0].paths[0]
    key_id = key[5:13] if key[:4] in ParsedDescriptor.BIP32_PREFIXES else key[:8]            

    # HDKey from Seed Name — The prefix "HDKey from" prepended to randomly created or user-selected name for seed. Space separated.
    from random_username.generate import generate_username
    seedname = f'HDKey from {generate_username()[0]}' 

    document_type = 'Output'

    # Descriptor Type — A textual descriptor of the derivation path, currently: "legacy", "legacymultisig", "nested", "nestedmultisig", "segwit", "segwitmultisig", or "taproot".
    descriptor_type = descriptor.get_address_type().value

    account_number = descriptor.account.get_account_number() if descriptor.account else 0 
    result = (
            f'{key_id}-'
            f'HDKey from {seedname}-'
            f'{document_type}-'
            f'[{descriptor.fingerprint}_{account_number}_{descriptor_type}_{descriptor.checksum}]-'
            'Beancount.txt'
            )

    return result

if __name__ == '__main__':
    
    import typer

    from lib import Network

    def beancount(
            spotbit_url: str,
            descriptor:  Descriptor,
            network:     Network = Network.TESTNET.value,
            currency:    str = 'USD',
            verbose:     bool = False):
        '''
        Generate a beancount file using the transactions found by generating addresses from the bitcoin mainnet descriptor.

        Ref. https://beancount.github.io/docs/trading_with_beancount.html
        '''

        _logger = get_logger(verbose)
        assert _logger

        typer.echo(f'Generating beancount report for descriptor: {descriptor}')
        typer.echo(f'Using currency: {currency}')

        spotbit = Spotbit(spotbit_url)
        import bdkpython as bdk
        bdk_network = bdk.Network[network.value.upper()]

        try:
           _logger.debug('Starting')
           _logger.debug(f'GAP_SIZE: {_GAP_SIZE}')
           result = asyncio.run(
                   make_beancount_file_for(descriptor, currency, bdk_network, spotbit), 
                   # debug = True
                   )
           result = result.result() if result else None
        except Exception as e:
           typer.echo(f'An error occurred while generating a beancount file: {e}')


    typer.run(beancount)






