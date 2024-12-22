
"""
SPI Bus Device
====================================================
"""
class SPIDevice:
    """
    Represents a single SPI device and manages locking the bus and the device
    address.
    :param ~busio.SPI spi: The SPI bus the device is on
    :param ~digitalio.DigitalInOut chip_select: The chip select pin object that implements the
        DigitalInOut API.
    :param int extra_clocks: The minimum number of clock cycles to cycle the bus after CS is high.
        (Used for SD cards.)
    .. note:: This class is **NOT** built into CircuitPython. See
          :ref:`here for install instructions <bus_device_installation>`.
    Example:
    .. code-block:: python
        import busio
        import digitalio
        from board import *
        from adafruit_bus_device.spi_device import SPIDevice
        with busio.SPI(SCK, MOSI, MISO) as spi_bus:
            cs = digitalio.DigitalInOut(D10)
            device = SPIDevice(spi_bus, cs)
            bytes_read = bytearray(4)
            # The object assigned to spi in the with statements below
            # is the original spi_bus object. We are using the busio.SPI
            # operations busio.SPI.readinto() and busio.SPI.write().
            with device as spi:
                spi.readinto(bytes_read)
            # A second transaction
            with device as spi:
                spi.write(bytes_read)
    """
    def __init__(self, spi, chip_select, *, baudrate=100000, polarity=0, phase=0, extra_clocks=0):
        self.spi = spi
        self.chip_select = chip_select
        self.baudrate = baudrate
        self.polarity = polarity
        self.phase = phase
        self.extra_clocks = extra_clocks

    def __enter__(self):
        # Locking has been disabled (for now) as MicroPython SPI object does not support it
        # while not self.spi.try_lock():
        #     pass
        # self.spi.configure(baudrate=self.baudrate, polarity=self.polarity, phase=self.phase)
        self.chip_select.value(0)
        return self.spi

    def __exit__(self, *exc):
        self.chip_select.value(1)
        if self.extra_clocks > 0:
            buf = bytearray(1)
            buf[0] = 0xff
            clocks = self.extra_clocks // 8
            if self.extra_clocks % 8 != 0:
                clocks += 1
            for _ in range(clocks):
                self.spi.write(buf)
        # Locking has been disabled (for now) as MicroPython SPI object does not support it
        # self.spi.unlock()
        return False