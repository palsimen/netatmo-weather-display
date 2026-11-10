# netatmo-weather-display
Weather display for Netatmo weather station using Raspberry Pi and ZeroSeg

App is typically started from a script, e.g:

```
#!/bin/bash

export PYTHONPATH=$PYTHONPATH:<PathToZeroSeg>

python3 NetatmoWeatherDisplay.py --client_id <client_id> --client_secret <client_secret> --webhook_url https://<public-host>/netatmo

```

Generate token from netatmo web page and add to file: token.txt

## Webhooks
Netatmo pushes new measurements (roughly every 10 min) to the app as [webhooks](https://dev.netatmo.com/apidocumentation/webhooks) instead of the app polling for them. The app receives them on port 8080 (change with `--listen` / `--port`), checks the `X-Netatmo-secret` signature against the client secret, and updates the display.

* Netatmo must be able to reach the Pi from the internet, preferably over HTTPS, e.g. with Tailscale Funnel (`sudo tailscale funnel --bg 8080`), a Cloudflare Tunnel, or a port forward on the router.
* `--webhook_url` registers the URL for your user at startup. Alternatively set the webhook URL in the app settings on dev.netatmo.com, and then generate a new token, since Netatmo links the webhook when the app is authorized.
* `curl https://<public-host>/netatmo` should answer `ok` when the Pi is reachable.
* At startup the current temperatures are read once from the station, so the display doesn't have to wait for the first webhook.
* Run with `--debug` to log every event received.

Display texts:
* `no dAtA`: no temperatures received yet
* `oLd dAtA`: nothing new from either module for 30 min
* `----` in one half: that module hasn't reported yet
* `oLd` in one half: that module hasn't reported for 30 min
* `Err`: text too long for the display

## Start from cron
```
# Check every 5th min if NetatmoWeatherDisplay.py is running, otherwise restart it
*/5 * * * * ~/misc/utils/check_process_and_action.sh -p NetatmoWeatherDisplay.py -a ~/start-netatmo-weather-display
```

```
#!/bin/bash

nohup ~/bin/netatmo-weather-display
```

## ZeroSeg
[Link](https://github.com/AverageMaker/ZeroSeg)

### Config
* Next run sudo raspi-config and enable SPI. Select option 5 Interfacing Options and then option 4 SPI. Select Yes to enable the SPI interface and hit enter.
* Exit the config tool by selecting Finish
* Reboot your Raspberry Pi by entering 'sudo reboot' and hit enter
* Once rebooted, run sudo apt-get install git build-essential python-dev python-pip. Enter 'Y' when prompted, and hit enter. Let the install run.
* Enter cd in the terminal and hit enter, to ensure you're in the home directory
* Next run git clone https://github.com/AverageMaker/ZeroSeg.git to download the ZeroSeg code library to your Pi.
* Enter cd ZeroSeg to enter your new ZeroSeg directory
* Next run sudo python setup.py install
* With the files now downloaded, complete the SPI setup. Whilst still in the ZeroSeg directory, run the following command and hit enter sudo pip install spidev
