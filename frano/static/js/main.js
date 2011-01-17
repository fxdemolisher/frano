// Copyright (c) 2010 Gennadiy Shafranovich
// Licensed under the MIT license
// see LICENSE file for copying permission.

var symbols = [];

$(function() {
  $("input").attr("autocomplete","off"); 
  
  scanForBannerMessages();
  $("#banner").click(function() {
    $(this).fadeOut();
  })
 
  $("#signIn").click(function(e) {
    e.preventDefault();
    var box = $(".signInBox");
    if(box.css("display") == 'none') {
      box.fadeIn();
    } else {
      box.fadeOut();
    }
  })
  
  $('#symbol').autocomplete({ source: symbols });
    
  var lastTransactionType = 'BUY';
  $(".newTransactionType").change(function() {
    var val = $(this).val();
    var isCash = (val == 'DEPOSIT' || val == 'WITHDRAW' || val == 'ADJUST');
    var wasCash = (lastTransactionType == 'DEPOSIT' || lastTransactionType == 'WITHDRAW' || lastTransactionType == 'ADJUST');
    lastTransactionType = val;
    
    if(isCash != wasCash) {
      if(isCash) {
        $(".securitiesField").attr("disabled", "disabled").val("").css("background-color", "#CCCCCC");
        $(".cashField").attr("disabled", "").filter('[type=text]').val("").css("background-color", "#FFFFFF");
      } else {
        $(".securitiesField").attr("disabled", "").val("").css("background-color", "#FFFFFF");
        $(".cashField").attr("disabled", "disabled").filter('[type=text]').val("").css("background-color", "#CCCCCC");
      }
    }
    
    $(".securitiesField").each(function (idx, obj) { $.validationEngine.closePrompt(obj) });
    $(".cashField").each(function (idx, obj) { $.validationEngine.closePrompt(obj) });
  });
  
  $("#addTransactionForm input").keypress(function(e) {
    if(e.keyCode == 13) {
      e.preventDefault()
      $("#addTransactionForm").submit();
    }
  });
  
  $("#quantity, #price, #comission").change(function() {
    $('#total').val((valueToFloat('#quantity', 0.0) * valueToFloat('#price', 0.0)) + valueToFloat('#comission', 0.0));
  });
  
  $("#addTransaction").click(function () {
    $("#addTransactionForm").submit();
  });
  
  $("#addTransactionForm").submit(function (e) {
    var val = '';
    $(".newTransactionType").each(function (idx, obj) {
      if($(obj).attr("checked")) {
        val = $(obj).val();
      }
    });
    
    var fields;
    if(val == 'DEPOSIT' || val == 'WITHDRAW' || val == 'ADJUST') {
      fields = $(".cashField").filter('[type=text]');
    } else {
      fields = $(".securitiesField");
    }
    
    var valid = true;
    fields.each(function(idx, obj) {
      valid = valid && !$.validationEngine.loadValidation(obj);
    });
    
    if(!valid) {
      e.preventDefault();
    }
  });
  
  $("#priceLookup").click(function() {
    var asOf = new Date($('#as_of_date').val());
    if(asOf.toString() == 'NaN' || asOf.toString() == 'Invalid Date') {
      return;
    }
    
    var symbol = trim($('#symbol').val());
    if(symbol == null || symbol == '') {
      return;
    }
    
    $.getJSON('/priceQuote.json', { day: asOf.getDate(), month: asOf.getMonth() + 1, year: asOf.getFullYear(), symbol: symbol }, function(data, textStatus) {
      if(textStatus == 'success' && data.price > 0) {
        $('#price').val(data.price);
        $('#total').val((valueToFloat('#quantity', 0.0) * valueToFloat('#price', 0.0)) + valueToFloat('#comission', 0.0));
      }
    });
    
  });
  
  $(".deleteTransaction").click(function (e) {
    if(!confirm('Are you sure you want to remove this transaction?')) {
      e.preventDefault();
    }
  });
  
  $(".removeAllTransactions").click(function (e) {
    if(!confirm('Are you sure you want to remove ALL transactions from this portfolio?\nThis action cannot be undone.')) {
      e.preventDefault();
    }
  });
  
  $("#seeAllTransactions A").click(function(e) {
    e.preventDefault();
    $(".transactionRow").show();
    $("#seeAllTransactions").hide();
  });
  
  $(".editable-transaction-field").each(function() {
    var holder = $(this)
    var components = holder.attr("id").substring('edit_'.length).split('_');
    holder.editable(function(value, settings) {
      var params = Object();
      params[components[2]] = value;
      $.post('/' + components[0] + '/' + components[1] + '/' + 'update.json', params, function(data, textStatus) {
        if(data.success == 'True') {
          val = 'Saved';
        } else {
          alert("Something went wrong...sorry");
          val = 'Failed';
        }
        
        holder.editable('disable');
        holder.unbind('click');
        holder.html(val);
        holder.siblings(".inline-editable-prompt").html("refresh to update");
        
      }, 'json');
      
      return "Saving..."
    }, {
      placeholder : '<div style="width:59px;">&nbsp;</div>',
      onblur      : 'submit',
      height      : 17,
      width       : parseInt(components[3]),
      style       : 'display: inline;',
      data        : function(value, settings) {
                      if (value.toLowerCase().indexOf('<div') == 0) {
                        return trim($('<div/>').html(value).text());
                      } else {
                        return value.replace(/[,\$]/gi, '');
                      }
                    }
    });
  });
  
  $(".transactionType").each(function() {
    var holder = $(this)
    var components = holder.attr("id").substring('edit_'.length).split('_');
    holder.editable(function(value, settings) {
      var params = Object();
      $.post('/' + components[0] + '/' + components[1] + '/' + 'update.json', { type : value }, function(data, textStatus) {
        if(data.success == 'True') {
          val = 'Saved';
        } else {
          alert("Something went wrong...sorry");
          val = 'Failed';
        }
        
        holder.editable('disable');
        holder.unbind('click');
        holder.html(val);
        holder.siblings(".inline-editable-prompt").html("refresh to update");
        
      }, 'json');
      
      return "Saving..."
    }, {
      onblur    : 'submit',
      type      : 'select',
      style     : 'display: inline;',
      data      : function (value, settings) {
        if(value == 'BUY' || value == 'SELL') {
          return { 'BUY' : 'Buy Securities', 'SELL' : 'Sell Securities', 'selected' : value };
        } else {
          return { 'DEPOSIT' : 'Deposit Cash', 'WITHDRAW' : 'Withdraw Cash', 'ADJUST' : 'Adjust Cash', 'selected' : value };
        }
      }
    });
  });
  
  $(".inline-editable").mouseenter(function() { toggleEditPrompt($(this), ".inline-editable-prompt", true); });
  $(".inline-editable").mouseleave(function() { toggleEditPrompt($(this), ".inline-editable-prompt", false); });
  $(".inline-editable").click(function() { toggleEditPrompt($(this), ".inline-editable-prompt", false); });
  
  $("#editPortfolioName").click(function(e) {
    e.preventDefault();
    var name = $("SELECT.selectPortfolio :selected").text();
    $("SELECT.selectPortfolio,#editPortfolioName").hide();
    $("#portfolioNameForm").css("display", 'inline');
    $("INPUT.selectPortfolio").val(name).focus();
  });
  
  $("#cancelPortfolioName").click(function (e) {
    e.preventDefault();
    $("#portfolioNameForm").hide();
    $("SELECT.selectPortfolio,#editPortfolioName").show();
  });
  
  $("#setPortfolioName").click(function (e) {
    e.preventDefault();
    var id = $(this).val();
    var value = $("INPUT.selectPortfolio").val();
    $.post('/' + id + '/setName.json', { name : value }, function(data, textStatus) {
      if(data.success != 'True') {
        alert("Something went wrong...sorry");
        return;
      }
      
      var dropdown = $(".selectPortfolio").get(0);
      $(dropdown.options[dropdown.selectedIndex]).html(value);
      
      $("#portfolioNameForm").hide();
      $("SELECT.selectPortfolio,#editPortfolioName").show();
    }, 'json');
  });
  
  var previousSelectedPortfolio;
  $("SELECT.selectPortfolio").focus(function() {
    previousSelectedPortfolio = $(this).val();
  }).change(function () {
    if ($(this).val() == '') {
      location.href = "/?demo=true"
    } else {
      var tester = new RegExp("^(.*/)" + previousSelectedPortfolio + "(/\\w+\\.html)$", "gi");
      if(tester.exec(location.href) != null) {
        location.href = location.href.replace(tester, "$1" + $(this).val() + "$2")
      } else {
        location.href = "/" + $(this).val() + "/positions.html"
      }
    }
  });
  
  $("#deletePortfolio").click(function (e) {
    if(!confirm('Are you sure you want to remove this portfolio?')) {
      e.preventDefault();
    }
  });
  
  $(".showImportRequestForm").click(function(e) {
    e.preventDefault();
    $("#importTransactionsForm").hide();
    $("#requestTransactionsForm").show();
  });
  
  $("#cancelImportRequest").click(function(e) {
    e.preventDefault();
    $("#requestTransactionsForm").hide();
    $("#importTransactionsForm").show();
    
  });
  
  $("#transactionSymbolFilter").change(function() {
    $(this).submit();
  });
  
  $(".showLots").click(function(e) {
    e.preventDefault();
    var myRow = $(this).parents("TR").next(".lotRow");
    var showMyRow = (myRow.css("display") == 'none');
    
    $(".lotRow").hide();
    if(showMyRow) {
      myRow.show();
    }
  })
  
  $(".allocationField, .cashIn, .cashOut").live("focus", function() {
    if (this.value == this.defaultValue) {
      this.select();
    }
  });
  
  $("#allocationAddInstrument").click(function (e) {
    e.preventDefault();
    
    var rows = $(".allocationTable TBODY TR");
    var lastRow = rows.slice(rows.length - 2, rows.length - 1);
    var newRow = lastRow.clone();
    lastRow.after(newRow);
    
    newRow.find(".unknownSymbol").hide();
    newRow.find(".price, .finalMarketValue").html("$0.00");
    newRow.find(".finalAllocation").html("0.00%");
    newRow.find(".allocationField").each(function(index, obj) {
      obj.value = obj.defaultValue;
    });
    
  });
  
  $(".allocationTable .symbol").live("blur", function(e) {
    var obj = $(this);
    var row = obj.parents("TR");
    var symbol = obj.val(obj.val().toUpperCase()).val();
    var unkownSymbol = row.find(".unknownSymbol");

    if(symbol != null && symbol != '') {
      row.find(".spinner").show();
      $.getJSON('/priceQuote.json', { symbol: symbol }, function(data, textStatus) {
        row.find(".spinner").hide();
        
        var price = 0;
        if(textStatus == 'success' && data.price > 0) {
          price = data.price;
          unkownSymbol.hide();
        } else {
          unkownSymbol.show();
        }
        
        row.find(".price").html("$" + price.toFixed(2));
        refreshAllocation();
      });
    }
  });
  
  $(".allocationTable .buy, .allocationTable .sell, .cashIn, .cashOut").live("change", function(e) {
    refreshAllocation();
    updateAllocationCharts();
  });
  
  $(".allocateButton").click(function (e) {
    e.preventDefault();
    allocateEqually();
    refreshAllocation();
    updateAllocationCharts();
  });
  
});

function scanForBannerMessages() {
  var msg = $('.message').first()
  if(msg.length > 0) {
    $("#banner").html(msg.html());
    $("#banner").fadeIn(function() {
      window.setTimeout('$("#banner").fadeOut(1000)',4500);
    });
  }
}

function valueToFloat(selector, defaultValue) {
  var out = parseFloat($(selector).val());
  return (isNaN(out) ? defaultValue : out);
}

function toggleEditPrompt(holder, promptClass,  state) {
  var prompt = holder.siblings(promptClass);
  if(holder.children('form').length == 0 && state) {
    prompt.css("visibility", "visible");
  } else {
    prompt.css("visibility", "hidden");
  }
}

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

function initializeAllocationPieChart(container, data, combineThreshold, chartTitle) {
  var plot = $.plot(container, 
      data, 
      {
        series: {
          pie: { 
            show: true, 
            radius: 0.98,
            label: {
                show: true,
                radius: 0.8,
                formatter: function(label, series) {
                    return '<div style="font-size:8pt;text-align:center;padding:2px;color:white; border: 1px solid #ccc;">'+label+'<br/>'+series.percent.toFixed(2)+'%</div>';
                },
                background: { opacity: 0.5, color: '#666' }
            },
            combine: {
              threshold: combineThreshold
            }
          }
        },
        legend: {
          show: false
        }
      }
    );
  
  if(chartTitle != null && chartTitle != '') {
    container.append('<div style="width:' + plot.width() + 'px;position:absolute;left:0px;top:2px;text-align:center;font-weight:bold;font-size:20px;color:#000;">' + chartTitle + '</div>');
  }
}

function initializeAllocationChart(container) {
  data = []
  for (var i = 0; i < allocation.length; i++) {
    data[i] = { label: allocation[i][0], data: allocation[i][1] }
  }
  
  initializeAllocationPieChart(container, data, 0.05);
}

function refreshAllocation() {
  var data = {}
  $(".allocationTable TBODY TR").each(function (index, domObj) {
    var obj = $(domObj);
    var symbol = obj.find(".tickerSymbol").html();
    if(symbol == null) {
      symbol = obj.find(".symbol").val();
    }
    
    if(symbol != null && symbol != '') {
      data[symbol] = {
          symbol: symbol,
          row: obj,
          originalQuantity: $.parseNumber(obj.find(".quantity").html(), {format:"#,##0.00", locale:"us"}),
          price: $.parseNumber(obj.find(".price").html(), {format:"$#,##0.00", locale:"us"}),
          buyQuantity: parseFloat(obj.find(".buy INPUT").val()),
          sellQuantity: parseFloat(obj.find(".sell INPUT").val())
        };
      
      if(isNaN(data[symbol].buyQuantity)) {
        data[symbol].buyQuantity = 0.0;
        obj.find(".buy INPUT").val('0.00');
      }
      
      if(isNaN(data[symbol].sellQuantity)) {
        data[symbol].sellQuantity = 0.0;
        obj.find(".sell INPUT").val('0.00');
      }
    }
  });
  
  var cashData = data['*CASH'];
  var cashMovement = parseFloat($(".cashIn").val()) - parseFloat($(".cashOut").val());
  var totalMarketValue = 0;
  for(var symbol in data) {
    current = data[symbol];
    current.marketValue = current.originalQuantity * current.price
    
    if(symbol != '*CASH') {
      current.finalQuantity = current.originalQuantity + current.buyQuantity - current.sellQuantity;
      current.finalMarketValue = current.finalQuantity * current.price;
      cashMovement -= current.finalMarketValue - current.marketValue;
      
      totalMarketValue += current.finalMarketValue;
    }
  }
  
  cashData.buyQuantity = (cashMovement > 0 ? cashMovement : 0.0);
  cashData.sellQuantity = (cashMovement < 0 ? 0-cashMovement : 0.0);
  cashData.finalQuantity = cashData.originalQuantity + cashMovement;
  cashData.finalMarketValue = cashData.finalQuantity;
  totalMarketValue += cashData.finalMarketValue
  
  for(var symbol in data) {
    current = data[symbol];
    var finalAllocation = current.finalMarketValue / totalMarketValue;
    current.row.find(".buy INPUT").val(current.buyQuantity.toFixed(2));
    current.row.find(".sell INPUT").val(current.sellQuantity.toFixed(2));
    current.row.find(".finalMarketValue").html($.formatNumber(current.finalMarketValue, {format:"$#,##0.00", locale:"us"}));
    current.row.find(".finalAllocation").html($.formatNumber(finalAllocation, {format:"#0.00%", locale:"us"}));
  }
  
}

function allocateEqually() {
  var data = {}
  $(".allocationTable TBODY TR").each(function (index, domObj) {
    var obj = $(domObj);
    var symbol = obj.find(".tickerSymbol").html();
    if(symbol == null) {
      symbol = obj.find(".symbol").val();
    }
    
    if(symbol != null && symbol != '') {
      data[symbol] = {
          symbol: symbol,
          row: obj,
          price: $.parseNumber(obj.find(".price").html(), {format:"$#,##0.00", locale:"us"}),
          allocation: $.parseNumber(obj.find(".currentAllocation").html(), {format:"#0.00%", locale:"us"})
        };
    }
  });
  
  var cashMovement = parseFloat($(".cashIn").val()) - parseFloat($(".cashOut").val());
  for(var symbol in data) {
    current = data[symbol];
    if(symbol != '*CASH') {
      quantity = (cashMovement * current.allocation) / current.price;
      buyQuantity = (quantity > 0 ? Math.floor(quantity) : 0.0)
      sellQuantity = (quantity < 0 ? Math.ceil(0-quantity) : 0.0)
      current.row.find(".buy INPUT").val(buyQuantity.toFixed(2));
      current.row.find(".sell INPUT").val(sellQuantity.toFixed(2));
    }
  }
}

function updateAllocationCharts() {
  data = []
  finalData = []
  $(".allocationTable TBODY TR").each(function (index, domObj) {
    var obj = $(domObj);
    var symbol = obj.find(".tickerSymbol").html();
    if(symbol == null) {
      symbol = obj.find(".symbol").val();
    }
    
    if(symbol != null && symbol != '') {
      data[data.length] = { label: symbol, data: $.parseNumber(obj.find(".currentAllocation").html(), {format:"#0.00%", locale:"us"}) * 100 };
      finalData[finalData.length] = { label: symbol, data: $.parseNumber(obj.find(".finalAllocation").html(), {format:"#0.00%", locale:"us"}) * 100 };
    }
  });
  
  
  initializeAllocationPieChart($("#currentAllocationChart"), data, 0.00, "Current Allocation");
  initializeAllocationPieChart($("#finalAllocationChart"), finalData, 0.00, "Final Allocation");
}

function trim(str) {
  return str.replace(/^[ \u00A0]*((?:.|[\n])*?)[ \u00A0]*$/gi, '$1');
}