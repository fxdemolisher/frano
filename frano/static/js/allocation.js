// Copyright (c) 2011 Gennadiy Shafranovich
// Licensed under the MIT license
// see LICENSE file for copying permission.

$(function() {
  
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
    newRow.find(".finalAllocation").val("0.00");
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
        updateAllocationCharts();
      });
    }
  });
  
  $(".allocationTable .finalAllocation").live("change", function(e) {
    totalMarketValue = 0;
    $(".allocationTable TBODY TR").each(function (index, domObj) {
      var obj = $(domObj);
      var symbol = obj.find(".tickerSymbol").html();
      if(symbol == null) {
        symbol = obj.find(".symbol").val();
      }
      
      if(symbol != null && symbol != '') {
        var price = $.parseNumber(obj.find(".price").html(), {format:"$#,##0.00", locale:"us"});
        var quantity = $.parseNumber(obj.find(".quantity").html(), {format:"#,##0.00", locale:"us"});
        quantity += parseFloat(obj.find(".buy INPUT").val());
        quantity -= parseFloat(obj.find(".sell INPUT").val());
        
        totalMarketValue += quantity * price;
      }
    });
    
    var row = $(this).parents("TR")
    var price = $.parseNumber(row.find(".price").html(), {format:"$#,##0.00", locale:"us"});
    var quantity = $.parseNumber(row.find(".quantity").html(), {format:"#,##0.00", locale:"us"});
    var currentMarketValue = quantity * price;
    var requestedMarketValue = totalMarketValue * (parseFloat($(this).val()) / 100);
    
    if(requestedMarketValue < currentMarketValue) {
      var sellQuantity = Math.ceil((currentMarketValue - requestedMarketValue) / price);
      row.find(".buy INPUT").val('0.00');
      row.find(".sell INPUT").val(sellQuantity.toFixed(2));
    } else {
      var buyQuantity = Math.floor((requestedMarketValue - currentMarketValue) / price);
      row.find(".buy INPUT").val(buyQuantity.toFixed(2));
      row.find(".sell INPUT").val('0.00');
    }
    
    refreshAllocation();
    updateAllocationCharts();
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
  
  $(".resetAllocationButton").click(function (e) {
    e.preventDefault();
    resetAllocation();
    refreshAllocation();
    updateAllocationCharts();
  });
  
});

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
    current.row.find(".finalAllocation").val($.formatNumber(finalAllocation * 100, {format:"#0.00", locale:"us"}));
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
      finalData[finalData.length] = { label: symbol, data: $.parseNumber(obj.find(".finalAllocation").val(), {format:"#0.00", locale:"us"}) * 100 };
    }
  });
  
  
  initializeAllocationPieChart($("#currentAllocationChart"), data, 0.00, "Current Allocation");
  initializeAllocationPieChart($("#finalAllocationChart"), finalData, 0.00, "Final Allocation");
}

function resetAllocation() {
  $(".cashIn").val('0')
  $(".cashOut").val('0')
  
  var firstNewRow = true;
  $(".allocationTable TBODY TR").each(function (index, domObj) {
    var obj = $(domObj);
    var symbolField = obj.find(".symbol");
    if (symbolField.length == 1) {
      if(firstNewRow) {
        firstNewRow = false;
        symbolField.val('');
        obj.find(".price, .finalMarketValue").html("$0.00")
        obj.find(".finalAllocation").val("0.00")
      } else {
        obj.remove();
        return;
      }
    }
    
    obj.find(".buy INPUT").val('0.00');
    obj.find(".sell INPUT").val('0.00');
  });

}