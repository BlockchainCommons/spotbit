google.charts.load("current", {
  packages: ["corechart", "line"],
});
google.charts.setOnLoadCallback(drawChart);
function drawChart() {
  var data = null;
  data = new google.visualization.DataTable();
  data.addColumn("string", "Date");
  data.addColumn("number", "Value");

  let options = {
    curveType: "function",
    series: { 0: { color: "#e7711b" } },
    color: "#d3362d",
    title: "BTC/USD Price",
    titleTextStyle: {
      color: "white",
    },
    backgroundColor: {
      //                      fill:'#3c4752'
      fill: "white",
    },
    hAxis: {
      //                  format: 'M/d/yy',
      format: "hh:mm",
      gridlines: { count: 15 },
      title: "Date",
      titleTextStyle: {
        color: "#F3F2F1",
      },
    },
    vAxis: {
      title: "Price",
      titleTextStyle: {
        color: "#F3F2F1",
      },
    },
  };
  let chart = new google.visualization.LineChart(
    document.getElementById("chart_div")
  );
  chart.draw(data, options);
  var ex = ["coinbase", "gemini", "kraken", "bitstamp", "bitfinex"];
  for (i = 0; i < ex.length; i++) {
    getPrice(ex[i]);
  }
  setInterval(function () {
    $.ajax({
      url: "proxy.php",
      dataType: "json",
      cache: true,
      success: function (data1) {
        var data2 = JSON.parse("[" + JSON.stringify(data1) + "]");
        var arr = data2[0];
        //                        console.log(arr[0]);
        var b = arr[0];
        //                        console.log(b.close);
        data.addRow([b.datetime, b.close]);
        chart.draw(data, options);
      },
      function(xhr, ajaxOptions, thrownError) {
        alert(xhr.status);
        alert(thrownError);
      },
    });
  }, 10000);
}

//FIX URI REQUEST ENDPOINT
function getPrice(exchange) {
  console.log(exchange);
  $.ajax({
    url: "proxy.php?exchange=" + exchange,
    dataType: "json",
    cache: true,
    success: function (data) {
      var data2 = JSON.parse("[" + JSON.stringify(data) + "]");
      var arr = data2[0];
      console.log(arr[0]);
      var b = arr[0];
      console.log("Exchange:" + exchange + " Price: " + b.close);
      $("#" + exchange).html(b.close);
    },
    function(xhr, ajaxOptions, thrownError) {
      alert(xhr.status);
      alert(thrownError);
    },
  });
}