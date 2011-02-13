// Copyright (c) 2010 Gennadiy Shafranovich
// Licensed under the MIT license
// see LICENSE file for copying permission.

$(function() {
  
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
  
});