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


        cli = typer.Typer()

        @cli.command()
        def run():

            import uvicorn

            assert logger
            logger.info(f'debug: {server.app.debug}')
            uvicorn.run('server:app', 
                    host ='127.0.0.1',
                    port = 5000, 
                    debug = server.settings.debug,
                    log_level = 'debug' if server.settings.debug else 'info',
                    reload = server.settings.debug,
                    reload_includes = ['spotbit.config']  # FIXME(nochiel) Does nothing? 
                    )

        return cli

    cli = make_cli(server.logger)
    assert cli
    cli()
