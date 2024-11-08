from ota import OTAUpdater
from WIFI_CONFIG import SSID, PASSWORD

from machine import Pin
import time


firmware_url = "https://github.com/atonughosh/tsdpl_vib_temp"

ota_updater = OTAUpdater(SSID, PASSWORD, firmware_url, "main.py")

ota_updater.download_and_install_update_if_available()

# Set up pin for the LED
led = Pin(2, Pin.OUT)  # Most ESP32 boards have an onboard LED on GPIO 2

# Blinking loop
while True:
    led.value(1)  # Turn on the LED
    time.sleep(2)  # Delay for 500ms
    led.value(0)  # Turn off the LED
    time.sleep(2)  # Delay for 500ms

#This is the file from GitHub
