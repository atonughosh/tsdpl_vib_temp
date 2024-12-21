import machine
import uasyncio as asyncio
import json
from machine import Pin, I2C
from machine import SoftSPI
from umqtt.simple import MQTTClient
import max31865
from ota import OTAUpdater
import gc
import math
import time

# Constants
RTD_NOMINAL = 100.0  # Resistance of RTD at 0°C
RTD_REFERENCE = 402.0  # Reference resistor on the PCB
RTD_WIRES = 3  # 3-wire configuration
MPU6050_ADDR = 0x68  # I2C address of the MPU6050 sensor
PWR_MGMT_1 = 0x6B  # Power management register
BROKER = "13.232.192.17"  # MQTT broker
PORT = 1883  # MQTT port
REBOOT_TOPIC = "remote_control"  # Topic for receiving commands
##########################Update This########################
NODE_ID = 2
#############################################################
TOPIC = f"OC7/data/N{NODE_ID}"  # Topic for publishing
firmware_url = "https://github.com/atonughosh/tsdpl_vib_temp"
SSID = "Ramniwas"
PASSWORD = "lasvegas@007"

# SPI and I2C setup
sck = machine.Pin(18, machine.Pin.OUT)
mosi = machine.Pin(23, machine.Pin.OUT)
miso = machine.Pin(19, machine.Pin.IN)
spi = machine.SoftSPI(baudrate=50000, sck=sck, mosi=mosi, miso=miso, polarity=0, phase=1)
cs1 = machine.Pin(5, machine.Pin.OUT, value=1)
css = [cs1]
sensors = [max31865.MAX31865(spi, cs, wires=RTD_WIRES, rtd_nominal=RTD_NOMINAL, ref_resistor=RTD_REFERENCE) for cs in css]

# I2C setup for MPU6050
scl_pin = machine.Pin(22)
sda_pin = machine.Pin(21)
i2c = I2C(0, scl=scl_pin, sda=sda_pin, freq=400000)

# Update below this

# Shared state for MPU6050 status
mpu6050_initialized = False  # Tracks if MPU6050 is initialized

OFFSET_FILE = "mpu6050_offsets.json"

last_error_time = 0  # Global variable to track last error print time


# Global variable for offsets
#offsets = (0, 0, 0)
def save_offsets_to_file(offsets):
    try:
        with open(OFFSET_FILE, "w") as f:
            json.dump({"ax_offset": offsets[0], "ay_offset": offsets[1], "az_offset": offsets[2]}, f)
        print("Offsets saved to file.")
    except Exception as e:
        print(f"Error saving offsets to file: {e}")

def load_offsets_from_file():
    try:
        with open(OFFSET_FILE, "r") as f:
            data = json.load(f)
            print("Offsets loaded from file.")
            return data["ax_offset"], data["ay_offset"], data["az_offset"]
    except Exception as e:
        print(f"Error loading offsets from file: {e}")
        return 0, 0, 0  # Default offsets if file is missing or corrupted

# Global variable for offsets
offsets = load_offsets_from_file()


async def detect_mpu6050():
    try:
        # Read a known register to confirm presence (WHO_AM_I register, 0x75, should return 0x68)
        data = i2c.readfrom_mem(MPU6050_ADDR, 0x75, 1)
        return data[0] == 0x68  # True if MPU6050 is detected
    except Exception:
        return False

async def initialize_mpu6050():
    try:
        # Wake up the MPU6050 as it starts in sleep mode
        i2c.writeto_mem(MPU6050_ADDR, PWR_MGMT_1, b'\x00')  # Write 0 to PWR_MGMT_1 to wake it up
        print("MPU6050 initialized successfully.")
        return True
    except Exception as e:
        print(f"Failed to initialize MPU6050: {e}")
        return False


# MQTT callback function
def on_message(topic, msg):
    print(f"Received message on {topic}: {msg}")
    
    # Decode msg from bytes to string
    msg_str = msg.decode('utf-8')  # Ensure it's decoded to a string
    topic_str = topic.decode('utf-8')  # Decode topic if necessary

    # Check if the message is a "reboot" command
    if topic_str == REBOOT_TOPIC and msg_str == "reboot":
        print("Reboot command received. Rebooting device...")
        machine.reset()
    
    # Handle calibration command
    elif topic_str == REBOOT_TOPIC and msg_str == "calibrate":
        print("Calibration command received. Starting calibration...")
        asyncio.create_task(trigger_calibration())


# Asynchronous functions

async def get_firmware_version():
    try:
        with open("version.json", "r") as f:
            version_data = json.load(f)
            gc.collect()
            return version_data.get("version", "unknown")
    except Exception as e:
        print(f"Failed to read version file: {e}")
        return "0"

async def connect_mqtt():
    client = MQTTClient(TOPIC, BROKER, port=PORT, keepalive=60)
    client.set_callback(on_message)
    try:
        client.connect()
        client.subscribe(REBOOT_TOPIC)  # Subscribe to the reboot topic
        print("Connected to MQTT broker and subscribed to topic")
        gc.collect()
        return client
    except Exception as e:
        print(f"Failed to connect to MQTT broker: {e}")
        return None

async def reconnect_mqtt(client):
    try:
        if client:  # Disconnect only if the client exists
            print("Disconnecting existing MQTT client...")
            client.disconnect()
            gc.collect()
    except Exception as e:
        print(f"Error during disconnection: {e}")
    
    # Wait for a short period before attempting to reconnect
    await asyncio.sleep(1)
    return await connect_mqtt()

async def publish_data(client, data):
    if client:
        try:
            client.publish(TOPIC, data)
            print(f"Published: {data}")
            gc.collect()
        except Exception as e:
            print(f"Error publishing: {e}")
            client = await reconnect_mqtt(client)
    return client

async def check_mqtt_messages(client):
    try:
        if client:  # Ensure the client exists
            # Attempt to check for incoming MQTT messages
            client.check_msg()  # Non-blocking call to check for incoming MQTT messages
        else:
            print("MQTT client is None, reconnecting...")
            client = await reconnect_mqtt(client)  # Attempt reconnection if client is None
    except Exception as e:
        print(f"Error checking MQTT messages: {e}")
        client = await reconnect_mqtt(client)  # Reconnect if error occurs
    return client

# async def read_accel():
#     try:
#         ax = await read_i2c_word(i2c, 0x3B)
#         ay = await read_i2c_word(i2c, 0x3D)
#         az = await read_i2c_word(i2c, 0x3F)
#         return ax / 16384.0, ay / 16384.0, az / 16384.0
#     except Exception as e:
#         print(f"Error reading accelerometer: {e}")
#         return 0.0, 0.0, 0.0

async def read_accel(i2c, offsets):
    ax_offset, ay_offset, az_offset = offsets
    try:
        ax = read_i2c_word(i2c, 0x3B) - ax_offset
        ay = read_i2c_word(i2c, 0x3D) - ay_offset
        az = read_i2c_word(i2c, 0x3F) - az_offset
        return ax / 16384.0, ay / 16384.0, az / 16384.0
    except Exception as e:
        print(f"Error reading accelerometer: {e}")
        return 0.0, 0.0, 0.0
    
async def calculate_rms(i2c, offsets, num_samples=500):
    ax_squared, ay_squared, az_squared = 0, 0, 0
    
    for _ in range(num_samples):
        ax, ay, az = await read_accel(i2c, offsets)
        ax_squared += ax ** 2
        ay_squared += ay ** 2
        az_squared += az ** 2
        await asyncio.sleep(0)  # Yield control to other tasks
    return (
        math.sqrt(ax_squared / num_samples),
        math.sqrt(ay_squared / num_samples),
        math.sqrt(az_squared / num_samples),
    )

async def calibrate_mpu6050(i2c):
    num_samples = 2000
    ax_offset, ay_offset, az_offset = 0, 0, 0
    gc.collect()
    
    for _ in range(num_samples):
        try:
            ax = read_i2c_word(i2c, 0x3B)
            ay = read_i2c_word(i2c, 0x3D)
            az = read_i2c_word(i2c, 0x3F)
            ax_offset += ax
            ay_offset += ay
            az_offset += az
        except Exception as e:
            print(f"Calibration error: {str(e)}")  # Use `str()` to safely convert the exception to a string
            ax, ay, az = 0, 0, 0  # Use default values for this sample
    gc.collect()
    
    ax_offset /= num_samples
    ay_offset /= num_samples
    az_offset /= num_samples

    # Adjust for gravity on Z-axis
    az_offset -= 16384  # Assuming the device is stationary and Z is 1g.
    gc.collect()
    return ax_offset, ay_offset, az_offset


def read_i2c_word(i2c, register):
    global last_error_time
    try:
        data = i2c.readfrom_mem(MPU6050_ADDR, register, 2)
        value = (data[0] << 8) | data[1]
        if value >= 0x8000:
            value -= 0x10000
        gc.collect()
        return value
    except Exception as e:
        current_time = time.time()
        if current_time - last_error_time > 10:  # 10 seconds
            print(f"Error reading I2C register {register}: {e}")
            last_error_time = current_time
        gc.collect()
        return 0  # Return a default value to prevent further errors

async def read_temperature():
    try:
        gc.collect()
        return sensors[0].temperature
    except Exception as e:
        print(f"Error reading temperature: {e}")
        return None
    
async def trigger_calibration():
    global offsets
    try:
        print("Calibrating MPU6050...")
        offsets = await calibrate_mpu6050(i2c)  # Calibrate the sensor
        save_offsets_to_file(offsets)          # Save offsets to file
        print(f"Calibration complete: {offsets}")
    except Exception as e:
        print(f"Error during calibration: {e}")

async def ota_task():
    retries = 0
    max_retries = 5  # Maximum number of retries for OTA
    retry_interval = 120  # Retry interval in seconds
    ota_check_interval = 3600  # Interval between OTA checks in seconds (1 hour)
    
    while True:
        try:
            gc.collect()
            print("Starting OTA check...")
            
            ota_updater = OTAUpdater(SSID, PASSWORD, firmware_url, "main.py", NODE_ID)
            
            # Check for updates
            if await ota_updater.check_for_updates():
                print("Update available. Starting download...")
                ota_updater.update_and_reset()
                return  # Exit if update is successful
            else:
                print("No update available.")
                retries = 0  # Reset retries on successful check
            
        except Exception as e:
            retries += 1
            print(f"Error in OTA update: {e}. Retry {retries}/{max_retries}")
            if retries >= max_retries:
                print("Max retries reached. Skipping OTA check for now.")
                retries = 0  # Reset retries after skipping
        
        # Wait before next OTA check
        await asyncio.sleep(ota_check_interval)

async def mpu6050_task():
    """
    Dynamically detect and initialize MPU6050 sensor.
    """
    global mpu6050_initialized, offsets

    while True:
        try:
            # Detect MPU6050
            if not mpu6050_initialized and await detect_mpu6050():
                print("MPU6050 detected. Initializing...")
                try:
                    await initialize_mpu6050()
                    mpu6050_initialized = True  # Mark as initialized
                    print("MPU6050 initialization successful.")
                    
                    # Reload offsets after reinitialization
                    offsets = load_offsets_from_file()
                    print(f"Offsets reloaded: {offsets}")
                except Exception as e:
                    print(f"MPU6050 initialization failed: {e}")
                    mpu6050_initialized = False  # Reset on failure
            elif not await detect_mpu6050():
                if mpu6050_initialized:
                    print("MPU6050 disconnected!")
                mpu6050_initialized = False  # Reset if disconnected
        except Exception as e:
            print(f"Error in MPU6050 task: {e}")
            mpu6050_initialized = False  # Reset on any error

        # Delay before next detection attempt
        await asyncio.sleep(5)


async def temperature_task():
    client = None
    firmware_version = await get_firmware_version()
    
    while True:
        try:
            # Ensure client is connected before checking for MQTT messages
            if client is None:
                print("MQTT client is None, attempting to reconnect...")
                client = await connect_mqtt()
                if client is None:
                    print("Failed to reconnect MQTT client, retrying after delay.")
                    await asyncio.sleep(5)
                    continue  # Skip the rest of the loop and try reconnecting again
            
            # Check for incoming MQTT messages
            client = await check_mqtt_messages(client)
            
            # Only read accelerometer data if MPU6050 is initialized
            if mpu6050_initialized:
                try:
                    ax, ay, az = await calculate_rms(i2c, offsets)
                    if ax is None or ay is None or az is None:
                        print("Invalid accelerometer data. Skipping cycle.")
                        continue
                except Exception as e:
                    print(f"Error reading accelerometer: {e}")
                    continue
            else:
                ax, ay, az = None, None, None  # Placeholder if MPU6050 not initialized

            temperature = await read_temperature()
            if temperature is None:
                print("Invalid temperature data. Skipping cycle.")
                await asyncio.sleep(5)
                temperature = 999

            # Prepare and publish data
            data = (
                (f"N{NODE_ID}, " 
            ) +
                f"AccX: {ax:.10f}, " if ax is not None else "AccX: 0.0, "
            ) + (
                f"AccY: {ay:.10f}, " if ay is not None else "AccY: 0.0, "
            ) + (
                f"AccZ: {az:.10f}, " if az is not None else "AccZ: 0.0, "
            ) + f"Temp: {temperature:.8f}C, FW: {firmware_version}"


            
            client = await publish_data(client, data)
            #print(f"Free memory: {gc.mem_free()} bytes")
            
            # Check for MQTT messages
            #client.check_msg()  # Ensure messages are handled

            # Delay before the next cycle
            await asyncio.sleep(2)
            
        except Exception as e:
            print(f"Error in temperature task: {e}")
            # Handle specific errors
            if str(e) == "[Errno 104] ECONNRESET":
                print("MQTT connection reset by broker. Reconnecting...")
                client = await reconnect_mqtt(client)  # Reconnect the MQTT client
            elif str(e) == "-1":
                print("Error -1 detected, attempting reconnection...")
                client = await reconnect_mqtt(client)  # Attempt reconnection on -1 error
            else:
                print(f"Error in temperature task: {e}")
                await asyncio.sleep(5)  # Delay to avoid busy loop during errors
            await asyncio.sleep(5)  # Delay to avoid busy loop during errors

#async def main():
    #await asyncio.gather(ota_task(), led_blink_task(), mpu6050_task(), temperature_task())
async def auto_reboot_task(interval_hours=12):
    interval_seconds = interval_hours * 3600
    while True:
        print(f"Rebooting in {interval_hours} hours...")
        await asyncio.sleep(interval_seconds)
        print("Rebooting now...")
        machine.reset()


async def main():
    gc.collect()
    # Run independent tasks
    tasks = [
        asyncio.create_task(ota_task()),
        asyncio.create_task(mpu6050_task()),
        asyncio.create_task(temperature_task()),
        asyncio.create_task(auto_reboot_task(4)),  # Auto-reboot every 4 hours
    ]
    await asyncio.gather(*tasks)
    gc.collect()

# Start the main loop
asyncio.run(main())