import argparse
import logging
import pprint

from NetatmoAccess import NetatmoAccess

name = "WeatherDisplay.py"

pp = pprint.PrettyPrinter()

logging.basicConfig(level=logging.DEBUG)
log = logging.getLogger(name)

parser = argparse.ArgumentParser(description=name)
parser.add_argument('--username',      help='username',      required=True)
parser.add_argument('--password',      help='password',      required=True)
parser.add_argument('--client_id',     help='client_id',     required=True)
parser.add_argument('--client_secret', help='client_secret', required=True)

args = parser.parse_args()



netatmo = NetatmoAccess(username=args.username,
                   password=args.password,
                   client_id=args.client_id,
                   client_secret=args.client_secret)  
netatmo.update()
try:
    data = netatmo.get('Outdoor module')
    pp.pprint(data)
    data = netatmo.get('Outdoo module')
    pp.pprint(data)
except KeyError, error:
    print 'Could not find module name. Error:', error
