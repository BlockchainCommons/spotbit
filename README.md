# Blockchain Commons Spotbit

**Spotbit** is a portable Flask API for Bitcoin price data and candles. Spotbit can aggregate data from over 100 exchanges and serve them from a single url or onion hidden service. The user can curate the list of exchanges and fiat currencies that the API will store data for, and decide how much data history to keep in storage. Users may choose to run their own local service, or simply connect to another user's already running service.

## Additional Information

* At this stage, Spotbit relies on the CCXT library for API calls. In the future, some exchanges will have websocket support as well to increase the amount and accuracy of the data recieved.

## Status - Late Alpha

Spotbit is currently under active development and in the late alpha testing phase. It should not be used for production tasks until it has had further testing and auditing.

### Installation and Usage
Spotbit is still under development, but it is currently working in a very limited sense. If you want to install it, first clone the development github branch. Then, install the required libraries via `pip install <LIBRARY>`. The code works on Linux (tested on Ubuntu 18.04), probably works on Mac, and is not currently supported on Windows. Finally, create a directory called `.spotbit` in your home folder. Copy `spotbit.config` to this directory from the Documentation branch. 

To run the server, run `python3.8 server.py`. Spotbit will then start making http GET requests to all the exchanges you list in the config file. Over 100 exchanges are supported. The Flask server runs over port 5000. There are currently three API routes you can use:
    * `/status`
        - Returns a string message if the server is running
    * `/now/<currency>/<exchange>`
        - Returns the latest candle for BTC/currency (if supported by the exchange API), or the latest spot price. 
        - currency is a three letter fiat currency (e.g. USD, JPY, etc)
        - exchange is the name of an exchange supported by CCXT. If the exchange is already in the config file, then the newest row from your local database is returned. If the exchange is not supported, then Spotbit will directly request this exchange and return data but it will not be stored locally.
    * `/hist/<currency>/<exchange>/<date_start>/<date_end>`
        - Returns all data in the specified BTC/currency pair between `date_start` and `date_end`.
        - Dates can be passed either as ISO-8601 dates (YYYY-MM-DDTHH:mm:SS) or millisecond timestamps.
        - If the exchange is not present in your config file, then no data is returned.

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
- Pip
- Flask
- Celery
- CCXT - ![CryptoCurrency eXchange Tools](https://github.com/ccxt/ccxt)

All of these Python libraries can be installed via pip. 

### Motivation
Spotbit aims to provide an easy option for aggregating exchange data that does not require the use of a third party data website like Coinmarketcap. These data can be used inside of other apps or for personal use / analysis. Acquiring data across many exchanges can be a pain because normally one would need write slightly different code in order to interact with each API. Additionally, the use of local storage means that data can always be served quickly even while new data are being downloaded. Spotbit runs two separate threads - one with the Flask webserver, and another that makes API requests to exchanges to update the local database.

### Derived from…

This  Spotbit project is inspired by the need of Fully Noded 2 to display realtime price info in-app:

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
