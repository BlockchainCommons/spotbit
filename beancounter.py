# Ref. https://beancount.github.io/docs/the_double_entry_counting_method.html
# Given a descriptor, generate a beancount file for accounting purposes.
# For each address check what inputs it has received. Put these under income/debits.
# For each address check what outputs it has paid. Put these under expenses/credits.

# Ref. https://github.com/Blockstream/esplora/blob/master/API.md#block-format

# Output descriptors https://github.com/dgpv/miniscript-alloy-spec
# https://github.com/spesmilo/electrum/issues/5694
# https://github.com/petertodd/python-bitcoinlib/issues/235
# https://github.com/bitcoin/bitcoin/pull/17975

_ESPLORA_API = 'https://blockstream.info/testnet/api/'
_GAP_SIZE = 1000    # Make this configurable (set via command line)


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

# Ref. https://github.com/tiangolo/fastapi/issues/1508
import logging
logger = logging.getLogger(__name__)
assert logger
logger.setLevel(logging.DEBUG)

handler = logging.StreamHandler()

formatter = logging.Formatter(
    '[%(asctime)s] %(levelname)s (thread %(thread)d):\t%(module)s.%(funcName)s: %(message)s')

handler.setFormatter(formatter)
logger.addHandler(handler)
logger.debug('starting')
logger.debug(f'_GAP_SIZE: {_GAP_SIZE}')

Descriptor = str
def get_new_wallet_descriptor() -> tuple[bdk.Wallet, Descriptor]:
    key = bdk.generate_extended_key(network = bdk.Network.TESTNET, 
            word_count = bdk.WordCount.WORDS12,
            password = None)

    return NotImplemented

    print(f'key.mnemonic: {key.mnemonic}')
    print(f'key.xprv: {key.xprv}')
    print(f'key.fingerprint: {key.fingerprint}')

    # FINDOUT how to get a descriptor from a key.
    assert descriptor

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
        transactions: list[Transactions]
        ) -> TransactionDetailsForAddresses:

    assert addresses
    assert transactions

    from statistics import mean

    result = {address: [] for address in addresses}

    server = app.app
    # server.config.update({'TESTING': True})

    def get_transaction_details_for(address: str, transactions: Transactions, server = server) -> TransactionDetailsForAddresses:

        logger.debug('')
        assert address
        assert transactions 
        assert len(transactions)

        result = {address: []}
        
        timestamps_to_get = [datetime.fromtimestamp(transaction['status']['block_time'])
                for transaction in transactions]
        timestamps_to_get = [timestamp.isoformat() for timestamp in timestamps_to_get]
    
        assert len(timestamps_to_get)
        client = server.test_client()
        response = client.post('/history/USD/bitstamp', 
                json   = timestamps_to_get)    

        candles = []
        if response.status_code < 400: 
            data = response.json
            logger.debug(f'data: {data}')
            if data:
                candles = [app.Candle(**candle) for candle in data]
                logger.debug(f'candles: {candles}')
        else:         # FIXME Handle HTTPStatus response errors.
            logger.error(f'{response.status}: {response.data}')

        if len(candles):
            assert len(candles) == len(transactions), f'len(candles): {len(candles)}\t len(transactions): {len(transactions)}'
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
                result[address].append(TransactionDetails(
                        timestamp = timestamp,
                        hash = transaction['txid'],
                        is_input = is_input,
                        twap = mean([candle.open, candle.high, candle.low, candle.close])))

        return result

    tasks = []
    for address_index in range(len(transactions)):
        transactions_for  = transactions[address_index]
        if len(transactions_for):
            address = addresses[address_index]
            tasks.append(asyncio.to_thread(get_transaction_details_for, 
                address = address, transactions = transactions_for))

    if len(tasks):
        _transaction_details = await asyncio.gather(*tasks)
        transaction_details = {address: detail 
                for details_for in _transaction_details
                for address, detail in details_for.items()}
        for address in addresses:
            details = transaction_details[address]
            result[address].extend(details)

    return result


def make_records(transaction_details: TransactionDetailsForAddresses, 
        addresses: list[Address], 
        transactions: list[Transactions]
        ) -> str | None:
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
    account_name = 'BTC'
    subaccount_name = ''

    from beancount.core import account

    components = [type.title(), country.title(), institution.title(), account_name, subaccount_name]
    components = [c for c in components if c != '']
    account_name = account.join(*components)
    assert account.is_valid(account_name), f'Account name is not valid. Got: {account_name}'

    # Loop through on-chain transactions and create transactions and relevant postings for each transaction.
    assert(transaction_details)

    transactions_by_hash = {tx['txid'] : tx 
            for for_address in transactions
            for tx in for_address}

    transaction_details_by_hash = {detail.hash : detail
            for _, details_for in transaction_details.items()
            for detail in details_for}

    def get_earliest_blocktime(transactions: list[Transactions] = transactions) -> datetime:
        assert transactions
        assert len(transactions[0])

        result = datetime.fromtimestamp(transactions[0][0]['status']['block_time'])
        for transactions_for in transactions:
            for transaction in transactions_for:
                timestamp = datetime.fromtimestamp(transaction['status']['block_time'])
                result = timestamp if timestamp < result else result

        return result

    date_of_account_open = get_earliest_blocktime().date()
    # e.g. YYYY-MM-DD open Account [ConstraintCurrency,...] ["BookingMethod"]
    account_directive = f'{date_of_account_open} open {account_name}    BTC'


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
    
    def get_payees(
            transaction_hash: str,
            addresses = addresses,
            transactions = transactions_by_hash,
            transaction_details_by_hash = transaction_details_by_hash,
           ) -> list[Payee]:

        assert addresses
        assert transactions
        assert transaction_details_by_hash

        result = []

        tx = transactions[transaction_hash]
        detail = transaction_details_by_hash[transaction_hash]
        assert tx
        assert detail

        payees = None
        outputs = tx['vout']
        result = [Payee(address = output['scriptpubkey_address'], amount = output['value']) 
                for output in outputs]
        if detail.is_input:
            # If user's address was an input, then remove output addresses that belong to user's wallet?
            payees = filter(lambda payee: payee.address not in addresses, 
                    list(result))
        else:
            # If user's utxo was not an input, then remove output addresses that don't belong to the user's wallet.
            # FIXME
            payees = filter(lambda payee: payee.address in addresses, 
                    result)

        result = list(payees) if payees else result
        return result

    assert transaction_details
    transaction_directives = []
    # logger.debug(f'transaction_details: {transaction_details}')

    for address, details in transaction_details.items():

        # Create a beancount transaction for each transaction.
        # Then add beancount transaction entries for each payee/output that is not one of the user's addresses.
        for transaction in details:

            meta = '' 
            date = transaction.timestamp
            flag = '*'

            payees = get_payees(transaction_hash = transaction.hash)

            tags = [] 
            links = []

            transaction_directive = f'{date} * {"Paying" if transaction.is_input else "Receiving"}'
            narration = 'Paying' if transaction.is_input else 'Receiving from' 

            payee_transaction_directives = []
            for payee in payees:
                # FIXME Show amounts in BTC and USD.
                payee_transaction_directive = f'{account_name} {"-" if transaction.is_input else ""}{transaction.twap} USD\t; {narration} {payee.address}' 
                payee_transaction_directives.append(payee_transaction_directive)

            transaction_directive += '\n'
            for directive in payee_transaction_directives:
                transaction_directive += directive
                transaction_directive += '\n'

            transaction_directives.append(transaction_directive)

    document = ''
    document += account_directive
    document += '\n'

    logger.debug(f'Number of transaction_directives: {len(transaction_directives)}')
    if len(transaction_directives):
        document += str.join('\n', transaction_directives)

    # TODO Validate document

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
    logger.debug(f'Number of transactions_details: {sum([len(t) for t in transaction_details])}')

    if not transaction_details:
        raise Exception('no transaction details')

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

    # descriptor = descriptors['test']['pubkey']  

    import blockchaincommons as bc
    descriptor = bc.descriptors['BlockchainCommons']['pubkey']  

    logger.debug(f'testing using descriptor: {descriptor}')
    # asyncio.run(make_beancount_file_for(descriptor,))
    asyncio.run(make_beancount_file_for(descriptor, network = bdk.Network.BITCOIN))  
