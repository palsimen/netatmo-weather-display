import requests

class NetatmoAccess:
    def __init__(self, username, password, client_id, client_secret):
        self.__payload = {'grant_type':    'password',
                          'username':      username,
                          'password':      password,
                          'client_id':     client_id,
                          'client_secret': client_secret,
                          'scope': ''}

        self.__data = {}

    def update(self):
        try:
            response = requests.post("https://api.netatmo.com/oauth2/token", data=self.__payload)
            response.raise_for_status()
            access_token=response.json()["access_token"]
            refresh_token=response.json()["refresh_token"]
            scope=response.json()["scope"]

            params = {
                'access_token': access_token
            }

            try:
                response = requests.post("https://api.netatmo.com/api/getstationsdata", params=params)
                response.raise_for_status()
                self.__data = response.json()["body"]
                #print self.__data
            except requests.exceptions.HTTPError as error:
                print(error.response.status_code, error.response.text)

        except requests.exceptions.HTTPError as error:
            print(error.response.status_code, error.response.text)

    def get(self, module_name):
        base = self.__data['devices'][0]
        # Add master module to list of availbale modules, only used for printing
        # if module was not found
        available_modules = [base['module_name']]
        # Check if module name is the master module
        if (base['module_name'] == module_name):
            return base['dashboard_data']
        else:
            # Find module index
            for idx, module in enumerate(base['modules']):
                available_modules.append(module['module_name'])
                if module['module_name'] == module_name:
                    return base['modules'][idx]['dashboard_data']

            # Not found, raise exception
            raise KeyError, 'Module \'' + module_name + '\' not found. Available modules are: ' + ",".join(available_modules)

