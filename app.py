import enum
class Network(enum.Enum):
    BITCOIN = 'bitcoin'
    TESTNET = 'testnet'
    SIGNET  = 'signet'
    REGTEST = 'regtest'
    
if __name__ == '__main__':

    import typer

    import server

    def make_cli(logger):

        import beancounter
        beancounter.logger = logger

        cli = typer.Typer()

        @cli.command()
        def run():

            import uvicorn

            assert logger
            typer.echo(f'server.app.debug: {server.app.debug}')
            uvicorn.run('server:app', 
                    host ='::', 
                    port = 5000, 
                    debug = server.settings.debug,
                    log_level = 'debug' if server.settings.debug else 'info',     # TODO(nochiel) TEST
                    reload = True,
                    reload_includes = ['spotbit.config']  # FIXME(nochiel) Does nothing? 
                    )

        default_exchange_id = list(server.supported_exchanges.keys())[0]
        default_currency    = server.settings.currencies[0]
        @cli.command()
        def beancount(descriptor: beancounter.Descriptor,
                network:  Network = Network.TESTNET.value,
                exchange: server.ExchangeName = default_exchange_id,
                currency: server.CurrencyName = default_currency):
            '''
            Generate a beancount file using the transactions found by generating addresses from the bitcoin mainnet descriptor.

            Ref. https://beancount.github.io/docs/trading_with_beancount.html
            '''

            typer.echo(f'Generating beancount report for descriptor: {descriptor}')
            typer.echo(f'Using currency: {currency}')
            typer.echo(f'Using exchange: {exchange}')

            import bdkpython as bdk
            bdk_network = bdk.Network.TESTNET
            match network:
                case Network.BITCOIN:
                    bdk_network = bdk.Network.BITCOIN
                case Network.TESTNET:
                    bdk_network = bdk.Network.TESTNET
            try:
               beancounter.make_beancount_from_descriptor(descriptor = descriptor, 
                       exchange = exchange, 
                       currency = currency, 
                       network  = bdk_network)
            except Exception as e:
               typer.echo(f'An error occurred while generating a beancount file: {e}')


        return cli

    cli = make_cli(server.logger)
    assert cli
    cli()
