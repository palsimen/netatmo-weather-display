import argparse
import logging
import time

import ZeroSeg.led as led

from NetatmoAccess import NetatmoAccess

NAME = "NetatmoWeatherDisplay.py"
UPDATE_INTERVAL = 60

log = logging.getLogger(NAME)

parser = argparse.ArgumentParser(description=NAME)
parser.add_argument('--username',      help='username',      required=True)
parser.add_argument('--password',      help='password',      required=True)
parser.add_argument('--client_id',     help='client_id',     required=True)
parser.add_argument('--client_secret', help='client_secret', required=True)
parser.add_argument('--nodisplay',     help='run system without zero seg display', action='store_true')
parser.add_argument('--debug',         help='enable debug logging')

args = parser.parse_args()

if args.debug:
    logging.basicConfig(level=logging.DEBUG)
else:
    logging.basicConfig(level=logging.ERROR)

netatmo = NetatmoAccess(username=args.username,
                        password=args.password,
                        client_id=args.client_id,
                        client_secret=args.client_secret)  

if not args.nodisplay:
    display = led.sevensegment()

while True:
    netatmo.update()
    try:
        indoor = netatmo.get('Indoor')
        outdoor = netatmo.get('Outdoor')

        # Create 8 char display text
        indoor_temp = indoor['Temperature']
        outdoor_temp = outdoor['Temperature']
        indoor_temp_round = str(int(round(indoor_temp)))
        outdoor_temp_round = str(int(round(outdoor_temp)))
        weather_summary = '{:4}'.format(indoor_temp_round) + '{:>4}'.format(outdoor_temp_round)

        # Display in terminal
        if args.nodisplay:
            print weather_summary
        # Display on zero seg
        else:
            log.debug('Updating zero seg')
            display.clear()
            display.write_text(0, weather_summary)

    except KeyError, error:
        print 'Could not find module name. Error:', error

    time.sleep(UPDATE_INTERVAL)
