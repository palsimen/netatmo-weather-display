# netatmo-weather-display
Weather display for Netatmo weather station using Raspberry Pi

App is typically started from a script, e.g:

```
#!/bin/bash

export PYTHONPATH=$PYTHONPATH:<PathToZeroSeg>

python3 NetatmoWeatherDisplay.py --username <username> --password <password> --client_id <client_id> --client_secret <client_secret>

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
