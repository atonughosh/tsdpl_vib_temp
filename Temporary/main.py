import machine
import uasyncio as asyncio
import json
from machine import SPI, Pin, I2C
from umqtt.simple import MQTTClient
import max31865
from ota import OTAUpdater
import gc

# Constants
RTD_NOMINAL = 100.0  # Resistance of RTD at 0°C
RTD_REFERENCE = 402.0  # Reference resistor on the PCB
RTD_WIRES = 3  # 3-wire configuration
MPU6050_ADDR = 0x68  # I2C address of the MPU6050 sensor
PWR_MGMT_1 = 0x6B  # Power management register
BROKER = "13.232.192.17"  # MQTT broker
PORT = 1883  # MQTT port
TOPIC = "esp32/data"  # Topic for publishing
REBOOT_TOPIC = "remote_control"  # Topic for receiving commands
NODE_ID = 2
firmware_url = "https://github.com/atonughosh/tsdpl_vib_temp"
SSID = "Ramniwas"
PASSWORD = "lasvegas@007"

# SPI and I2C setup
sck = machine.Pin(18, machine.Pin.OUT)
mosi = machine.Pin(23, machine.Pin.OUT)
miso = machine.Pin(19, machine.Pin.IN)
spi = machine.SPI(baudrate=50000, sck=sck, mosi=mosi, miso=miso, polarity=0, phase=1)
cs1 = machine.Pin(5, machine.Pin.OUT, value=1)
css = [cs1]
sensors = [max31865.MAX31865(spi, cs, wires=RTD_WIRES, rtd_nominal=RTD_NOMINAL, ref_resistor=RTD_REFERENCE) for cs in css]

# I2C setup for MPU6050
scl_pin = machine.Pin(22)
sda_pin = machine.Pin(21)
i2c = I2C(0, scl=scl_pin, sda=sda_pin, freq=400000)

# LED setup
led = Pin(2, Pin.OUT)

# Function to create or overwrite WIFI_CONFIG.py
def create_wifi_config_file():
    with open('WIFI_CONFIG.py', 'w') as f:
        f.write(f'SSID = "{SSID}"\n')
        f.write(f'PASSWORD = "{PASSWORD}"\n')

# Function to create or overwrite boot.py with custom contents
def create_boot_file():
    with open('boot.py', 'w') as f:
        # Specify the full contents of boot.py here
        boot_code = f"""
import os
import gc
import uasyncio as asyncio

# Import SSID and PASSWORD from WIFI_CONFIG.py
try:
    from WIFI_CONFIG import SSID, PASSWORD
except ImportError:
    print("Error: WIFI_CONFIG.py not found!")
    SSID = ""
    PASSWORD = ""

# Your boot actions: 

from ota import OTAUpdater
from WIFI_CONFIG import SSID, PASSWORD
import gc
NODE_ID = "2"

gc.collect()
firmware_url = "https://github.com/atonughosh/tsdpl_vib_temp"

async def boot_time_ota():
    try:
        ota_updater = OTAUpdater(SSID, PASSWORD, firmware_url, "main.py", NODE_ID)
        
        # Check if an update is available
        await asyncio.sleep(20)
        if await ota_updater.check_for_updates():
            # If there's a new version, perform the update
            ota_updater.update_and_reset()
        else:
            print("No update available.")
    except:
        print(f"Error during OTA update")


# Start the async update process
async def boot():
    gc.collect()
    await boot_time_ota()  # Await the update process

# Execute the boot process using uasyncio
asyncio.run(boot())

gc.collect()

# You can add more boot actions here if needed
"""
        f.write(boot_code)

# First, create the WIFI_CONFIG.py file
create_wifi_config_file()

# Then, create the boot.py file with your custom content
create_boot_file()

# Update below this

# MQTT callback function
def on_message(topic, msg):
    print(f"Received message on {topic}: {msg}")
    
    # Decode msg from bytes to string
    msg_str = msg.decode('utf-8')  # Ensure it's decoded to a string
    
    if topic == REBOOT_TOPIC and msg_str == "reboot":
        print("Reboot command received. Rebooting device...")
        machine.reset()

# Asynchronous functions

async def get_firmware_version():
    try:
        with open("version.json", "r") as f:
            version_data = json.load(f)
            return version_data.get("version", "unknown")
    except Exception as e:
        print(f"Failed to read version file: {e}")
        return "unknown"

async def connect_mqtt():
    client = MQTTClient("esp32_client", BROKER, port=PORT, keepalive=60)
    client.set_callback(on_message)
    try:
        client.connect()
        client.subscribe(REBOOT_TOPIC)  # Subscribe to the reboot topic
        print("Connected to MQTT broker and subscribed to topic")
        return client
    except Exception as e:
        print(f"Failed to connect to MQTT broker: {e}")
        return None

async def reconnect_mqtt(client):
    try:
        client.disconnect()
    except Exception:
        pass  # Ignore errors during disconnect
    return await connect_mqtt(client)

async def publish_data(client, data):
    if client:
        try:
            client.publish(TOPIC, data)
            print(f"Published: {data}")
        except Exception as e:
            print(f"Error publishing: {e}")
            client = await reconnect_mqtt(client)
    return client

async def read_accel():
    try:
        ax = await read_i2c_word(i2c, 0x3B)
        ay = await read_i2c_word(i2c, 0x3D)
        az = await read_i2c_word(i2c, 0x3F)
        return ax / 16384.0, ay / 16384.0, az / 16384.0
    except Exception as e:
        print(f"Error reading accelerometer: {e}")
        return 0.0, 0.0, 0.0

async def read_i2c_word(i2c, register):
    data = i2c.readfrom_mem(MPU6050_ADDR, register, 2)
    value = (data[0] << 8) | data[1]
    if value >= 0x8000:
        value -= 0x10000
    return value

async def read_temperature():
    try:
        return sensors[0].temperature
    except Exception as e:
        print(f"Error reading temperature: {e}")
        return None

async def ota_task():
    retries = 0
    while retries < 5:
        try:
            ota_updater = OTAUpdater(SSID, PASSWORD, firmware_url, "main.py", NODE_ID)
            if await ota_updater.check_for_updates():
                ota_updater.update_and_reset()
                return  # Exit if update is successful
            else:
                print("No update available.")
            retries = 0
        except Exception as e:
            retries += 1
            print(f"Error in OTA update: {e}. Retry {retries}/5")
        await asyncio.sleep(120)

async def led_blink_task():
    while True:
        led.value(1)
        await asyncio.sleep(1)
        led.value(0)
        await asyncio.sleep(1)

async def temperature_task():
    client = None
    firmware_version = await get_firmware_version()
    
    while True:
        if client is None:
            print("Connecting to MQTT...")
            client = await connect_mqtt()
            if client is None:
                await asyncio.sleep(5)
                continue
        
        ax, ay, az = await read_accel()
        if ax is None or ay is None or az is None:
            print("Invalid accelerometer data, skipping cycle.")
            await asyncio.sleep(5)
            continue
        
        temperature = await read_temperature()
        data = f"AccX: {ax:.2f}, AccY: {ay:.2f}, AccZ: {az:.2f}, Temp: {temperature:.2f}C, FW: {firmware_version}"
        
        client = await publish_data(client, data)
        client.check_msg()  # Check for incoming messages
        await asyncio.sleep(5)

async def main():
    await asyncio.gather(ota_task(), led_blink_task(), temperature_task())

# Start the main loop
asyncio.run(main())
