import argparse
import itertools
import logging
import threading
import time
from urllib.parse import urlparse

import requests

from NetatmoAccess import DEFAULT_TOKEN_FILE, NetatmoAccess
from NetatmoWebhook import WeatherState, start_webhook_server

NAME = "NetatmoWeatherDisplay.py"

# Texts shown instead of temperatures. 7 segments can't draw K, M, W or X,
# and O, D, S look like 0, 0, 5, hence the odd mix of upper and lower case
NO_DATA     = "no dAtA"   # no temperatures received yet
OLD_DATA    = "oLd dAtA"  # nothing new from either module for STALE_AFTER
NO_READING  = "----"      # one module hasn't reported yet
OLD_READING = "oLd"       # one module has been quiet for STALE_AFTER
DISPLAY_OVERFLOW_ERROR = "Err"

# Module names as set in the Netatmo app
MODULE_NAMES = {'indoor': 'Indoor', 'outdoor': 'Outdoor'}

# Stations report every ~10 min. Show 'oLd' rather than a temperature older than this (secs)
STALE_AFTER = 30 * 60
# Wait between retries of failed startup calls to Netatmo (secs). The last one repeats
RETRY_DELAYS = [30, 60, 120, 300]
ONE_SECOND = 1
ZERO_SEG_MAX_CHARS = 8
DEVICE_ID = 0
DISPLAY_BRIGHTNESS = 1

log = logging.getLogger(NAME)

def write_display(display, text):
    """
    Function to write to the zero seg display and not use
    a separate char for displaying a '.'. Text is right-aligned, so its last
    char is at position 1, where the live indicator blinks.
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
    chars = [(' ', False)] * (ZERO_SEG_MAX_CHARS - len(chars)) + chars

    # Write it to the zero seg display. Position 1 is the rightmost char
    for pos, (char, dot) in enumerate(reversed(chars)):
        display.letter(deviceId=DEVICE_ID,
                       position=(pos+1),
                       char=char,
                       dot=dot,
                       redraw=True)


def format_reading(reading, now):
    """Temperature with 1 decimal, or a text if there is no recent reading."""
    if reading is None:
        return NO_READING
    if now - reading[1] > STALE_AFTER:
        return OLD_READING
    return '{0:.1f}'.format(reading[0])


def build_summary(state, now):
    """
    Summary. 4 display chars for indoor and 4 for outdoor. A '.' is drawn on
    the char before it, so it doesn't take up a char of its own. When both
    have the same problem, it's spelled out across the whole display.
    """
    indoor = format_reading(state.get('indoor'), now)
    outdoor = format_reading(state.get('outdoor'), now)
    if indoor == outdoor == NO_READING:
        return NO_DATA
    if indoor == outdoor == OLD_READING:
        return OLD_DATA
    return indoor.ljust(4 + indoor.count('.')) + outdoor.rjust(4 + outdoor.count('.'))


def show(display, summary):
    """Show summary, and return the text that ended up on the display."""
    # Display in terminal
    if display is None:
        print(summary, flush=True)
        return summary
    # Display on zero seg
    log.info("Showing '%s'", summary)
    display.clear()
    try:
        write_display(display, summary)
        return summary
    except OverflowError:
        log.error("'%s' is too long for the display", summary)
        write_display(display, DISPLAY_OVERFLOW_ERROR)
        return DISPLAY_OVERFLOW_ERROR


def describe(error):
    """
    Which Netatmo call failed, and why. Netatmo explains failures in the
    response body, which HTTPError's message leaves out.
    """
    request = getattr(error, 'request', None)
    where = '{0} {1}: '.format(request.method, urlparse(request.url).path) if request is not None else ''
    response = getattr(error, 'response', None)
    if response is not None:
        return where + '{0} {1}'.format(response.status_code, response.text)
    return where + repr(error)


def is_transient(error):
    """Timeouts, connection problems, 5xx and 429 may go away. Other errors, like a rejected token, won't."""
    response = getattr(error, 'response', None)
    if response is None:
        return isinstance(error, requests.exceptions.RequestException)
    return response.status_code >= 500 or response.status_code == 429


def seed_from_station(netatmo, state):
    """
    Look up which module ids are named Indoor/Outdoor and show their current
    temperature right away, instead of E0 until the first webhook (up to ~10
    min). The app still works if this fails: modules are then picked by type.
    Returns False if it should be retried.
    """
    if state.get('indoor') and state.get('outdoor'):
        log.info('Webhooks already gave both temperatures, skipping station data')
        return True
    try:
        modules = netatmo.get_modules()
    except (requests.exceptions.RequestException, KeyError, IndexError, ValueError) as error:
        log.warning('Could not get station data: %s', describe(error))
        return not is_transient(error)

    log.info('Station modules: %s', ', '.join('{0} ({1}, {2})'.format(name, module['type'], module['temperature'])
                                               for name, module in modules.items()))
    for role, name in MODULE_NAMES.items():
        module = modules.get(name)
        if module is None:
            log.warning("Module '%s' not found. Available modules are: %s", name, ', '.join(modules))
            continue
        state.set_module_id(role, module['id'])
        if module['temperature'] is not None:
            state.set_reading(role, module['temperature'], module['time'] or time.time())
    return True


def register_webhook(netatmo, url):
    """Returns False if it should be retried."""
    try:
        urls = netatmo.register_webhook(url)
    except requests.exceptions.RequestException as error:
        log.error('Could not register webhook %s: %s', url, describe(error))
        return not is_transient(error)
    if url in urls:
        log.info('Registered webhook %s, Netatmo has: %s', url, ', '.join(urls))
    else:
        log.error('Netatmo did not store webhook %s, it has: %s', url, ', '.join(urls) or 'none')
    return True


def retry(tasks):
    for delay in itertools.chain(RETRY_DELAYS, itertools.repeat(RETRY_DELAYS[-1])):
        log.warning('Retrying Netatmo in %d s', delay)
        time.sleep(delay)
        tasks = [task for task in tasks if not task()]
        if not tasks:
            log.warning('Netatmo retry succeeded')
            return


def connect_to_netatmo(netatmo, state, webhook_url):
    """
    Seed the display and register the webhook. If Netatmo can't be reached,
    keep retrying on a background thread, since without the registration no
    webhooks will arrive.
    """
    tasks = [lambda: seed_from_station(netatmo, state)]
    if webhook_url:
        tasks.append(lambda: register_webhook(netatmo, webhook_url))
    tasks = [task for task in tasks if not task()]
    if tasks:
        threading.Thread(target=retry, args=(tasks,), name='netatmo-retry', daemon=True).start()


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
      level=logging.DEBUG if args.debug else logging.INFO,
      datefmt='%Y-%m-%d %H:%M:%S')
    log.info('Starting %s (display: %s, webhook url: %s)', NAME,
             'terminal' if args.nodisplay else 'zero seg',
             args.webhook_url or 'from app settings on dev.netatmo.com')

    # Read token from file
    with open(args.token_file, "r") as f:
        refresh_token = f.read().rstrip()
    log.info('Read refresh token from %s', args.token_file)
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

    connect_to_netatmo(netatmo, state, args.webhook_url)
    log.info('Waiting for webhooks...')

    # Redraw when the readings change, otherwise blink a dot every second as
    # 'live indicator'. If app stops, the last text on display stays on the display.
    shown = None
    on_display = None
    live_indicator = False
    while True:
        summary = build_summary(state, time.time())
        if summary != shown:
            on_display = show(display, summary)
            shown = summary
        elif display is not None:
            live_indicator = not live_indicator
            display.letter(deviceId=DEVICE_ID,
                           position=1,
                           char=on_display[-1],
                           dot=live_indicator,
                           redraw=True)
        time.sleep(ONE_SECOND)


if __name__ == '__main__':
    main()
