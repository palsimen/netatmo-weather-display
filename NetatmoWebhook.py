"""
Receives Netatmo webhook events (https://dev.netatmo.com/apidocumentation/webhooks)
and keeps the latest indoor/outdoor temperature.
"""
import hashlib
import hmac
import json
import logging
import threading
import time
from http.server import BaseHTTPRequestHandler, HTTPServer
from socketserver import ThreadingMixIn

log = logging.getLogger(__name__)

# Events are small; refuse anything absurd instead of reading it into memory
MAX_BODY_BYTES = 1024 * 1024
# Weather webhooks don't say which type a module is. So when the module ids
# couldn't be looked up by name at startup, recognize them by id instead: the
# base station (indoor) has the event's device_id, and outdoor modules' ids
# start with 02: (rain modules are 05:, extra indoor modules 03:, wind 06:)
OUTDOOR_ID_PREFIX = '02:'


def guess_role(module_id, device_id):
    if module_id == device_id:
        return 'indoor'
    if module_id.startswith(OUTDOOR_ID_PREFIX):
        return 'outdoor'
    return None


def signature_is_valid(raw_body, client_secret, signature):
    """Netatmo signs the raw body with HMAC-SHA256 keyed by the app's client_secret, as lowercase hex."""
    expected = hmac.new(client_secret.encode('utf-8'), raw_body, hashlib.sha256).hexdigest()
    return hmac.compare_digest(expected.encode('ascii'),
                               (signature or '').strip().lower().encode('utf-8', 'replace'))


def module_temperature(module):
    """
    Netatmo doesn't document the weather fields in webhook payloads, so accept
    both the Home+ spelling ('temperature') and the getstationsdata spelling
    ('Temperature', possibly nested in 'dashboard_data').
    """
    for source in (module, module.get('dashboard_data') or {}):
        for key in ('temperature', 'Temperature'):
            value = source.get(key)
            if isinstance(value, (int, float)) and not isinstance(value, bool):
                return float(value)
    return None


class WeatherState:
    """Latest (temperature, unix time) per role ('indoor' / 'outdoor'). Thread safe."""

    def __init__(self):
        self.__lock = threading.Lock()
        self.__module_ids = {}
        self.__readings = {}
        self.__last_webhook = None

    def set_module_id(self, role, module_id):
        with self.__lock:
            self.__module_ids[role] = module_id

    def set_reading(self, role, temperature, timestamp):
        """Store a reading, unless a newer one has already arrived by webhook."""
        with self.__lock:
            current = self.__readings.get(role)
            if current is None or timestamp >= current[1]:
                self.__readings[role] = (temperature, timestamp)

    def get(self, role):
        with self.__lock:
            return self.__readings.get(role)

    def last_webhook(self):
        """When a webhook last delivered a temperature (unix time), or None."""
        with self.__lock:
            return self.__last_webhook

    def __role_for(self, module, device_id):
        module_id = module.get('id') or ''
        for role, known_id in self.__module_ids.items():
            if known_id == module_id:
                return role
        role = guess_role(module_id, device_id)
        if role is None or role in self.__module_ids:
            return None
        log.info("Using module %s as %s", module_id, role)
        self.__module_ids[role] = module_id
        return role

    def apply_event(self, event):
        push_type = event.get('push_type')
        modules = (event.get('extra_params') or {}).get('modules') or []
        if push_type != 'device_event':
            log.info("Received '%s' event, nothing to do", push_type)
            return
        log.info("Received device_event with %d module(s)", len(modules))

        # Out-of-order or duplicate deliveries are not handled (sequence_id is
        # ignored): Netatmo only retries for seconds, while weather modules
        # report every ~10 minutes, so a retry can't overwrite a newer reading.
        now = time.time()
        with self.__lock:
            for module in modules:
                role = self.__role_for(module, event.get('device_id'))
                if role is None:
                    log.info("  %s: not indoor/outdoor, skipped", module.get('id'))
                    continue
                temperature = module_temperature(module)
                if temperature is None:
                    log.warning("  %s (%s): no temperature, fields: %s",
                                module.get('id'), role, ', '.join(sorted(module)))
                    continue
                log.info("  %s (%s): %.1f", module.get('id'), role, temperature)
                self.__readings[role] = (temperature, now)
                self.__last_webhook = now


class _Handler(BaseHTTPRequestHandler):
    # Drop clients that stall mid-request so they can't tie up a thread
    timeout = 10

    def do_GET(self):
        # Handy for checking from outside that the URL reaches the Pi
        log.info("Health check from %s", self.client_address[0])
        self.__reply(200, b"ok\n")

    def do_POST(self):
        try:
            length = int(self.headers.get('Content-Length', ''))
        except ValueError:
            length = -1
        if not 0 <= length <= MAX_BODY_BYTES:
            self.__reply(400, b"bad content length\n")
            return

        raw_body = self.rfile.read(length)
        if not signature_is_valid(raw_body, self.server.client_secret, self.headers.get('X-Netatmo-secret')):
            log.warning("Rejected webhook with bad signature from %s", self.client_address[0])
            self.__reply(403, b"bad signature\n")
            return

        try:
            event = json.loads(raw_body.decode('utf-8'))
        except ValueError:
            event = None
        if not isinstance(event, dict):
            self.__reply(400, b"bad json\n")
            return

        log.debug("Webhook event: %s", event)
        # Reply before handling, so a bug in handling doesn't make Netatmo
        # retry and eventually suspend the endpoint
        self.__reply(200, b"ok\n")
        try:
            self.server.on_event(event)
        except Exception:
            log.exception("Failed to handle webhook event")

    def __reply(self, status, body):
        self.send_response(status)
        self.send_header('Content-Type', 'text/plain')
        self.send_header('Content-Length', str(len(body)))
        self.end_headers()
        self.wfile.write(body)

    def log_message(self, fmt, *args):
        log.debug("%s - " + fmt, self.client_address[0], *args)


class _Server(ThreadingMixIn, HTTPServer):
    daemon_threads = True


def start_webhook_server(host, port, client_secret, on_event):
    """Serve webhooks on a background thread, calling on_event(dict) for each verified event."""
    server = _Server((host, port), _Handler)
    server.client_secret = client_secret
    server.on_event = on_event
    threading.Thread(target=server.serve_forever, name='webhook-server', daemon=True).start()
    log.info("Listening for webhooks on %s:%d", host, server.server_address[1])
    return server
