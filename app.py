if __name__ == '__main__':

    import typer

    import server

    def make_cli(logger):

        import beancounter

        cli = typer.Typer()

        @cli.command()
        def run():

            import uvicorn

            
            assert logger
            typer.echo(f'app.debug: {app.debug}')
            uvicorn.run('app:app', 
                    host ='::', 
                    port = 5000, 
                    debug = _settings.debug,
                    log_level = 'debug' if _settings.debug else 'info',     # TODO(nochiel) TEST
                    reload = True,
                    reload_includes = ['spotbit.config']  # FIXME(nochiel) Does nothing? # TODO(nochiel) TEST
                    )

        @cli.command()
        def beancount(descriptor: beancounter.Descriptor = 'example'):
            '''
            Generate a beancount file using the transactions found by generating addresses from the bitcoin mainnet descriptor.

           Ref. https://beancount.github.io/docs/trading_with_beancount.html
           '''

            beancounter.logger = logger
            try:
                beancounter.make_beancount_from_descriptor(descriptor)
            except e:
                typer.echo(f'An error occurred while generating a beancount file: {e}')

        return cli

    cli = make_cli(server.logger)
    assert cli
    cli()
