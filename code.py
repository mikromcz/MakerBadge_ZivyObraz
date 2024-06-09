from mb_setup import setup, get_battery
import adafruit_requests
import displayio
import wifi
import socketpool
import os
import time
import alarm
import microcontroller

# ZivyObraz API settings
# fw 1.0  - BMP
# fw 2.0  - Z2 (Aktuálně server vrací pouze formát Z2 a pouze u Obrazovek (v případě, že se ePaper hlásí jako FW 2.0))
# fw 2.1+ - Z3 (Od FW 2.1 je připravená i varianta Z3.)
fw = "2.0"

# Displej is most likely GDEM0213B74 => 4 shades of grey
# So you can play with both options. Don't forget to change on https://zivyobraz.eu/?page=muj-ucet&upravitEpaper= too!
color = "BW"  # Black and White
color = "4G"  # 4 Grey

(display, touch, led_matrix, colors) = setup(touch_enable=False, led_enable=False)


# Connect to WiFi
def connect_to_wifi(ssid, password):
    try:
        wifi.radio.connect(ssid, password)
        # print(f"Connected to {ssid}")
        return True
    except Exception:  # except Exception as e:
        # print(f"Failed to connect to {ssid}: {e}")
        return False


# Try connecting to the first network
if not connect_to_wifi(os.getenv("CIRCUITPY_WIFI_SSID"), os.getenv("CIRCUITPY_WIFI_PASSWORD")):
    # If the first network fails, try connecting to the second network
    if not connect_to_wifi(os.getenv("CIRCUITPY_WIFI_FALLBACK_SSID"), os.getenv("CIRCUITPY_WIFI_FALLBACK_PASSWORD")):
        # If both networks fail, turn off Wi-Fi
        print("Failed to connect to both networks, turning off Wi-Fi")
        wifi.radio.enabled = False
    else:
        print("Connected to backup Wi-Fi:", os.getenv("CIRCUITPY_WIFI_FALLBACK_SSID"))
else:
    print("Connected to primary Wi-Fi:", os.getenv("CIRCUITPY_WIFI_SSID"))

# ssid = wifi.radio.ap_info.ssid
# print("SSID:", ssid)

rssi = wifi.radio.ap_info.rssi
print("RSSI:", rssi)

mac_addr = ":".join([f"{i:02x}" for i in wifi.radio.mac_address])
print("MAC address:", mac_addr)

battery_voltage = get_battery()
print("Battery voltage:", battery_voltage)

URL = (
    "http://cdn.zivyobraz.eu/index.php?"
    + f"mac={mac_addr}&"
    + "timestamp_check=1&"
    # + f"ssid={ssid}&"  # We don't want to share this
    + f"rssi={rssi}&"
    + f"v={battery_voltage}&"
    + f"x={display.width}&"
    + f"y={display.height}&"
    + f"c={color}&"
    + f"fw={fw}"
)
print("URL:", URL)

pool = socketpool.SocketPool(wifi.radio)
requests = adafruit_requests.Session(pool)
resp = requests.get(URL)


def get_chunk(source, chunk_size, chunk=b""):

    # We use while loop to read the whole chunk,
    # becouse resp.iter_content() can return less bytes than requested
    while len(chunk) < chunk_size:
        chunk += source.iter_content(chunk_size=chunk_size - len(chunk)).__next__()

    return chunk


with requests.get(URL, stream=True) as resp:

    # Get headers
    try:
        sleep_time = int(resp.headers["sleep"]) * 60
        timestamp = int(resp.headers["timestamp"])
    except Exception as e:
        print(f"Exception occured, setting the default sleep time: {e}")
        sleep_time = 60 * 60
        timestamp = 0

    # Get previous timestamp from NVM
    bytes_timestamp = microcontroller.nvm[0:4]
    timestamp_old = int.from_bytes(bytes_timestamp, "little")

    print("Sleep_Time:", sleep_time, ", Timestamp:", timestamp, ", Timestamp_Old:", timestamp_old)

    if timestamp != timestamp_old:
        print("New image available!")
        
        # Read header - image format
        chunk_size = 2
        chunk = get_chunk(resp, chunk_size)
        print("Format:", chunk.decode('utf-8'))
        
        if chunk == b"Z2":
            bitmap = displayio.Bitmap(display.width, display.height, 2)
            palette = displayio.Palette(2)
            palette[0] = colors["white"]
            palette[1] = colors["black"]
            
            # position in bitmap
            i = 0
            for chunk in resp.iter_content(chunk_size=512):
                for byte in chunk:
                    count = byte & 0b00111111
                    pixel_color = (byte & 0b11000000) >> 6
                    for _ in range(count):
                        bitmap[i] = pixel_color
                        i += 1
            
        elif chunk == b"BM":
            # Read BMP header and first 4 bytes from DIB header
            # they contains size of DIB header (14 - 2 gathered + 4 bytes)
            chunk_size = 14 - 2 + 4
            data = get_chunk(resp, chunk_size)
            
            # Read the rest of DIB header (usually 40 bytes - 4 already read)
            # data[14:18] from previous chunk contains size of DIB header
            chunk_size = int.from_bytes(data[12:16], "little") - 4
            data = get_chunk(resp, chunk_size)
            
            # Extract image size and bit depth from DIB header
            width = int.from_bytes(data[0:4], "little")
            height = int.from_bytes(data[4:8], "little")
            bit_depth = int.from_bytes(data[10:12], "little")
            color_count = 2 ** bit_depth
            
            # BMP row size in bytes must be multiple of 4, so we need to pad it
            line_width_pad = (width * bit_depth + 31) // 32 * 4
            
            print("Downloaded image Width:", width, ", Height:", height, ", Bit_Depth:", bit_depth, ", Color_Count:", color_count)
            # If it returns "250 122 1 2" it is ok
            # In some cases it returns "250 122 24 16777216" eg. 24bit/16M colors and then it fails on MemoryError: memory allocation failed 
            
            # Read and process the color palette
            # (64 bytes for 16 colors, 4 bytes for each color)
            chunk_size = color_count * 4
            data = get_chunk(resp, chunk_size)
            palette = displayio.Palette(color_count)
            
            # Extract colors from the palette and convert them from BGR to RGB
            for i in range(0, len(data), 4):
                blue, green, red, _ = data[i : i + 4]
                palette[i // 4] = (red << 16) + (green << 8) + blue
            
            bitmap = displayio.Bitmap(width, height, color_count)
            
            # Process the image data row by row from bottom to top
            # Row counter
            row = 1
            
            # We try to load whole row + padding at once
            chunk_size = line_width_pad
            
            for data in resp.iter_content(chunk_size=chunk_size):
                # pixel position in the row
                index = 0
                data = get_chunk(resp, chunk_size, data)
                
                # Calculate the current row from bottom
                row_offset = (height - row) * width
                pixels_per_byte = 8 // bit_depth
                
                # Process every byte returned
                for byte in data:
                    
                    # Extract pixels from the byte based on bit depth
                    for pixel_position in range(pixels_per_byte - 1, -1, -1):
                        
                        # Calculate the shift based on the current pixel position
                        shift = pixel_position * bit_depth
                        
                        # Create a mask to isolate the pixel
                        mask = (1 << bit_depth) - 1
                        pixel = (byte >> shift) & mask
                        
                        # Set the pixel if we're not past the width of the bitmap
                        if index < width:
                            bitmap[row_offset + index] = pixel
                            index += 1
                    
                row += 1
            
        elif chunk == b"Z1":
            print("Z1 compression not supported yet")
            bitmap = displayio.Bitmap(1, 1, 1)
            
        elif chunk == b"Z3":
            print("Z3 compression not supported yet")
            bitmap = displayio.Bitmap(1, 1, 1)
            
        else:
            print("Unknown image format:", chunk)
            bitmap = displayio.Bitmap(1, 1, 1)
        
        # Send bitmap to display and shows it
        tile_grid = displayio.TileGrid(bitmap, pixel_shader=palette)
        group = displayio.Group()
        group.append(tile_grid)
        display.root_group = group
        display.refresh()
        
        while display.busy:
            pass
        
        bytes_timestamp = timestamp.to_bytes(4, "little")
        microcontroller.nvm[0:4] = bytes_timestamp
        
    else:
        print("No new image - doesn't refresh the display")

time_alarm = alarm.time.TimeAlarm(monotonic_time=time.monotonic() + sleep_time)
print(f"Good night for {sleep_time}s!")
alarm.exit_and_deep_sleep_until_alarms(time_alarm)
