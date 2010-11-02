// Copyright (c) 2010 Gennadiy Shafranovich
// Licensed under the MIT license
// see LICENSE file for copying permission.

$(function() {
  $("input").attr("autocomplete","off"); 
  
  scanForBannerMessages();
  $("#banner").click(function() {
    $(this).fadeOut(function() {
      scanForBannerMessages();
    });
  })
  
  $(".newTransactionType").change(function() {
    var val = $(this).val();
    if(val == 'DEPOSIT' || val == 'WITHDRAW' || val == 'ADJUST') {
      $(".securitiesField").attr("disabled", "disabled").val("");
      $(".cashField").attr("disabled", "").filter('[type=text]').val("");
    } else {
      $(".securitiesField").attr("disabled", "").val("");
      $(".cashField").attr("disabled", "disabled").filter('[type=text]').val("");
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
    var total = (valueToFloat('#quantity', 0.0) * valueToFloat('#price', 0.0)) + valueToFloat('#comission', 0.0);
    $('#total').val(total);
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
    
    var symbol = $('#symbol').val().trim();
    if(symbol == null || symbol == '') {
      return;
    }
    
    $.getJSON('/priceQuote.json', { day: asOf.getDate(), month: asOf.getMonth() + 1, year: asOf.getFullYear(), symbol: symbol }, function(data, textStatus) {
      if(textStatus == 'success' && data.price > 0) {
        $('#price').val(data.price);
      }
    });
    
  });
  
  $("#deleteTransaction").click(function (e) {
    if(!confirm('Are you sure you wish to remove this transaction?')) {
      e.preventDefault();
    }
  });
  
  $(".inline-editable").each(function() {
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
      tooltip   : 'Click to edit...',
      onblur    : 'submit',
      height    : 17,
      width     : parseInt(components[3]),
      style     : 'display: inline;',
      data      : function(value, settings) { return value.replace(/[,\$]/gi, ''); }
    });
  });
  
  $(".inline-editable").mouseenter(function() { toggleEditPrompt($(this), true); });
  $(".inline-editable").mouseleave(function() { toggleEditPrompt($(this), false); });
  $(".inline-editable").click(function() { toggleEditPrompt($(this), false); });
  
  $("#portfolioForm").validationEngine({
    inlineValidation: false,
    scroll: false
  });
  
  $("#portfolio").change(function () {
    if ($(this).val() == '') {
      location.href = "/index.html"
    } else {
      location.href = "/" + $(this).val() + "/positions.html"
    }
  });
  
  $("#deletePortfolio").click(function (e) {
    if(!confirm('Are you sure you wish to remove this portfolio?')) {
      e.preventDefault();
    }
  });
  
});

function scanForBannerMessages() {
  var msg = $('.message').first()
  if(msg.length > 0) {
    $("#banner").html(msg.html() + "[need a close button]");
    $("#banner").fadeIn();
    msg.remove();
  }
}

function valueToFloat(selector, defaultValue) {
  var out = parseFloat($(selector).val());
  return (isNaN(out) ? defaultValue : out);
}

function toggleEditPrompt(holder, state) {
  var prompt = holder.siblings(".inline-editable-prompt");
  if(holder.children('form').length == 0 && state) {
    prompt.css("visibility", "visible");
  } else {
    prompt.css("visibility", "hidden");
  }
}