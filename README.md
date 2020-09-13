# Blockchain Commons Spotbit

**Spotbit** is a portable Flask API for Bitcoin price data and candles. Spotbit can aggregate data from over 100 exchanges and serve them from a single url or onion hidden service. The user can curate the list of exchanges and fiat currencies that the API will store data for, and decide how much data history to keep in storage. Users may choose to run their own local service, or simply connect to another user's already running service. Spotbit can be easily used with Tor and served as a hidden service.

## Additional Information

* At this stage, Spotbit relies on the CCXT library for API calls. In the future, some exchanges will have websocket support as well to increase the amount and accuracy of the data recieved.

## Status - Late Alpha

Spotbit is currently under active development and in the late alpha testing phase. It should not be used for production tasks until it has had further testing and auditing.

### Installation and Usage

#### Script Install
The latest version of Spotbit includes a script called `install.sh` for installing Spotbit and configuring Tor on the system. Run `chmod +x install.sh` inside the Spotbit directory before running the script. The script must be run as root; it will exit if the current user does not run it with `sudo`. 

`install.sh` will set up your system to run spotbit. First, it checks if Python3.8 is being used on your system. Many linux distributions use an older version of python by default that will need to be upgraded. The installer will download, compile and install python3.8 for you.

Then the installer will install the required python3 libraries via pip. These are `ccxt` and `flask`. 

After that, the installer will install and setup tor on your system, then create a user named `spotbit` that controls the hidden service directory location at `/var/lib/tor/Spotbit`. The source code will be copied to `/home/spotbit/source`, and the config file will be copied to `/home/spotbit/.spotbit/spotbit.config`. This is the location where configuration settings will be read from when spotbit runs. Finally, a systemd service will be copied to `/etc/systemd/system`. 

The install script will set up a hidden service for you then show you the link after creating it. You can view this link anytime by looking at the file `/var/lib/tor/Spotbit/hostname` as root. You do not need to use Spotbit over tor. Note: you do not need to specify the port number in the address bar if you are using Tor. 

#### Running Spotbit
To run the server, run `sudo systemctl start spotbit`. Spotbit will then start making http GET requests to all the exchanges you list in the config file. Over 100 exchanges are supported. The Flask server runs over port 5000. There are currently three API routes you can use:

* `/status`
    - Returns a string message if the server is running
* `/now/<currency>/<exchange>`
    - Returns the latest candle for BTC/currency (if supported by the exchange API), or the latest spot price. 
    - currency is a three letter fiat currency (e.g. USD, JPY, etc)
    - exchange is the name of an exchange supported by CCXT. If the exchange is already in the config file, then the newest row from your local database is returned. If the exchange is not supported, then Spotbit will directly request this exchange and return data but it will not be stored locally.
    - Example response:
    ```
    {"close":10314.06,"currency_pair":"BTC-USD","datetime":"2020-09-13 14:31:00","high":10315.65,"id":122983,"low":10314.06,"open":10315.65,"timestamp":1600007460000,"vol":3.53308926}
    ```
* `/now/<currency>`
    - Similar to above, but when the user does not specify a specific exchange (e.g. `/now/USD`)
    - Spotbit will return an average value of the latest data from each exchange in the list. All values will be no older than 15 minutes from present.
    - If no data are present for any exchange, then spotbit will try to make a direct request to that exchange. If that fails, then that exchange will be excluded from the average value.
    - In the response json, there will be a list called `failed_exchanges` showing which exchanges had to be excluded.
    - Example response:
    ```
    {"close":10320.4375,"currency_pair":"BTC-USD","datetime":"Sun, 13 Sep 2020 14:39:11 GMT","exchanges":["coinbasepro","hitbtc","bitfinex","kraken","bitstamp"],"failed_exchanges":["hitbtc"],"high":10321.0875,"id":"average_value","low":10319.3175,"oldest_timestamp":1600007460000,"open":10320.0875,"timestamp":1600007951358.4841,"volume":2.3988248000000003}
    ```

* `/hist/<currency>/<exchange>/<date_start>/<date_end>`
    - Returns all data in the specified BTC/currency pair between `date_start` and `date_end`.
    - Dates can be passed either as ISO-8601 dates (YYYY-MM-DDTHH:mm:SS) or millisecond timestamps.
    - If the exchange is not present in your config file, then no data is returned.
    - Example response:
* `/configure`
    - Shows the current config settings for this server, including what exchanges and currencies are supported.
    - Example response:
    ```
    {"cached exchanges":["gemini","bitstamp","okcoin","coinbasepro","kraken","cex","bitfinex","acx","bitflyer","liquid","bitbank","zaif"],"currencies":["USD","GBP","JPY","AUD","USDT","BRL","EUR","KRW","ZAR","TRY","USDC","INR","CAD","IDR"],"interval":5,"keepWeeks":5,"on demand exchanges":["acx","aofex","bequant","bibox","bigone","binance","bitbank","bitbay","bitfinex","bitflyer","bitforex","bithumb","bitkk","bitmax","bitstamp","bittrex","bitz","bl3p","bleutrade","braziliex","btcalpha","btcbox","btcmarkets","btctradeua","bw","bybit","bytetrade","cex","chilebit","coinbase","coinbasepro","coincheck","coinegg","coinex","coinfalcon","coinfloor","coinmate","coinone","crex24","currencycom","digifinex","dsx","eterbase","exmo","exx","foxbit","ftx","gateio","gemini","hbtc","hitbtc","hollaex","huobipro","ice3x","independentreserve","indodax","itbit","kraken","kucoin","lakebtc","latoken","lbank","liquid","livecoin","luno","lykke","mercado","oceanex","okcoin","okex","paymium","poloniex","probit","southxchange","stex","surbitcoin","therock","tidebit","tidex","upbit","vbtc","wavesexchange","whitebit","yobit","zaif","zb"],"updated settings?":"no"}
    ```
* `/`
    - Shows a landing page with info about spotbit.

You can check on a spotbit's status at any time by running `sudo systemctl status spotbit`, or take a look at the log file in `/home/spotbit/source/spotbit.log`. 

#### Exchanges Used for Averaging
For each of the listed fiat currencies, there is a list of 5 exchanges that will be used to average data for the `/now/CURRENCY` endpoint. They have been selected based on volume rankings and coinmarketcap's confidence rating. In order to stick with exchanges supported by ccxt, some candidates were excluded (such as btse). These exchanges should all be listed in the `exchanges` field of `spotbit.config` in order to ensure spotbit runs as smoothly as possible. The default config will include these values for you.
* USD
    - coinbasepro
    - hitbtc
    - bitfinex
    - kraken
    - bitstamp
* GBP
    - coinbasepro
    - coinsbank
    - bitstamp
    - kraken
    - cexio
* EUR
    - kraken
    - coinbasepro
    - bitfinex
    - bitstamp
    - indoex
* JPY
    - bitflyer
    - liquid
    - coincheck
    - bitbank
    - zaif
* USDT
    - binance
    - okex
    - huobipro
    - bitmax
    - gateio

#### Test Server
A spotbit instance is currently running at `h6zwwkcivy2hjys6xpinlnz2f74dsmvltzsd4xb42vinhlcaoe7fdeqd.onion`. This instance is on a dedicated server.
Alternatively, you can use our test server at `km3danfmt7aiqylbq5lhyn53zhv2hhbmkr6q5pjc64juiyuxuhcsjwyd.onion`. This server will have the latest bugfixes on it, but may not have 100% uptime. 

#### Config Options
Spotbbit uses a config file located at `/home/spotbit/.spotbit/spotbit.config` to change settings. The allowed fields are:
* `keepWeeks`
    - The number of weeks worth of data to keep in the database for exchanges that you are not retrieving history for. This setting does not apply to exchanges that have a long term history.
* `exchanges`
    - The exchanges you want to get current data for. They should be supplied as a list of lowercase names separated by spaces. By default, spotbit.config will include the exchanges needed to create averages for you in USD, GBP, EUR, JPY and USDT.
* `currencies`
    - The fiat currencies you want to get data for. They should be supplied as a list of currency codes (eg USD, AUD, CAD, etc) separated by spaces
* `interval`
    - The time in seconds spotbit should wait between making GET requests to API servers. This value should be between 5-15 seconds for best results.
* `exchange_limit`
    - The number of exchanges to allow to be run in one thread, before performance mode is turned on and spotbit distributes exchanges to multiple threads. Set the threshold higher if you want to reduce Spotbit's impact on your system, and lower the threshold if you want Spotbit to run as fast as possible with many exchanges supported. THE MULTITHREADING IS STILL POORLY TESTED AND MAY NOT BEHAVE PROPERLY. OMITTING THIS IS PREFERRED.
* `averaging_time`
    - The time window in hours that Spotbit will consider "current" when calculating an average price. It is useful to set this to at least an hour or so if you are supporting several dozen or more exchanges, because in these situations some exchanges may occasionally fall slightly behind in the request queue, depending on what you have set as your `interval` and `exchange_limit`.
* `historicalExchanges`
    - Exchanges that you want to request past data for in addition to current data. Should be supplied in the same format as the `exchanges` field.
* `historyEnd`
    - A millisecond timestamp that represents the oldest point in history you want to keep in storage.

## Origin, Authors, Copyright & Licenses

Unless otherwise noted (either in this [/README.md](./README.md) or in the file's header comments) the contents of this repository are Copyright © 2020 by Blockchain Commons, LLC, and are [licensed](./LICENSE) under the [spdx:BSD-2-Clause Plus Patent License](https://spdx.org/licenses/BSD-2-Clause-Patent.html).

In most cases, the authors, copyright, and license for each file reside in header comments in the source code. When it does not, we have attempted to attribute it accurately in the table below.

This table below also establishes provenance (repository of origin, permalink, and commit id) for files included from repositories that are outside of this repo. Contributors to these files are listed in the commit history for each repository, first with changes found in the commit history of this repo, then in changes in the commit history of their repo of their origin.

| File      | From                                                         | Commit                                                       | Authors & Copyright (c)                                | License                                                     |
| --------- | ------------------------------------------------------------ | ------------------------------------------------------------ | ------------------------------------------------------ | ----------------------------------------------------------- |
| exception-to-the-rule.c or exception-folder | [https://github.com/community/repo-name/PERMALINK](https://github.com/community/repo-name/PERMALINK) | [https://github.com/community/repo-name/commit/COMMITHASH]() | 2020 Exception Author  | [MIT](https://spdx.org/licenses/MIT)                        |

### Dependencies

To use Spotbit you'll need to use the following tools:

- Python3.8 or higher (some libraries don't work as needed on older versions of Python)
To build  Spotbit you'll need to use the following tools:

- Python3.8 or higher
- Pip
- Flask
- CCXT - ![CryptoCurrency eXchange Tools](https://github.com/ccxt/ccxt)

All of these Python libraries can be installed via pip and Python3.8 can be installed for you in the install script.

### Motivation
Spotbit aims to provide an easy option for aggregating exchange data that does not require the use of a third party data website like Coinmarketcap. These data can be used inside of other apps or for personal use / analysis. Acquiring data across many exchanges can be a pain because normally one would need write slightly different code in order to interact with each API. Additionally, the use of local storage means that data can always be served quickly even while new data are being downloaded. Spotbit runs two separate threads - one with the Flask webserver, and another that makes API requests to exchanges to update the local database.

### Derived from…
This  Spotbit project is either derived from or was inspired by the need of Fully Noded 2 to display realtime price info in-app:

- [FullyNoded 2](https://github.com/BlockchainCommons/FullyNoded-2) — The mobile app for managing a BTC node via Tor, by [Fonta1n3](https://github.com/Fonta1n3).

## Financial Support

Spotbit is a project of [Blockchain Commons](https://www.blockchaincommons.com/). We are proudly a "not-for-profit" social benefit corporation committed to open source & open development. Our work is funded entirely by donations and collaborative partnerships with people like you. Every contribution will be spent on building open tools, technologies, and techniques that sustain and advance blockchain and internet security infrastructure and promote an open web.

To financially support further development of Spotbit and other projects, please consider becoming a Patron of Blockchain Commons through ongoing monthly patronage as a [GitHub Sponsor](https://github.com/sponsors/BlockchainCommons). You can also support Blockchain Commons with bitcoins at our [BTCPay Server](https://btcpay.blockchaincommons.com/).

## Contributing

We encourage public contributions through issues and pull requests! Please review [CONTRIBUTING.md](./CONTRIBUTING.md) for details on our development process. All contributions to this repository require a GPG signed [Contributor License Agreement](./CLA.md).

### Questions & Support

As an open-source, open-development community, Blockchain Commons does not have the resources to provide direct support of our projects. If you have questions or problems, please use this repository's [issues](./issues) feature. Unfortunately, we can not make any promises on response time.

If your company requires support to use our projects, please feel free to contact us directly about options. We may be able to offer you a contract for support from one of our contributors, or we might be able to point you to another entity who can offer the contractual support that you need.

### Credits

The following people directly contributed to this repository. You can add your name here by getting involved. The first step is learning how to contribute from our [CONTRIBUTING.md](./CONTRIBUTING.md) documentation.

| Name              | Role                | Github                                            | Email                                 | GPG Fingerprint                                    |
| ----------------- | ------------------- | ------------------------------------------------- | ------------------------------------- | -------------------------------------------------- |
| Christopher Allen | Principal Architect | [@ChristopherA](https://github.com/ChristopherA) | \<ChristopherA@LifeWithAlacrity.com\> | FDFE 14A5 4ECB 30FC 5D22  74EF F8D3 6C91 3574 05ED |
| Christian Murray | Lead Developer | [@watersnake1](https://github.com/watersnake1) | \<Christian.B.Murray.21@Dartmouth.edu\> | 9A44 D707 5580 A022 8A99  8CEC 0178 C17E 95C7 BA35 |

## Responsible Disclosure

We want to keep all of our software safe for everyone. If you have discovered a security vulnerability, we appreciate your help in disclosing it to us in a responsible manner. We are unfortunately not able to offer bug bounties at this time.

We do ask that you offer us good faith and use best efforts not to leak information or harm any user, their data, or our developer community. Please give us a reasonable amount of time to fix the issue before you publish it. Do not defraud our users or us in the process of discovery. We promise not to bring legal action against researchers who point out a problem provided they do their best to follow the these guidelines.

### Reporting a Vulnerability

Please report suspected security vulnerabilities in private via email to ChristopherA@BlockchainCommons.com (do not use this email for support). Please do NOT create publicly viewable issues for suspected security vulnerabilities.

The following keys may be used to communicate sensitive information to developers:

| Name              | Fingerprint                                        |
| ----------------- | -------------------------------------------------- |
| Christopher Allen | FDFE 14A5 4ECB 30FC 5D22  74EF F8D3 6C91 3574 05ED |
| Christian Murray |  9A44 D707 5580 A022 8A99  8CEC 0178 C17E 95C7 BA35|

You can import a key by running the following command with that individual’s fingerprint: `gpg --recv-keys "<fingerprint>"` Ensure that you put quotes around fingerprints that contain spaces.
