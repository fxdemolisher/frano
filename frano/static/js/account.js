// Copyright (c) 2010 Gennadiy Shafranovich
// Licensed under the MIT license
// see LICENSE file for copying permission.

$(function() {
  
  $(".removeMeButton").click(function (e) {
    if(!confirm('Are you sure you want to delete this account?\nNOTE: This cannot be undone, you\'ll have to re-register.')) {
      e.preventDefault();
    }
  });
  
  $(".createPortfolioButton,.setNameButton").click(function (e) {
    e.preventDefault();
    $(this).parents("TR").find("FORM").submit();
  });
  
  $(".portfolioNameForm").submit(function (e) {
    var valid = true;
    $(this).find("INPUT").each(function(idx, obj) {
      valid = valid && !$.validationEngine.loadValidation(obj);
    });
    
    if(!valid) {
      e.preventDefault();
    }
  });
  
  $(".removePortfolioButton").click(function (e) {
    if(!confirm('Are you sure you want to remove this portfolio?\nNOTE: This cannot be undone...sorry.')) {
      e.preventDefault();
    }
  });
  
}