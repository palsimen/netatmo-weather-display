import argparse
import logging
import time

from NetatmoAccess import NetatmoAccess

NAME = "NetatmoWeatherDisplay.py"
UPDATE_INTERVAL = 5

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

while True:
    netatmo.update()
    try:
        indoor = netatmo.get('Indoor')
        outdoor = netatmo.get('Outdoor module')

        # Display in terminal
        if args.nodisplay:
            print "Inne: " + str(indoor['Temperature'])
            print "Ute: " + str(outdoor['Temperature'])
        # Display on zero seg
        else:
            print "Zero seg"

    except KeyError, error:
        print 'Could not find module name. Error:', error

    time.sleep(UPDATE_INTERVAL)
