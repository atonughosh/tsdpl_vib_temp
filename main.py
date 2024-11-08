from ota import OTAUpdater
from WIFI_CONFIG import SSID, PASSWORD

import _thread
from machine import Pin
import time


firmware_url = "https://github.com/atonughosh/tsdpl_vib_temp"


# Set up pin for the LED
led = Pin(2, Pin.OUT)  # Most ESP32 boards have an onboard LED on GPIO 2


def task1():
    while True:
        ota_updater = OTAUpdater(SSID, PASSWORD, firmware_url, "main.py")
        ota_updater.download_and_install_update_if_available()

def task2():
    # Blinking loop
    while True:
        led.value(1)  # Turn on the LED
        time.sleep(0.5)  # Delay for 500ms
        led.value(0)  # Turn off the LED
        time.sleep(0.5)  # Delay for 500ms

# Start Task 1 in a new thread
_thread.start_new_thread(task1, ())

# Run Task 2 in the main thread
task2()
