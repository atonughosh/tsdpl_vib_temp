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
        self.firmware_url = self.repo_url + f'/main/node_{self.node_id}/{self.filename}'

        # Get the current version (stored in version.json) for the specific node
        version_file_path = '/version.json'
        
        # Check if the version file exists and load it, otherwise create it with version 0
        try:
            with open(version_file_path, 'r') as f:
                self.current_version = int(json.load(f)['version'])
            print(f"Current device firmware version for node {self.node_id} is '{self.current_version}'")
        except OSError:  # If the file doesn't exist, we assume it's the first boot
            self.current_version = 0
            # Save the current version as 0 in version.json
            with open(version_file_path, 'w') as f:
                json.dump({'version': self.current_version}, f)

    def connect_wifi(self):
        """ Connect to Wi-Fi with error handling. """
        sta_if = network.WLAN(network.STA_IF)
        sta_if.active(True)
        
        # Check if already connected
        if sta_if.isconnected():
            current_ssid = sta_if.config('essid')
            if current_ssid == self.ssid:
                print(f"Already connected to {self.ssid}. Skipping connection.")
                print(f'IP is: {sta_if.ifconfig()[0]}')
                return  # Skip connection if already connected to the desired SSID
            else:
                print(f"Already connected to {current_ssid}, but trying to connect to {ssid}. Reconnecting...")

        try:
            print("Connecting to WiFi...")
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

        except OSError as e:
            print(f"Error during Wi-Fi connection: {e}")
            print("Rebooting the device to attempt reconnection...")
            time.sleep(30)
            machine.reset()  # Reboot ESP32 if Wi-Fi connection fails

    def fetch_latest_code(self) -> bool:
        """ Fetch the latest code from the repo, returns False if not found."""
        response = urequests.get(self.firmware_url)
        if response.status_code == 200:
            print(f'Fetched latest firmware code, status: {response.status_code}')
            # Save the fetched code to memory
            self.latest_code = response.text
            return True
        elif response.status_code == 404:
            print(f'Firmware not found - {self.firmware_url}.')
            return False

    def update_no_reset(self):
        """ Update the code without resetting the device."""
        # Save the fetched code and update the version file to the latest version.
        with open('latest_code.py', 'w') as f:
            f.write(self.latest_code)

        # Update the version in memory
        self.current_version = self.latest_version  # Use latest_version, as it is now correctly set

        # Save the current version to version.json
        version_file_path = '/version.json'
        with open(version_file_path, 'w') as f:
            json.dump({'version': self.current_version}, f)

        # Free up some memory
        self.latest_code = None

    def update_and_reset(self):
        """ Update the code and reset the device."""
        print(f"Updating device... (Renaming latest_code.py to {self.filename})", end="")
        
        # Overwrite the old code with the updated one
        os.rename('latest_code.py', self.filename)

        # Restart the device to run the new code.
        print('Restarting device...')
        machine.reset()  # Reset the device to run the new code.

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

        finally:
            # Clean up response and data objects safely
            if response:
                response.close()  # Close the response to free resources
            if data:
                del data  # Only delete if data was assigned
            del response  # Delete response object to free up memory
            gc.collect()

        return newer_version_available  # Return False if no update is found


    def download_and_install_update_if_available(self):
        """ Check for updates, download and install them."""
        if await self.check_for_updates():
            if self.fetch_latest_code():
                self.update_no_reset()
                self.update_and_reset()
        else:
            print('No new updates available.')
