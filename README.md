# netatmo-display
Weather display for Netatmo weather station using Raspberry Pi

App is typically started from a script, e.g:

''' 
#!/bin/bash

export PYTHONPATH=$PYTHONPATH:<PathToZeroSeg>

python NetatmoWeatherDisplay.py --username <username> --password <password> --client_id <client_id> --client_secret <client_secret>

'''
