// Copyright (c) 2011 Gennadiy Shafranovich
// Licensed under the MIT license
// see LICENSE file for copying permission.

$(function() {
  
  $(".showLots").click(function(e) {
    e.preventDefault();
    var myRow = $(this).parents("TR").next(".lotRow");
    var showMyRow = (myRow.css("display") == 'none');
    
    $(".lotRow").hide();
    if(showMyRow) {
      myRow.show();
    }
  })
  
});

function initializeProfitLossChart(container) {
  var dataPercent = []
  var benchmarkPercent = []
  for(var i = 0; i < performance.length; i++) {
    dataPercent[i] = [ i, performance[i] ]
    benchmarkPercent[i] = [ i, benchmark[i] ]
  }
  
  $.plot(container,
    [ 
      { data: dataPercent, yaxis: 2, label: "Performance %" },
      { data: benchmarkPercent, yaxis: 2, label: 'Benchmark (' + benchmarkSymbol + ')' }
    ],
    {
      series: {
        lines: { show: true }
      },
      xaxis: {
        ticks: dates.length / 7,
        minTickSize: 1,
        tickFormatter: function (value, axis) {
          if(value >= 0 && value < dates.length) {
            return $.datepicker.formatDate('mm/dd', dates[value]);
          }
        }
      },
      y2axis: {
        tickFormatter: function (value, axis) {
          return (value * 100).toFixed(2) + "%";
        }
      },
      grid: {
        backgroundColor: { colors: ["#ffffff", "#eeeeee"] }
      },
      legend: {
        show: true,
        position: 'nw',
        backgroundColor: '#FFFFFF',
        opacity: 0.8
      }
    });
}

function initializeAllocationChart(container) {
  data = []
  for (var i = 0; i < allocation.length; i++) {
    data[i] = { label: allocation[i][0], data: allocation[i][1] }
  }
  
  initializeAllocationPieChart(container, data, 0.05);
}