Backgound Jobs
==============

There are a few background scheduled jobs that are required to run for frano 
to operate correctly.

Price Refresh
-------------

The refresh_quotes management command needs to be executed every 15 minutes 
between the times of 9AM and 5PM, Monday through Friday. The easiest way to
do this is via cron calls to:

python manage.py refresh_quotes

Price History Refresh
---------------------

The historical refresh of prices for all existing quotes should take place 
every four hours, every day. This can be done via cron call to:

python manage.py refresh_price_history

Session Cleanup
---------------

The clean up of django sessions should take place every day at 1AM via a cron
trigger to:

python manage.py cleanup_sessions

Sample Portfolio Cleanup
------------------------

The clean up of sample portfolio older than two weeks should be done every day
at 1AM via a cron trigger to:

python manage.py cleanup_sample_portfolios
