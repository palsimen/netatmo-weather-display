import requests

class NetatmoAccess:
    def __init__(self, client_id, client_secret, refresh_token):
        self.__client_id=client_id
        self.__client_secret=client_secret
        self.__refresh_token=refresh_token

        self.__data = {}

    def update(self):
        try:
            print("Getting token...")
            payload = {'grant_type':    'refresh_token',
                       'refresh_token': self.__refresh_token,
                       'client_id':     self.__client_id,
                       'client_secret': self.__client_secret}
            response = requests.post("https://api.netatmo.com/oauth2/token", data=payload)
            response.raise_for_status()
            access_token=response.json()["access_token"]
            self.__refresh_token=response.json()["refresh_token"]
            # Write refresh token to file in case system shytsdown
            f = open("/home/pi/netatmo-weather-display/token.txt", "w")
            f.write(self.__refresh_token)
            f.close()
            scope=response.json()["scope"]

            params = {
                'access_token': access_token
            }
            print("...got access_token=" + access_token + ", refesh_token=" + self.__refresh_token)

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
            raise KeyError('Module \'' + module_name + '\' not found. Available modules are: ' + ",".join(available_modules))

