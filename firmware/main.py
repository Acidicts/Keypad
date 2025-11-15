import supervisor

# Check if SW1 was pressed at boot - if so, don't run keyboard code
try:
    if supervisor.runtime.serial_bytes_available:
        print("SW1 was pressed at boot - keyboard disabled for file editing")
        while True:
            pass  # Infinite loop, do nothing
except:
    pass

import board
from kmk.kmk_keyboard import KMKKeyboard
from kmk.keys import KC, Key
from kmk.scanners import DiodeOrientation
from kmk.extensions.media_keys import MediaKeys
from kmk.modules.layers import Layers
import digitalio

# Keyboard configuration
keyboard = KMKKeyboard()

# Pin configuration for columns and rows
keyboard.col_pins = (board.D0, board.D1, board.D2, board.D3)
keyboard.row_pins = (board.D4, board.D5, board.D6, board.D10, board.D9)

# Diode orientation: COL2ROW means diodes point from columns to rows
keyboard.diode_orientation = DiodeOrientation.COL2ROW

# Add layers module for multiple modes
layers = Layers()
keyboard.modules.append(layers)

# Initialize RGB NeoPixel on pin 14
pixels = None
try:
    import neopixel
    # NeoPixel is on pin 14 (not board.NEOPIXEL)
    try:
        led_pin = board.D14
    except:
        # Fallback to NEOPIXEL if D14 doesn't exist
        led_pin = board.NEOPIXEL
    
    pixels = neopixel.NeoPixel(led_pin, 1, brightness=0.3, auto_write=True)
    pixels.fill((0, 0, 0))  # Start with LED off
    print(f"NeoPixel initialized on pin 14")
except Exception as e:
    print(f"NeoPixel not available: {e}")
    pixels = None

# Media keys support
keyboard.extensions.append(MediaKeys())

# Mode colors (R, G, B) values 0-255
MODE_COLORS = [
    (255, 0, 0),    # Mode 0 (Layer 0): Red - Numpad
    (0, 255, 0),    # Mode 1 (Layer 1): Green - Media Controls
    (0, 0, 255),    # Mode 2 (Layer 2): Blue - Macros/Shortcuts
]

# Manual rotary encoder implementation - only trigger on full detent
class ManualEncoder:
    def __init__(self, pin_a, pin_b):
        self.pin_a = digitalio.DigitalInOut(pin_a)
        self.pin_a.direction = digitalio.Direction.INPUT
        self.pin_a.pull = digitalio.Pull.UP
        
        self.pin_b = digitalio.DigitalInOut(pin_b)
        self.pin_b.direction = digitalio.Direction.INPUT
        self.pin_b.pull = digitalio.Pull.UP
        
        # Track state for full rotation detection
        self.last_a = self.pin_a.value
        self.position = 0
        
        print(f"Manual encoder initialized")
    
    def update(self):
        """Check encoder - only returns direction on A pin falling edge when both pins match"""
        a = self.pin_a.value
        b = self.pin_b.value
        
        # Only detect on falling edge of pin A
        if self.last_a and not a:
            self.last_a = a
            # Check pin B to determine direction
            if b:
                return -1  # Counter-clockwise
            else:
                return 1   # Clockwise
        
        self.last_a = a
        return 0

# Create manual encoder instance
manual_encoder = ManualEncoder(board.D8, board.D7)

# Current mode tracking
class ModeManager:
    def __init__(self):
        self.current_mode = 0
        self.mode_select_active = False
        self.initialized = False
        self.counter = 0
        self.blink_counter = 0
        self.blink_state = False
        self.pending_key_release = None
        self.release_counter = 0
    
    def set_mode_color(self):
        """Update LED color based on current mode"""
        if pixels:
            try:
                color = MODE_COLORS[self.current_mode % len(MODE_COLORS)]
                pixels.fill(color)
                pixels.show()
                print(f"LED set to mode {self.current_mode}: {color}")
            except Exception as e:
                print(f"LED error: {e}")
    
    def update_blink(self):
        """Handle LED blinking in mode select"""
        if self.mode_select_active and pixels:
            self.blink_counter += 1
            if self.blink_counter >= 30:  # Blink every ~30 scans (about 0.3s)
                self.blink_counter = 0
                self.blink_state = not self.blink_state
                try:
                    if self.blink_state:
                        pixels.fill(MODE_COLORS[self.current_mode])
                    else:
                        pixels.fill((0, 0, 0))
                    pixels.show()
                except:
                    pass
    
    def cycle_mode(self, direction):
        """Cycle through modes when encoder is rotated during mode selection"""
        if self.mode_select_active:
            if direction > 0:  # Clockwise
                self.current_mode = (self.current_mode + 1) % 3
            else:  # Counter-clockwise
                self.current_mode = (self.current_mode - 1) % 3
            print(f"Mode changed to: {self.current_mode}")
            self.set_mode_color()
            keyboard.active_layers = [self.current_mode]
            return True
        return False
    
    def toggle_mode_select(self):
        """Toggle mode selection on/off"""
        self.mode_select_active = not self.mode_select_active
        self.blink_counter = 0
        self.blink_state = False
        print(f"Mode select: {self.mode_select_active}")
        if not self.mode_select_active:
            # Exiting mode select - set solid color
            self.set_mode_color()
    
    def check_init(self):
        """Check if we should initialize the color"""
        if not self.initialized:
            self.counter += 1
            if self.counter > 10:  # Wait for a few scan cycles
                self.set_mode_color()
                self.initialized = True
    
    def handle_key_release(self):
        """Handle auto-release of encoder keys"""
        if self.pending_key_release:
            self.release_counter += 1
            if self.release_counter >= 2:  # Release after 2 scans
                keyboard.remove_key(self.pending_key_release)
                self.pending_key_release = None
                self.release_counter = 0

mode_manager = ModeManager()

# Create a custom key class for mode selection
class ModeSelectKey(Key):
    def __init__(self):
        super().__init__()
    
    def on_press(self, keyboard, coord_int=None, coord_raw=None):
        mode_manager.toggle_mode_select()
        return False
    
    def on_release(self, keyboard, coord_int=None, coord_raw=None):
        return False

KC.MODE_SELECT = ModeSelectKey()

# Keymap - 3 layers (modes)
keyboard.keymap = [
    # LAYER 0: NUMPAD MODE (RED)
    [
        KC.N7,         KC.N8,         KC.NO,         KC.MODE_SELECT,     # Row 0
        KC.N4,         KC.N5,         KC.N6,         KC.PLUS,            # Row 1
        KC.N1,         KC.N2,         KC.N3,         KC.MINS,            # Row 2
        KC.N0,         KC.DOT,        KC.ENT,        KC.NO,              # Row 3
        KC.BSPC,       KC.PAST,       KC.PSLS,       KC.EQL,             # Row 4
    ],
    
    # LAYER 1: MEDIA CONTROL MODE (GREEN)
    [
        KC.MPRV,       KC.MPLY,       KC.NO,         KC.MODE_SELECT,     # Row 0
        KC.NO,         KC.NO,         KC.NO,         KC.MNXT,            # Row 1
        KC.NO,         KC.NO,         KC.NO,         KC.MUTE,            # Row 2
        KC.NO,         KC.NO,         KC.NO,         KC.NO,              # Row 3
        KC.NO,         KC.NO,         KC.NO,         KC.NO,              # Row 4
    ],
    
    # LAYER 2: MACRO/SHORTCUT MODE (BLUE)
    [
        KC.F13,        KC.F14,        KC.NO,         KC.MODE_SELECT,     # Row 0
        KC.F15,        KC.F16,        KC.F17,        KC.F18,             # Row 1
        KC.F19,        KC.F20,        KC.F21,        KC.F22,             # Row 2
        KC.LCTL(KC.C), KC.LCTL(KC.V), KC.LCTL(KC.Z), KC.NO,              # Row 3
        KC.LCTL(KC.S), KC.LCTL(KC.A), KC.LCTL(KC.X), KC.LCTL(KC.Y),     # Row 4
    ],
]

# Hook into before_matrix_scan to handle encoder, LED blinking and initialization
def custom_before_matrix_scan():
    mode_manager.check_init()
    mode_manager.update_blink()
    mode_manager.handle_key_release()
    
    # Check encoder
    direction = manual_encoder.update()
    if direction != 0:
        if mode_manager.mode_select_active:
            # In mode select - cycle modes
            mode_manager.cycle_mode(direction)
        else:
            # Normal mode - send volume keys with auto-release
            # First release any pending key
            if mode_manager.pending_key_release:
                keyboard.remove_key(mode_manager.pending_key_release)
            
            # Add the new key
            if direction > 0:
                keyboard.add_key(KC.VOLU)
                mode_manager.pending_key_release = KC.VOLU
            else:
                keyboard.add_key(KC.VOLD)
                mode_manager.pending_key_release = KC.VOLD
            
            mode_manager.release_counter = 0

keyboard.before_matrix_scan = custom_before_matrix_scan

print("Manual encoder ready!")

if __name__ == '__main__':
    keyboard.go()