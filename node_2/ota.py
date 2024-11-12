import network
import urequests
import os
import json
import machine
from time import sleep
import time
import gc
import uasyncio as asyncio

class OTAUpdater:
    """ This class handles OTA updates. It connects to the Wi-Fi, checks for updates, downloads and installs them."""
    def __init__(self, ssid, password, repo_url, filename, node_id):
        self.filename = filename
        self.ssid = ssid
        self.password = password
        self.repo_url = repo_url
        self.node_id = node_id  # Node ID for the specific node

        if "www.github.com" in self.repo_url:
            print(f"Updating {repo_url} to raw.githubusercontent")
            self.repo_url = self.repo_url.replace("www.github", "raw.githubusercontent")
        elif "github.com" in self.repo_url:
            print(f"Updating {repo_url} to raw.githubusercontent'")
            self.repo_url = self.repo_url.replace("github", "raw.githubusercontent")            
        
        # Use the node-specific folder in the repo URL
        self.version_url = self.repo_url + f'/main/node_{self.node_id}/version.json'
        print(f"Version URL is: {self.version_url}")
        self.firmware_url = self.repo_url + f'/main/node_{self.node_id}/firmware.tar'

        # Get the current version (stored in version.json) for the specific node
        self.version_file_path = '/version.json'
        
        # Check if the version file exists and load it, otherwise create it with version 0
        try:
            with open(self.version_file_path, 'r') as f:
                self.current_version = int(json.load(f)['version'])
            print(f"Current device firmware version for node {self.node_id} is '{self.current_version}'")
        except OSError:  # If the file doesn't exist, we assume it's the first boot
            self.current_version = 0
            # Save the current version as 0 in version.json
            with open(self.version_file_path, 'w') as f:
                json.dump({'version': self.current_version}, f)

    def connect_wifi(self):
        """ Connect to Wi-Fi with error handling. """
        sta_if = network.WLAN(network.STA_IF)
        sta_if.active(True)
        
        # Check if already connected
        if sta_if.isconnected():
            current_ssid = sta_if.config('essid')
            if current_ssid == self.ssid:
                print(f"Already connected to {self.ssid}. Skipping reconnection.")
                print(f'IP is: {sta_if.ifconfig()[0]}')
                return  True# Skip connection if already connected to the desired SSID
            else:
                print(f"Already connected to {current_ssid}, but trying to connect to {ssid}. Reconnecting...")

        try:
            print("Connecting to WiFi...")
            time.sleep(10)
            sta_if.connect(self.ssid, self.password)

            # Wait for the connection with a timeout
            timeout = 30  # Timeout in seconds
            start_time = time.time()

            while not sta_if.isconnected():
                if time.time() - start_time > timeout:
                    raise OSError("Wi-Fi connection timeout")
                print('.', end="")  # Dot to show it's trying to connect
                time.sleep(0.5)

            print(f'Connected to WiFi, IP is: {sta_if.ifconfig()[0]}')
            return True
        
        except OSError as e:
            print(f"Error during Wi-Fi connection: {e}")
            print("Rebooting the device to attempt reconnection...")
            time.sleep(30)
            machine.reset()  # Reboot ESP32 if Wi-Fi connection fails
    
    def fetch_firmware(self):
        """Download the firmware.tar.gz file."""
        print("Downloading firmware...")
        try:
            print("Firmware URL:" + self.firmware_url)
            response = urequests.get(self.firmware_url)
            if response.status_code == 200:
                with open("firmware.tar", "wb") as f:
                    f.write(response.content)
                print("Firmware downloaded successfully.")
                return True
            else:
                print(f"Failed to download firmware. Status: {response.status_code}")
        except Exception as e:
            print(f"Error downloading firmware: {e}")
        return False
    
    def extract_firmware(self):
        """Extracts the firmware.tar file to the root directory."""
        print("Extracting firmware...")
        try:
            with open("firmware.tar", "rb") as f:
                while True:
                    tar_header = f.read(512)  # Read 512-byte header blocks for tar files
                    if not tar_header or len(tar_header) < 512:
                        break
                    
                    # Extract filename and file size from the header
                    filename = tar_header[0:100].strip(b'\x00').decode()
                    file_size_str = tar_header[124:136].strip(b'\x00').decode()  # File size in octal

                    # If file_size_str is empty or invalid, skip this entry
                    if not file_size_str:
                        continue

                    try:
                        file_size = int(file_size_str, 8)  # Convert octal to decimal
                    except ValueError:
                        print(f"Invalid file size '{file_size_str}' in file {filename}, skipping file.")
                        continue  # Skip this file if the size is invalid
                    
                    if filename and file_size > 0:
                        print(f"Extracting {filename}...")
                        with open(filename, "wb") as out_file:
                            out_file.write(f.read(file_size))
                        # Move the read pointer to the next 512-byte block (pad to next multiple of 512)
                        f.read((512 - file_size % 512) % 512)

            print("Firmware extraction complete.")
            os.remove("firmware.tar")  # Clean up the downloaded file

        except Exception as e:
            print(f"Error extracting firmware: {e}")

    def update_version_file(self):
        """Update the version.json file on the ESP32."""
        try:
            with open(self.version_file_path, 'w') as f:
                json.dump({'version': self.latest_version}, f)
            print(f"Updated version.json to version {self.latest_version}")
        except Exception as e:
            print(f"Error updating version file: {e}")
            
    def update_and_reset(self):
        """Perform OTA update and reset the device if successful."""
        if self.connect_wifi() and self.fetch_firmware():
            self.extract_firmware()
            self.update_version_file()  # Update the version file with the new version
            print("Update successful! Restarting...")
            time.sleep(1)
            machine.reset()
        else:
            print("Update failed.")
    
    async def check_for_updates(self):
        """ Check if updates are available, without retry logic, only handling exceptions. """
        self.connect_wifi()
        await asyncio.sleep(30)
        gc.collect()

        latest_version = self.current_version
        newer_version_available = False
        
        response = None
        data = None

        try:
            print(f"Checking for latest version at {self.version_url}...")

            headers = {
            'Cache-Control': 'no-cache',  # Ensure no cached response is used
            }

            # Send GET request to fetch version information
            response = urequests.get(self.version_url, headers=headers)
            if response.status_code == 200:
                data = response.json()
                fetched_version = int(data.get('version', -1))
                print(f"Fetched version from server: {fetched_version}")

                if fetched_version != -1:
                    # Check if the fetched version is newer than the current version
                    self.latest_version = fetched_version
                    newer_version_available = self.current_version < self.latest_version
                    print(f'Newer version available: {newer_version_available}')

                    if newer_version_available:
                        return True  # New version available, return True
                else:
                    print("Failed to retrieve valid version data.")
            else:
                print(f"Unexpected response status: {response.status_code}")
        
        except OSError as e:
            # Handle specific network errors like ECONNABORTED
            print(f"Error checking for updates: {e}")
            if '113' in str(e):
                print("Wi-Fi connection aborted (Error 113). Consider retrying or checking Wi-Fi.")
            # Optionally, you can try to reconnect to Wi-Fi here or handle it as needed.

        
        except Exception as e:
            # Handle any error (connection issues, timeouts, etc.)
            print(f"Error checking for updates: {e}")
            if 'Errno 118' in str(e):
                self.connect_wifi()

        finally:
            # Clean up response and data objects safely
            if response:
                response.close()  # Close the response to free resources
            if data:
                del data  # Only delete if data was assigned
            del response  # Delete response object to free up memory
            gc.collect()

        return newer_version_available  # Return False if no update is found
