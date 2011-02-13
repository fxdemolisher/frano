// Copyright (c) 2010 Gennadiy Shafranovich
// Licensed under the MIT license
// see LICENSE file for copying permission.

var symbols = [];

$(function() {
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
  
  $("#transactionSymbolFilter").change(function() {
    $(this).submit();
  });
  
});