(function() {
  "use strict";
  function calculateColors() {
    let primaryColor = window.getComputedStyle(document.documentElement).getPropertyValue('--mdc-theme-primary').trim();
    let secondaryColor = window.getComputedStyle(document.documentElement).getPropertyValue('--mdc-theme-secondary').trim();
    let secondaryColor700 = window.getComputedStyle(document.documentElement).getPropertyValue('--mdc-theme-secondary-700').trim();

    // Fallback for IE11, whereby getPropertyValue returns an empty string.
    primaryColor = '' === primaryColor ? '#ffce61' : primaryColor;
    secondaryColor = '' === secondaryColor ? '#f56c2a' : secondaryColor;
    secondaryColor700 = '' === secondaryColor700 ? '#f99a32' : secondaryColor700;
    return {primaryColor, secondaryColor, secondaryColor700};
  }
  function setupDashboardCharts() {

    const themeID = sessionStorage.getItem('crypto-html-theme');
    let chartFontColor = themeID && themeID === 'light-purple-red' ?
      'rgba(0, 0, 0, 0.65)' :
      'rgba(255, 255, 255, 0.45)';
    let colors = calculateColors();
    const snackbar = new mdc.snackbar.MDCSnackbar(document.querySelector('.mdc-snackbar'));
    const walletPriceContainers = document.querySelectorAll('.crypto-wallet__market');
    const walletStatsContainers = document.querySelectorAll('.crypto-wallet__stats');
    const accountBalanceContainer = document.querySelector('.crypto-wallet-overview__balance');


    const coinCurrentPrices = [0, 0, 0];
    const coinWallets = [0.81215, 7.190, 32.730];
    let coinInitialPrices = [0, 0, 0];
    let activeCoinIndex = 0;

    let startTime = new Date().getTime();
    let chartDash = 0;
    let chartCurve = 'smooth';
    let chartTooltipsEnabled = true;
    let options = {
      series: [
        {
          name: "Bitcoin",
          data: []
        }
      ],
      colors: [colors.primaryColor, colors.secondaryColor, colors.secondaryColor700],
      chart: {
        height: 500,
        foreColor: chartFontColor,
        type: 'line',
        speed: 2000,
        animations: {
          easing: 'linear',
          dynamicAnimation: {
            speed: 2000
          }
        },
        toolbar: {
          show: false
        },
        zoom: {
          enabled: false
        }
      },
      grid: {
        borderColor: chartFontColor,
      },
      markers: {
        size: 3,
        opacity: 0.4,
        colors: [colors.primaryColor, colors.secondaryColor, colors.secondaryColor700],
        strokeColor: '#fff',
        strokeWidth: 1,
        style: 'inverted', // full, hollow, inverted
        hover: {
          size: 5,
        }
      },
      dataLabels: {
        enabled: false
      },
      stroke: {
        curve: chartCurve,
        width: 2,
        dashArray: chartDash
      },
      xaxis: {
        range: 28,
        tickAmount: 14,
        axisBorder: {
          show: true,
          color: 'rgba(255, 255, 255, 0.1)',
        },
        labels: {
          formatter: function(value, timestamp) {
            return new Date(startTime +  Math.floor(timestamp) * 1000).toLocaleTimeString();
          }
        }
      },
      legend: {
        show: true
      },
      tooltip: {
        x: {
          show: false,
          formatter: function(index) {
            return new Date(startTime + index * 1000).toLocaleTimeString();
          }
        },
        enabled: chartTooltipsEnabled,
        fillSeriesColor: true,
      }
    }
    let chart = new ApexCharts(
      document.querySelector('#wallets-performance-chart'),
      options
    );
//jev    chart.render();

    const products = [{
      id: 'BTC-USD',
      label: 'Bitcoin'
    }, {
      id: 'ETH-USD',
      label: 'Ethereum'
    }, {
      id: 'LTC-USD',
      label: 'Litecoin'
    }];

    const subscribe = {
      type: 'subscribe',
      channels: [
        {
          name: 'ticker',
          product_ids: products.map(product => product.id)
        }
      ]
    };

    const ws = new WebSocket('wss://ws-feed.gdax.com');
    ws.onopen = () => {
      ws.send(JSON.stringify(subscribe));
    };

    let lastUpdate = 0;
    ws.onmessage = (e) => {
      const value = JSON.parse(e.data);
      if (value.type !== 'ticker') {
        return;
      }


      const index = products.findIndex(product => product.id === value.product_id);
      if (index !== -1) {
        let now = new Date().getTime();
        let price = parseFloat(value.price);
        coinCurrentPrices[index] = price;
        if (!coinInitialPrices[index]) {
          coinInitialPrices[index] = price;
        }
        updateWallets();
        updateAccountBalance();

        // add dummy bitcoin data on init, based on initial price
        if (lastUpdate === 0) {
//jev          randomizeInitialData(price);
        }

        if (index === activeCoinIndex && now - lastUpdate > 10000) {
          lastUpdate = now;
          snackbar.show({
            message: products[index].label + ' price updated'
          });
        }
      }
    };

/*    window.setInterval(function () {
      chart.appendData([{
JEV       data: [coinCurrentPrices[activeCoinIndex]]
      }]);
      updateAxisBoundaries();
    }, 2000);
*/
    let maxBoundary = 0;
    let minBoundary = 0;
    function updateAxisBoundaries() {
      let values = chart.opts.series[0].data.slice(-28);
      let maxPrice = Math.max.apply(null, values);
      let minPrice = Math.min.apply(null, values);

      if (maxPrice > maxBoundary || minPrice < minBoundary ||
          minPrice - minBoundary > 2 || maxBoundary - maxPrice > 2) {
        maxBoundary = maxPrice + 2;
        minBoundary = minPrice - 2;
        chart.updateOptions({
          yaxis: {
            min: minBoundary,
            max: maxBoundary
          }
        }, false, true, false)
      }
    }

    function updateWallets() {
      walletPriceContainers.forEach(function(container, index){
        container.innerText = '$' + coinCurrentPrices[index];
      })

      walletStatsContainers.forEach(function(container, index){
        const stat = coinInitialPrices[index] ?
          (coinCurrentPrices[index] - coinInitialPrices[index]) / coinInitialPrices[index] * 100
          : 0.00;
        container.innerText = stat.toFixed(2) + '%';

        const statsClass = stat >= 0 ? 'crypto-wallet__stats--up' : 'crypto-wallet__stats--down';
        container.classList.remove('crypto-wallet__stats--up', 'crypto-wallet__stats--down');
        container.classList.add(statsClass);
      });
    }

    function updateAccountBalance() {
      const balance = coinCurrentPrices[0] * coinWallets[0] +
                      coinCurrentPrices[1] * coinWallets[1] +
                      coinCurrentPrices[2] * coinWallets[2];

//jev      accountBalanceContainer.innerText = balance.toFixed(2);
    }

    function randomizeInitialData(price) {
      let randoms = [];
      for(let i=0;i<14;i++){
        randoms.push(Math.floor(Math.random() * 4) + (price - 2));
      }

      chart.appendData([{
          data: randoms
      }]);
    }

    const coinChartActions = document.querySelector('.crypto-widget__actions');
    const coinChartLinks = document.querySelectorAll('.crypto-widget__actions a');
    coinChartActions.addEventListener('click', function(e) {
        coinChartLinks.forEach((item) => {
          item.classList.remove('mdc-button--raised');
        });
        e.target.classList.add('mdc-button--raised');
        activeCoinIndex = Array.prototype.findIndex.call(coinChartLinks, link => link.classList.contains('mdc-button--raised'));
        e.preventDefault();
    }, false)

    // Most invested chart
    let mostInvestedOptions = {
      series: [
        {
          name: 'Bitcoin',
          data: [
            {x: new Date(1533514320000), y: 100},
            {x: new Date(1533600720000), y: 200},
            {x: new Date(1533687120000), y: 400},
            {x: new Date(1533773520000), y: 580},
            {x: new Date(1533859920000), y: 650}
          ]
        }
      ],
      colors: colors.primaryColor,
      chart: {
        height: 170,
        width: '100%',
        foreColor: chartFontColor,
        type: 'area',
        toolbar: {
          show: false
        },
        zoom: {
          enabled: false
        }
      },
      grid: {
        show: false
      },
      markers: {
        size: 3,
        opacity: 0.4,
        colors: 'transparent',
        strokeColor: colors.primaryColor,
        strokeWidth: 2,
        style: 'inverted', // full, hollow, inverted
        hover: {
          size: 3,
        }
      },
      dataLabels: {
        enabled: false
      },
      stroke: {
        curve: 'straigth',
        width: 2,
      },
      xaxis: {
        type: 'datetime',
        tickAmount: 7,
        axisBorder: {
          show: true,
          color: 'rgba(255, 255, 255, 0.1)',
        },
        tooltip: {
          enabled: false
        },
        labels: {
          datetimeFormatter: {
            day: 'dd/M'
          },
        }
      },
      yaxis: {
        labels: {
          show: false
        }
      },
      tooltip: {
        x: {
          show: false
        },
        y: {
          show: false
        },
        enabled: true,
        fillSeriesColor: true,
      }
    }
    let mostInvestedChart = new ApexCharts(
      document.querySelector('#chart-most-invested'),
      mostInvestedOptions
    );
//jev    mostInvestedChart.render();

    // We need to reload the charts because we switched skin.
    const body = document.getElementsByTagName('body').item(0);
    body.addEventListener('cryptoThemeChanged', () =>
      {
        const themeID = sessionStorage.getItem('crypto-html-theme');
        let chartFontColor = themeID && themeID === 'light-purple-red' ?
          'rgba(0, 0, 0, 0.65)' :
          'rgba(255, 255, 255, 0.45)';
        let colors = calculateColors();

        chart.updateOptions({
          colors: [colors.primaryColor, colors.secondaryColor, colors.secondaryColor700],
          markers: {
            colors : [colors.primaryColor, colors.secondaryColor, colors.secondaryColor700]
          },
          chart: {
            foreColor: chartFontColor
          },
          grid: {
            borderColor: chartFontColor,
          }
        }, false, true, false);

        mostInvestedChart.updateOptions({
          colors: colors.primaryColor,
          markers: {
            strokeColor : colors.primaryColor
          },
          chart: {
            foreColor: chartFontColor
          },
        }, false, true, false);

      }
    );
  } // end of setupDashboardCharts.

  // Wait 1sec before initializing the charts so the switcher CSS works.
  setTimeout(setupDashboardCharts, 1000);

  const tableExpandTogglesContainer = document.querySelector('.crypto-widget__content .mdl-data-table');
  tableExpandTogglesContainer.addEventListener('click', function(e){
    let element = e.target;
    while (element !== e.currentTarget) {
      if (element.classList.contains('crypto-transactions-list__item-toggle')) {
        element.classList.toggle('rotated');
        element.parentNode.parentNode.nextElementSibling.classList.toggle('expanded');
        e.preventDefault();
        return;
      }
      element = element.parentNode;
    }
  });

// //TODO:MISSING HTML MARKUP
//   const menuEl = document.querySelector('#widget-menu');
//   const menu = new mdc.menu.MDCMenu(menuEl);
//   const menuButtonEl = document.querySelector('#menu-button');
//   menuButtonEl.addEventListener('click', function() {
//     menu.open = !menu.open;
//   });
//   menu.setAnchorMargin({left: -60});

  // // Wallet
  // const newWalletDialog = new mdc.dialog.MDCDialog(document.querySelector('.mdc-dialog'));
  // document.querySelector('.crypto-wallet--new').addEventListener('click', function(evt) {
  //   newWalletDialog.lastFocusedTarget = evt.target;
  //   newWalletDialog.show();
  // });

})();
