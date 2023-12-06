import argparse
import logging
import time

import ZeroSeg.led as led

from NetatmoAccess import NetatmoAccess

NAME = "NetatmoWeatherDisplay.py"

# Errors
NO_RECENT_DATA_ERROR   = "E0"
NO_CONNECTION_ERROR    = "E1"
DISPLAY_OVERFLOW_ERROR = "E2"
MODULE_NAME_ERROR      = "E2"


# Update interval in secs
UPDATE_INTERVAL = 300
ONE_SECOND = 1
ZERO_SEG_MAX_CHARS = 8
DEVICE_ID = 0
DISPLAY_BRIGHTNESS = 1

log = logging.getLogger(NAME)

def write_display(display, text):
    """
    Function to write to the zero seg display and not use
    a separate char for displaying a '.'.
    """
    dot_pos = []
    # Iterate through text and store position of '.'
    for idx, char in enumerate(text):
        if char == '.':
            dot_pos.append((idx-1-len(dot_pos)))
    # Delete ','
    text = text.replace('.', '')
    if len(text) > ZERO_SEG_MAX_CHARS:
        raise OverflowError('{0} contains too many characters for display'.format(text))

    # Write it to the zero seg display
    for pos, char in enumerate(text.ljust(8)[::-1]):
        dot = False
        if pos in dot_pos:
            dot = True
        display.letter(deviceId=DEVICE_ID, 
                       position=(pos+1), 
                       char=char,
                       dot=dot,
                       redraw=True)
    

parser = argparse.ArgumentParser(description=NAME)
parser.add_argument('--client_id',     help='client_id',     required=True)
parser.add_argument('--client_secret', help='client_secret', required=True)
parser.add_argument('--nodisplay',     help='run system without zero seg display', action='store_true')
parser.add_argument('--debug',         help='enable debug logging', action='store_true')

args = parser.parse_args()

if args.debug:
    logging.basicConfig(
      format='%(asctime)s %(levelname)-8s %(message)s',
      level=logging.DEBUG,
      datefmt='%Y-%m-%d %H:%M:%S')
else:
    logging.basicConfig(level=logging.ERROR)

# Read token from file
f = open("/home/pi/netatmo-weather-display/token.txt", "r")
refresh_token = f.read().rstrip()
log.debug("Read token from file: " + refresh_token)
netatmo = NetatmoAccess(client_id=args.client_id,
                        client_secret=args.client_secret,
                        refresh_token=refresh_token)  

if not args.nodisplay:
    display = led.sevensegment()
    # Set the brightness
    display.brightness(DISPLAY_BRIGHTNESS)

while True:
    netatmo.update()
    try:
        indoor = netatmo.get('Indoor')
        outdoor = netatmo.get('Outdoor')

        # Force temps to have 1 decimal
        indoor_temp = '{0:.1f}'.format(float(indoor['Temperature']))
        outdoor_temp = '{0:.1f}'.format(float(outdoor['Temperature']))
        # Summary. 5 chars for indoor and 5 for outdoor (incl 2 dots)
        # TODO: display_text as list
        temp_summary = '{:5}'.format(indoor_temp) + '{:>5}'.format(outdoor_temp)


    except KeyError as error:
        temp_summary = MODULE_NAME_ERROR 
        print("Could not find module name. Error:", error)

    #except ConnectionError, error
    #    temp_summary = NO_CONNECTION_ERROR
    #    print error

    finally:
        # Display in terminal
        if args.nodisplay:
            print(temp_summary)
        # Display on zero seg
        else:
            log.debug('Updating zero seg')
            display.clear()
            log.debug(temp_summary)
            try:
                write_display(display, temp_summary)
            except OverflowError as overflowError:
                display.write_text(DEVICE_ID, DISPLAY_OVERFLOW_ERROR)

    # For loop to execute every second to serve as 'live indicator' on the display.
    # If app stops, the last text on display stays on the display.
    live_indicator = False
    for idx in range(0, UPDATE_INTERVAL):
        time.sleep(ONE_SECOND)
        live_indicator = not live_indicator
        if not args.nodisplay:
            display.letter(deviceId=DEVICE_ID,
                           position=1,
                           char=temp_summary[len(temp_summary)-1],
                           dot=live_indicator,
                           redraw=True)

    
