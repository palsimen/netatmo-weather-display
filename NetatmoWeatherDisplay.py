import argparse
import logging
import time

import requests

from NetatmoAccess import DEFAULT_TOKEN_FILE, NetatmoAccess
from NetatmoWebhook import WeatherState, start_webhook_server

NAME = "NetatmoWeatherDisplay.py"

# Errors
NO_RECENT_DATA_ERROR   = "E0"
NO_CONNECTION_ERROR    = "E1"
DISPLAY_OVERFLOW_ERROR = "E2"

# Module names as set in the Netatmo app
MODULE_NAMES = {'indoor': 'Indoor', 'outdoor': 'Outdoor'}

# Stations report every ~10 min. Show E0 rather than a temperature older than this (secs)
STALE_AFTER = 30 * 60
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
    # Pair each char with whether a '.' follows it
    chars = []
    for char in text:
        if char == '.' and chars:
            chars[-1] = (chars[-1][0], True)
        else:
            chars.append((char, False))
    if len(chars) > ZERO_SEG_MAX_CHARS:
        raise OverflowError('{0} contains too many characters for display'.format(text))
    chars += [(' ', False)] * (ZERO_SEG_MAX_CHARS - len(chars))

    # Write it to the zero seg display. Position 1 is the rightmost char
    for pos, (char, dot) in enumerate(reversed(chars)):
        display.letter(deviceId=DEVICE_ID,
                       position=(pos+1),
                       char=char,
                       dot=dot,
                       redraw=True)


def format_reading(reading, now):
    """Temperature with 1 decimal, or E0 if there is no recent reading."""
    if reading is None or now - reading[1] > STALE_AFTER:
        return NO_RECENT_DATA_ERROR
    return '{0:.1f}'.format(reading[0])


def build_summary(state, now):
    """
    Summary. 4 display chars for indoor and 4 for outdoor. A '.' is drawn on
    the char before it, so it doesn't take up a char of its own.
    """
    indoor = format_reading(state.get('indoor'), now)
    outdoor = format_reading(state.get('outdoor'), now)
    return indoor.ljust(4 + indoor.count('.')) + outdoor.rjust(4 + outdoor.count('.'))


def show(display, summary):
    # Display in terminal
    if display is None:
        print(summary, flush=True)
    # Display on zero seg
    else:
        log.debug('Updating zero seg: %s', summary)
        display.clear()
        try:
            write_display(display, summary)
        except OverflowError:
            display.write_text(DEVICE_ID, DISPLAY_OVERFLOW_ERROR)


def describe(error):
    """Netatmo explains failures in the response body, which HTTPError's message leaves out."""
    response = getattr(error, 'response', None)
    if response is not None:
        return '{0} {1}'.format(response.status_code, response.text)
    return repr(error)


def seed_from_station(netatmo, state):
    """
    Look up which module ids are named Indoor/Outdoor and show their current
    temperature right away, instead of E0 until the first webhook (up to ~10
    min). The app still works if this fails: modules are then picked by type.
    """
    try:
        modules = netatmo.get_modules()
    except (requests.exceptions.RequestException, KeyError, IndexError, ValueError) as error:
        log.warning('Could not get station data, waiting for first webhook: %s', describe(error))
        return

    for role, name in MODULE_NAMES.items():
        module = modules.get(name)
        if module is None:
            log.warning("Module '%s' not found. Available modules are: %s", name, ', '.join(modules))
            continue
        state.set_module_id(role, module['id'])
        if module['temperature'] is not None:
            state.set_reading(role, module['temperature'], module['time'] or time.time())


def main():
    parser = argparse.ArgumentParser(description=NAME)
    parser.add_argument('--client_id',     help='client_id',     required=True)
    parser.add_argument('--client_secret', help='client_secret', required=True)
    parser.add_argument('--webhook_url',   help='public URL Netatmo should send events to. Registered at startup; '
                                                'leave out if the webhook URL is set in the app settings on dev.netatmo.com')
    parser.add_argument('--listen',        help='address to receive webhooks on (default: %(default)s)', default='0.0.0.0')
    parser.add_argument('--port',          help='port to receive webhooks on (default: %(default)s)', type=int, default=8080)
    parser.add_argument('--token_file',    help='file holding the refresh token (default: %(default)s)', default=DEFAULT_TOKEN_FILE)
    parser.add_argument('--nodisplay',     help='run system without zero seg display', action='store_true')
    parser.add_argument('--debug',         help='enable debug logging', action='store_true')
    args = parser.parse_args()

    logging.basicConfig(
      format='%(asctime)s %(levelname)-8s %(message)s',
      level=logging.DEBUG if args.debug else logging.WARNING,
      datefmt='%Y-%m-%d %H:%M:%S')

    # Read token from file
    with open(args.token_file, "r") as f:
        refresh_token = f.read().rstrip()
    netatmo = NetatmoAccess(client_id=args.client_id,
                            client_secret=args.client_secret,
                            refresh_token=refresh_token,
                            token_file=args.token_file)

    display = None
    if not args.nodisplay:
        # Imported here so the app can run with --nodisplay where ZeroSeg isn't installed
        import ZeroSeg.led as led
        display = led.sevensegment()
        # Set the brightness
        display.brightness(DISPLAY_BRIGHTNESS)

    state = WeatherState()
    # Listen before registering, so the endpoint is up when Netatmo starts sending
    start_webhook_server(args.listen, args.port, args.client_secret, state.apply_event)
    log.debug('Listening for webhooks on %s:%d', args.listen, args.port)

    seed_from_station(netatmo, state)

    if args.webhook_url:
        try:
            netatmo.register_webhook(args.webhook_url)
            log.debug('Registered webhook %s', args.webhook_url)
        except requests.exceptions.RequestException as error:
            log.error('Could not register webhook %s: %s', args.webhook_url, describe(error))

    # Redraw when the readings change, otherwise blink a dot every second as
    # 'live indicator'. If app stops, the last text on display stays on the display.
    shown = None
    live_indicator = False
    while True:
        summary = build_summary(state, time.time())
        if summary != shown:
            show(display, summary)
            shown = summary
        elif display is not None:
            live_indicator = not live_indicator
            display.letter(deviceId=DEVICE_ID,
                           position=1,
                           char=summary[-1],
                           dot=live_indicator,
                           redraw=True)
        time.sleep(ONE_SECOND)


if __name__ == '__main__':
    main()
