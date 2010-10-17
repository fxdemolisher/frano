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
  
  $("label.infield").inFieldLabels({ fadeOpacity: .1, finalOpacity: 0.5 });
    
  $("#type").change(function() {
    var val = $(this).val();
    var objs = $("#symbol, #price, #comission");
    var labels = objs.siblings('label')
    if(val == 'DEPOSIT' || val == 'WITHDRAW' || val == 'ADJUST') {
      objs.attr("disabled", "disabled").val("");
      labels.hide();
    } else {
      objs.attr("disabled", "");
      labels.show();
    }
  });
  
  $("#addTransactionForm input").keypress(function(e) {
    if(e.keyCode == 13) {
      e.preventDefault()
      $("#addTransactionForm").submit();
    }
  });
  
  $("#addTransaction").click(function () {
    $("#addTransactionForm").submit();
  });
  
  $("#addTransactionForm").submit(function() {
    var type = $("#type").val();
    if(type == 'DEPOSIT' || type == 'WITHDRAW' || type == 'ADJUST') {
      $("#symbol").val("*CASH").attr("disabled", "");
      $("#price").val("1").attr("disabled", "");
    }
  });
  
  $("#addTransactionForm").validationEngine({
    inlineValidation: false
  });
  
  $("#deleteTransaction").click(function (e) {
    if(!confirm('Are you sure you wish to remove this transaction?')) {
      e.preventDefault();
    }
  });
  
  $("#portfolioForm").validationEngine({
    inlineValidation: false
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