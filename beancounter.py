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

_ESPLORA_API = 'https://blockstream.info/testnet/api/'
_GAP_SIZE = 1_024    # Make this configurable (set via command line)


import asyncio
from datetime import datetime
import time

from pydantic import BaseModel
import requests

import app as spotbit

# bdk seems limited. Things I want to be able to do:
# - generate a descriptor from an extended key.
# - test if an address belongs to a HDkey
# - query Esplora or Electrum/Electrs using an agnostic API.
# - load utxo transaction history 
# ref. https://raw.githubusercontent.com/bitcoin/bitcoin/master/doc/descriptors.md

import bdkpython as bdk

logger = spotbit.logger
assert logger
logger.debug('starting')
logger.debug(f'_GAP_SIZE: {_GAP_SIZE}')

Descriptor = str
Address = str
Transactions = list[dict]

async def get_transactions(addresses: list[Address]) -> list[Transactions]:

    result = None

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

    def get_transactions_for(address: str) -> Transactions | None:
        # FIXME Don't include unconfirmed transactions.

        assert address
        # logger.debug(address)

        result = None

        wait = 4
        while wait > 0:

            try:
                request = f'{_ESPLORA_API}/address/{address}/txs'
                response = requests.get(request)
                wait = 0
                if response.status_code == 200:
                    result = response.json()

            except (requests.exceptions.ConnectTimeout, requests.exceptions.ConnectionError) as e:
                logger.debug(f'rate limited on address: {address}')
                wait *= 2
                time.sleep(wait)

        return result

    tasks = [asyncio.to_thread(get_transactions_for, address)
            for address in addresses]

    result = await asyncio.gather(*tasks) if len(tasks) else []
    result = [transactions for transactions in result if transactions is not None]

    # logger.debug(f'result {result}')
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
        addresses, 
        transactions: list[Transactions],
        server = spotbit.app,
        ) -> tuple[TransactionDetailsForAddresses, TransactionDetailsForAddresses]:

    assert addresses
    assert transactions

    from statistics import mean

    receiving_transaction_details = {address: [] for address in addresses}
    sending_transaction_details = {address: [] for address in addresses}

    async def get_transaction_details_for(address: str, transactions: Transactions, server = server) -> tuple[TransactionDetailsForAddresses, TransactionDetailsForAddresses]:

        assert address
        assert transactions 

        receiving = {address: []}
        sending   = {address: []}
        
        timestamps_to_get = [datetime.fromtimestamp(transaction['status']['block_time'])
                for transaction in transactions]
    
        assert len(timestamps_to_get)

        from fastapi.testclient import TestClient
        client = TestClient(server)

        assert spotbit.supported_exchanges
        candles = []
        for exchange in spotbit.supported_exchanges:

            candles = await spotbit.get_candles_at_dates(
                    currency = spotbit.CurrencyName.USD,
                    exchange = spotbit.ExchangeName.BITSTAMP,
                    dates = timestamps_to_get)

            if candles:
                if len(candles) == len(transactions): break

            '''
            response = client.post(f'/history/USD/{exchange}', 
                    json   = timestamps_to_get)    

            if response.ok:

                data = response.json()
                logger.debug(f'data: {data}')
                if data:
                    candles = [spotbit.Candle(**candle) for candle in data]
                    logger.debug(f'candles: {candles}')

                    if len(candles) < len(transactions): continue

                    break
            else:
                logger.error(f'{response.status}: {response.data}')
                continue
            '''

        if candles:
            assert len(candles) == len(transactions), f'Expected: len(transactions): {len(transactions)}\tGot: len(candles): {len(candles)}'
            logger.debug(f'candles: {candles}')
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
                if is_input: 
                    sending[address].append(detail)
                else:
                    receiving[address].append(detail)

        return receiving, sending

    tasks = []
    for address_index in range(len(transactions)):
        transactions_for  = transactions[address_index]
        if len(transactions_for):
            address = addresses[address_index]
            # FIXME(nochiel) Make these multithreaded.
            tasks.append(asyncio.create_task(get_transaction_details_for( 
                address = address, transactions = transactions_for)))


    if tasks:
        transaction_details = await asyncio.gather(*tasks)

        for details_for in [details_for[0] for details_for in transaction_details]:
            for address, details in details_for.items():
                receiving_transaction_details[address].extend(details)

        for details_for in [details_for[1] for details_for in transaction_details]:
            for address, details in details_for.items():
                sending_transaction_details[address].extend(details)

    return receiving_transaction_details, sending_transaction_details

def make_records(transaction_details: tuple[TransactionDetailsForAddresses, TransactionDetailsForAddresses], 
        addresses: list[Address], 
        transactions: list[Transactions]
        ) -> str:

    assert transaction_details
    assert addresses
    assert transactions

    # FIXME I can't use the beancount api to create a data structure that I can then dump to a beancount file.
    # Instead I must emit strings then load the strings to test for correctness.

    # Ref. https://beancount.github.io/docs/beancount_language_syntax.html
    # FINDOUT How to create a collection of entries and dump it to text file.
    # - Create accounts
    # - Create transactions 
    # - Add postings to transactions.
    # - Dump the account to a file.

    # Ref. realization.py
    type = 'Assets'
    country = ''
    institution = ''
    btc_account_name = 'BTC'
    usd_account_name = 'USD'    # TODO(nochiel) The users sets the currency.
    subaccount_name = ''

    from beancount.core import account

    components = [type.title(), country.title(), institution.title(), btc_account_name, subaccount_name]
    components = [c for c in components if c != '']
    btc_account = account.join(*components)
    assert account.is_valid(btc_account), f'Account name is not valid. Got: {btc_account}'

    # Test: Treat cash as a liability.
    # TODO(nochiel) Store the exchange rate at each transaction date.
    components = ['liabilities'.title(), 'Cash', usd_account_name, subaccount_name]
    components = [c for c in components if c != '']
    fiat_account = account.join(*components)
    assert account.is_valid(fiat_account), f'Account name is not valid. Got: {fiat_account}'

    # Loop through on-chain transactions and create transactions and relevant postings for each transaction.

    def get_earliest_blocktime(transactions: list[Transactions] = transactions) -> datetime:
        assert transactions

        result = datetime.now()
        if transactions[0]:
            result = datetime.fromtimestamp(transactions[0][0]['status']['block_time'])

        for transactions_for in transactions:
            if transactions_for:
                for transaction in transactions_for:
                    timestamp = datetime.fromtimestamp(transaction['status']['block_time'])
                    result = timestamp if timestamp < result else result

        return result

    date_of_account_open = get_earliest_blocktime().date()

    # Commodity directive
    '''
    1867-07-01 commodity CAD
      name: "Canadian Dollar"
      asset-class: "cash"
    '''
    btc_commodity_directive = (
'''
2008-10-31 commodity BTC
  name: "Bitcoin"
  asset-class: "cryptocurrency"
'''
)

    # Account directive
    # e.g. YYYY-MM-DD open Account [ConstraintCurrency,...] ["BookingMethod"]
    account_directives = [
            f'{date_of_account_open} open {btc_account}\tBTC',
            f'{date_of_account_open} open {fiat_account}\tUSD',
            ]

    transactions_by_hash = {tx['txid'] : tx 
            for for_address in transactions
            for tx in for_address}

    '''
    transaction_details_by_hash = {detail.hash : detail
            for details_for in transaction_details.values()
            for detail in details_for}

    n_inputs = 0
    for d in transaction_details_by_hash.values():
        if d.is_input: n_inputs += 1 

    logger.debug(f'Number of input txs: {n_inputs}')
    logger.debug(f'Number of all txs: {len(transaction_details_by_hash.values())}')
    '''

    '''
    receiving_transaction_details_by_hash = {}

    for address, details_for in transaction_details.items():
        for detail in details_for:
            if not detail.is_input:
                receiving_transaction_details_by_address[address].extend(transaction_details[address])
    '''

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
    # logger.debug(f'transaction_details: {transaction_details}')

    transaction_directives = []
    # Post income transactions first so that we never post a net-negative amount of btc. that is, the funding transaction should appear first.
    for details_for in transaction_details:
        for address, details in details_for.items():
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
                tags = [] 
                links = []

                # Should a payee posting use the output address as a subaccount?
                # Each payee is a transaction
                # If not is_input put our receiving transactions first.
                payee_transaction_directives = []
                for payee in payees:
                    transaction_directive = f'{date} * "{payee.address}" "Transaction hash: {detail.hash}"'
                    btc_payee_transaction_directive = f'\t{btc_account}\t{"-" if detail.is_input else ""}{round(payee.amount * 1e-8, 8)} BTC' 

                    # TODO(nochiel)  Ref. https://beancount.github.io/docs/how_inventories_work.html#price-vs-cost-basis
                    transaction_fiat_amount = round(detail.twap * payee.amount * 1e-8, 2)
                    if not detail.is_input:
                        btc_payee_transaction_directive += f' {{{detail.twap} USD}}' 
                    if detail.is_input: 
                        btc_payee_transaction_directive += f' @ {detail.twap} USD\t' 
                    fiat_payee_transaction_directive = (f'\t{fiat_account}\t{"-" if not detail.is_input else ""}' 
                            + f'{transaction_fiat_amount} USD\t')

                    payee_transaction_directive = btc_payee_transaction_directive
                    payee_transaction_directive += '\n'
                    payee_transaction_directive += fiat_payee_transaction_directive
                    payee_transaction_directives.append(payee_transaction_directive)

                    transaction_directive += '\n'
                    transaction_directive += str.join('\n', payee_transaction_directives)
                    transaction_directive += '\n'
                    transaction_directives.append(transaction_directive)

    document = ''
    document = btc_commodity_directive
    document += '\n'
    document += str.join('\n', account_directives)
    document += '\n\n'
    document += str.join('\n', transaction_directives)

    # TODO Validate document
    from beancount import loader
    _, errors, _ = loader.load_string(document)
    if errors:
        logger.error(f'---{len(errors)} Errors in the generated beancount file---')
        for error in errors:
            logger.error(error)

    return document

async def make_beancount_file_for(descriptor: Descriptor, network = bdk.Network.TESTNET):

    assert descriptor

    config     = bdk.DatabaseConfig.MEMORY('')

    esplora = bdk.BlockchainConfig.ESPLORA(
            bdk.EsploraConfig(
                base_url = _ESPLORA_API,
                stop_gap = 100,
                proxy = None,
                timeout_read = 5,
                timeout_write = 5,
                )
            )

    wallet = bdk.Wallet(
            descriptor = descriptor,
            change_descriptor = descriptor,
            network = network,
            database_config = config,
            blockchain_config = esplora
            )

    logger.debug(f'wallet.balance: {wallet.get_balance()}')
    logger.debug(f'wallet.transactions: {wallet.get_transactions()}')

    # TODO Verify that I've got all the addresses (including change addresses). 
    # HD wallet address generation should just work. 
    # FINDOUT How do I test with bdk if an address e.g. tb1qu06efjxlj3r880mlnnaz63euuv0cdklthjt87j belongs to this key?
    addresses = [wallet.get_new_address() for i in range(_GAP_SIZE)]
    assert addresses

    transactions = []
    transactions = await get_transactions(addresses)    
    logger.debug(f'Number of transactions: {sum([len(t) for t in transactions])}')

    if len(transactions) == 0:
        logger.info(f'{descriptor} does not have any transactions with gap size of {_GAP_SIZE}.')
        return

    logger.debug('Making transaction details.')
    transaction_details = await make_transaction_details(addresses = addresses, transactions = transactions)
    # logger.debug(transaction_details)

    if not transaction_details:
        raise Exception('no transaction details')

    '''
    for i in range(50):
        address = addresses[i]
        txs_for = transactions[i]
        logger.debug([tx['status']['block_height'] for tx in txs_for])
    '''

    # logger.debug(f'transaction_details: {transaction_details}')

    logger.debug('Making beancount file.')
    beancount_document = make_records(transaction_details = transaction_details, 
            addresses = addresses, transactions = transactions)
    if not beancount_document:
        raise Exception('the beancountfile was not generated')
    if beancount_document:
        with open('spotbit.beancount', mode = 'w') as file:
            file.write(beancount_document)

if __name__ == '__main__':

    descriptors = {
            'bdk':"wpkh(tprv8ZgxMBicQKsPcx5nBGsR63Pe8KnRUqmbJNENAfGftF3yuXoMMoVJJcYeUw5eVkm9WBPjWYt6HMWYJNesB5HaNVBaFc1M6dRjWSYnmewUMYy/84h/1h/0h/0/*)",

            'test': {

                # Using test xpub for large wallet. https://github.com/spesmilo/electrum/issues/6625#issuecomment-724912330
                # Given an xpub, how do I generate a descriptor?
                # Ref. https://bitcoindevkit.org/docs-rs/bdk/nightly/latest/bdk/macro.descriptor.html
                # Ref. https://bitcoin.stackexchange.com/questions/102502/import-multisig-wallet-into-bitcoin-core-vpub-keys-are-not-valid-how-to
                # To convert vpub into wpkh Ref. https://jlopp.github.io/xpub-converter/

                'xpub' : 'vpub5VfkVzoT7qgd5gUKjxgGE2oMJU4zKSktusfLx2NaQCTfSeeSY3S723qXKUZZaJzaF6YaF8nwQgbMTWx54Ugkf4NZvSxdzicENHoLJh96EKg',

                'pubkey': "wpkh(tpubD9hudZxy8Uj3453QrsEbr8KiyXTYC5ExHjJ5sNDVW7yKJ8wc7acKQcpdbvZX6dFerHK6MfVvs78VvGfotjN28yC4ij6nr4uSVhX2qorUV8V/0/*)", 
                'change': "wpkh(tpubD9hudZxy8Uj3453QrsEbr8KiyXTYC5ExHjJ5sNDVW7yKJ8wc7acKQcpdbvZX6dFerHK6MfVvs78VvGfotjN28yC4ij6nr4uSVhX2qorUV8V/1/*)", 
                },

            # TODO Handle multisig descriptors. Don't I need the xpubs for cosigners?

            }

    # FIXME Given an xpub make sure change addresses are also generated.
    # Take _GAP_SIZE depth. Generate 1 key at each depth. 
    # Store each path for which the first key has a transaction.
    # Stop enumerating keys as soon as a transaction is not found at a given depth. 
    # For each valid path, generate _GAP_SIZE keys. Filter out all keys for which there are no transactions.
    # FINDOUT How do I ensure bdk does this automatically? 
    # FINDOUT How does Electrum get all the relevant descriptors when given an xpub? Depth search?

    descriptor = descriptors['test']['pubkey']  
    logger.debug(f'testing using descriptor: {descriptor}')
    asyncio.run(make_beancount_file_for(descriptor,))

    import blockchaincommons as bc
    # descriptor = bc.descriptors['BlockchainCommons']['test']  
    # logger.debug(f'testing using descriptor: {descriptor}')
    # asyncio.run(make_beancount_file_for(descriptor, network = bdk.Network.BITCOIN))  
