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
  
  $("div[id^=deletePortfolio_]").click(function() {
    var id = $(this).attr('id').substring('deletePortfolio_'.length)
    location.href = "/deletePortfolio.html?id=" + id;
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
  
  $("div[id^=deleteTransaction_]").click(function() {
    var id = $(this).attr('id').substring('deleteTransaction_'.length)
    location.href = "/deleteTransaction.html?id=" + id;
  });
    
});