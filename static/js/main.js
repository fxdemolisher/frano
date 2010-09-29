// Copyright (c) 2010 Gennadiy Shafranovich
// Licensed under the MIT license
// see LICENSE file for copying permission.

$(function() {
  $("#addNewPortfolio").click(function() {
    $("#createNewDialogue, #closeCreateNewDialogue").fadeIn();
    $(this).hide();
  });
  
  $("#closeCreateNewDialogue").click(function() {
    $("#addNewPortfolio").show();
    $("#createNewDialogue, #closeCreateNewDialogue").fadeOut(function() {
      
    });
  });

  $("#itemSelector").click(function() {
    $("#myPortfolios").css("display", "block");
  });
  
  $("#myPortfolios").click(function() {
    var id = $(this).val();
    location.href = "/portfolio.html?id=" + id;
  });
  
  $("#newTransactionType").change(function() {
    var val = $(this).val();
    if(val == 'DEPOSIT' || val == 'WITHDRAW' || val == 'ADJUST') {
      $("#newTransactionSymbol").val("*CASH");
      $("#newTransactionPrice").val("1.00");
    }
  });
  
  $("#addTransaction").click(function() {
    $('#addTransactionForm').submit();
  });
   
});