#this is version number 6
#Do NOT update following lines
NODE_ID = 1
firmware_url = "https://github.com/atonughosh/tsdpl_vib_temp"
from ota import OTAUpdater
from WIFI_CONFIG import SSID, PASSWORD
#Update below this

import uasyncio as asyncio
from machine import Pin
import time
import gc



# Set up pin for the LED
led = Pin(2, Pin.OUT)  # Most ESP32 boards have an onboard LED on GPIO 2

async def task1():
    while True:
        gc.collect()
        ota_updater = OTAUpdater(SSID, PASSWORD, firmware_url, "main.py", NODE_ID)
        ota_updater.download_and_install_update_if_available()
        gc.collect()
        await asyncio.sleep(0.5)

async def task2():
    while True:
        led.value(1)  # Turn on the LED
        time.sleep(0.5)  # Delay for 500ms
        led.value(0)  # Turn off the LED
        time.sleep(0.5)  # Delay for 500ms
        await asyncio.sleep(0.5)

async def main():
    await asyncio.gather(task1(), task2())

# Start the main event loop
asyncio.run(main())
