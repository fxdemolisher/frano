// Copyright (c) 2011 Gennadiy Shafranovich
// Licensed under the MIT license
// see LICENSE file for copying permission.

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
  
  $(".inline-editable").mouseenter(function() { toggleEditPrompt($(this), ".inline-editable-prompt", true); });
  $(".inline-editable").mouseleave(function() { toggleEditPrompt($(this), ".inline-editable-prompt", false); });
  $(".inline-editable").click(function() { toggleEditPrompt($(this), ".inline-editable-prompt", false); });
  
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

function toggleEditPrompt(holder, promptClass,  state) {
  var prompt = holder.siblings(promptClass);
  if(holder.children('form').length == 0 && state) {
    prompt.css("visibility", "visible");
  } else {
    prompt.css("visibility", "hidden");
  }
}

function valueToFloat(selector, defaultValue) {
  var out = parseFloat($(selector).val());
  return (isNaN(out) ? defaultValue : out);
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

function trim(str) {
  return str.replace(/^[ \u00A0]*((?:.|[\n])*?)[ \u00A0]*$/gi, '$1');
}