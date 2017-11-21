import argparse
import logging
import time

import ZeroSeg.led as led

from NetatmoAccess import NetatmoAccess

NAME = "NetatmoWeatherDisplay.py"
# Update interval in secs
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
        indoor2 = netatmo.get('Indoor 2')
        outdoor = netatmo.get('Outdoor')

        # Create 8 char display text
        indoor_temp = indoor['Temperature']
        indoor2_temp = indoor2['Temperature']
        outdoor_temp = outdoor['Temperature']
        # Summary
        indoor_temp_round = str(int(round(indoor_temp)))
        outdoor_temp_round = str(int(round(outdoor_temp)))
        summary_display = '{:4}'.format(indoor_temp_round) + '{:>4}'.format(outdoor_temp_round)
        # Indoor
        indoor_display = '{:4}'.format('In') + '{:>4}'.format('{0:.1f}'.format(indoor_temp))
        # Indoor 2
        indoor2_display = '{:4}'.format('In2') + '{:>4}'.format('{0:.1f}'.format(indoor2_temp))
        # Outdoor
        outdoor_display = '{:4}'.format('Out') + '{:>4}'.format('{0:.1f}'.format(outdoor_temp))

        # Display in terminal
        if args.nodisplay:
            print summary_display
            print indoor_display
            print indoor2_display
            print outdoor_display
        # Display on zero seg
        else:
            log.debug('Updating zero seg')
            display.clear()
            display.write_text(0, summary_display)

    except KeyError, error:
        print 'Could not find module name. Error:', error

    time.sleep(UPDATE_INTERVAL)
