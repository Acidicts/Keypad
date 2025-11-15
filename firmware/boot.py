import usb_hid
import board
import digitalio
import storage
import supervisor
import time

# Enable USB HID devices
usb_hid.enable(
    (usb_hid.Device.KEYBOARD,
     usb_hid.Device.CONSUMER_CONTROL)
)

# SW1 is at position (Col 3, Row 0)
# Col 3 = D3, Row 0 = D4
# Diodes are Col to Row (COL2ROW)
col3_pin = board.D3
row0_pin = board.D4

# Set up row pin as output (drive it LOW)
row0 = digitalio.DigitalInOut(row0_pin)
row0.direction = digitalio.Direction.OUTPUT
row0.value = False  # Drive row LOW

# Set up column pin as input with pullup
col3 = digitalio.DigitalInOut(col3_pin)
col3.direction = digitalio.Direction.INPUT
col3.pull = digitalio.Pull.UP

# Small delay to let pins stabilize
time.sleep(0.01)

# Read the column
# If SW1 is pressed, col3 will be pulled LOW through the diode
# If SW1 is NOT pressed, col3 will stay HIGH (pulled up)
button_pressed = not col3.value

# Clean up
col3.deinit()
row0.deinit()

if button_pressed:
    # Button pressed - enable USB drive and prevent code from running
    print("SW1 pressed at boot - USB drive enabled, main.py disabled")
    supervisor.disable_autoreload()
    # Don't disable USB drive so we can edit files
else:
    # Button not pressed - disable USB drive and run normally
    storage.disable_usb_drive()
    print("USB drive disabled - running normally")

# Store button state in supervisor runtime for main.py to check
supervisor.runtime.serial_bytes_available = button_pressed