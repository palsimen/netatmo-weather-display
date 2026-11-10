import logging
import time

import requests

TOKEN_URL = "https://api.netatmo.com/oauth2/token"
STATIONS_DATA_URL = "https://api.netatmo.com/api/getstationsdata"
WEBHOOKS_URL = "https://api.netatmo.com/webhooks/v1/"
DEFAULT_TOKEN_FILE = "/home/pi/netatmo-weather-display/token.txt"
REQUEST_TIMEOUT = 30
# Refresh a bit before Netatmo says the access token expires
EXPIRY_MARGIN = 60

log = logging.getLogger(__name__)


class NetatmoAccess:
    def __init__(self, client_id, client_secret, refresh_token, token_file=DEFAULT_TOKEN_FILE):
        self.__client_id = client_id
        self.__client_secret = client_secret
        self.__refresh_token = refresh_token
        self.__token_file = token_file
        self.__access_token = None
        self.__access_token_expires = 0

    def __auth_header(self):
        if self.__access_token is None or time.time() >= self.__access_token_expires:
            log.info("Refreshing access token...")
            payload = {'grant_type':    'refresh_token',
                       'refresh_token': self.__refresh_token,
                       'client_id':     self.__client_id,
                       'client_secret': self.__client_secret}
            response = requests.post(TOKEN_URL, data=payload, timeout=REQUEST_TIMEOUT)
            response.raise_for_status()
            body = response.json()
            self.__access_token = body["access_token"]
            self.__access_token_expires = time.time() + body.get("expires_in", 0) - EXPIRY_MARGIN
            # Netatmo rotates the refresh token. Write it to file in case system shuts down
            self.__refresh_token = body["refresh_token"]
            with open(self.__token_file, "w") as f:
                f.write(self.__refresh_token)
            log.info("...got access token valid for %d min, saved new refresh token to %s",
                     body.get("expires_in", 0) // 60, self.__token_file)
        return {'Authorization': 'Bearer ' + self.__access_token}

    def get_modules(self):
        """
        Return {module_name: {'id', 'type', 'temperature', 'time'}} for the
        station's base module and all its modules.
        """
        headers = self.__auth_header()
        log.info("Getting station data...")
        response = requests.post(STATIONS_DATA_URL, headers=headers, timeout=REQUEST_TIMEOUT)
        response.raise_for_status()
        base = response.json()["body"]["devices"][0]

        modules = {}
        for module in [base] + base.get('modules', []):
            # dashboard_data is missing while a module is unreachable
            dashboard = module.get('dashboard_data') or {}
            modules[module['module_name']] = {'id': module['_id'],
                                              'type': module.get('type'),
                                              'temperature': dashboard.get('Temperature'),
                                              'time': dashboard.get('time_utc')}
        return modules

    def register_webhook(self, url):
        """
        Make url the webhook for this user. Uses PUT (replace all) rather than
        POST (append) so restarting the app doesn't pile up registrations until
        Netatmo's per-app limit is hit.
        """
        headers = self.__auth_header()
        log.info("Registering webhook %s...", url)
        response = requests.put(WEBHOOKS_URL, json=[{'url': url}], headers=headers, timeout=REQUEST_TIMEOUT)
        response.raise_for_status()
        body = response.json().get('body', [])
        log.debug("Netatmo webhooks for this user: %s", body)
        return body
