import gc
import machine
import uasyncio as asyncio
from ota import OTAUpdater

# Wi-Fi credentials
try:
    from WIFI_CONFIG import SSID, PASSWORD
except ImportError:
    print("Error: WIFI_CONFIG.py not found!")
    SSID = ""
    PASSWORD = ""

# Firmware details
NODE_ID = 2
FIRMWARE_URL = "https://github.com/atonughosh/tsdpl_vib_temp"

# Function to connect to Wi-Fi
async def connect_wifi(ssid, password, max_retries=10):
    import network
    sta_if = network.WLAN(network.STA_IF)
    sta_if.active(True)
    retries = 0

    if not sta_if.isconnected():
        print(f"Connecting to Wi-Fi: {ssid}")
        sta_if.connect(ssid, password)
        while not sta_if.isconnected() and retries < max_retries:
            await asyncio.sleep(1)
            retries += 1

    if sta_if.isconnected():
        print(f"Connected to Wi-Fi. IP address: {sta_if.ifconfig()[0]}")
    else:
        print("Failed to connect to Wi-Fi. Rebooting...")
        machine.reset()

# Function to perform OTA update at boot
async def boot_ota_update():
    try:
        print("Starting OTA update process...")
        ota_updater = OTAUpdater(SSID, PASSWORD, FIRMWARE_URL, "main.py", NODE_ID)
        if await ota_updater.check_for_updates():
            print("Update available. Installing...")
            ota_updater.update_and_reset()
        else:
            print("No update available.")
    except Exception as e:
        print(f"OTA update failed: {e}")

# Main boot sequence
async def boot():
    gc.collect()
    await connect_wifi(SSID, PASSWORD)
    await boot_ota_update()

# Run the boot process
asyncio.run(boot())
gc.collect()