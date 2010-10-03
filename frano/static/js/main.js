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
  
  $("#createPortfolioForm").validationEngine({ promptPosition: 'centerRight' });
  $("#recoverPortfolioForm").validationEngine({ promptPosition: 'centerRight' });
  
  $("label.infield").inFieldLabels();
    
  $("#type").change(function() {
    var val = $(this).val();
    var objs = $("#symbol, #quantity, #price");
    var labels = objs.siblings('label')
    if(val == 'DEPOSIT' || val == 'WITHDRAW' || val == 'ADJUST') {
      objs.attr("disabled", "disabled").val("");
      labels.hide();
    } else {
      objs.attr("disabled", "");
      labels.show();
    }
  });
  
  $("input#as_of_date").datepicker({
    constrainInput: true,
    maxDate: 0
  });
  
  $("#addTransaction").click(function() {
    var type = $("#type").val();
    if(type == 'DEPOSIT' || type == 'WITHDRAW' || type == 'ADJUST') {
      $("#symbol").val("*CASH").attr("disabled", "");
      $("#quantity").val($("#total").val()).attr("disabled", "");
      $("#price").val("1").attr("disabled", "");
    }
    
    $('#addTransactionForm').submit();
  });
  
  $("#addTransactionForm").validationEngine({ });
   
});

function scanForBannerMessages() {
  var msg = $('.message').first()
  if(msg.length > 0) {
    $("#banner").html(msg.html() + "[need a close button]");
    $("#banner").fadeIn();
    msg.remove();
  }
}