import sys
import time
import asyncio
import threading
import logging
import argparse
from colorsys import hsv_to_rgb

import soundcard as sc
from bleak import BleakClient
import numpy as np
#import matplotlib.pyplot as plt

ADDRESS = "BE:16:A3:00:13:A9"
ENDPOINT = "0000fff3-0000-1000-8000-00805f9b34fb"

SAMPLE_RATE = 24000
SAMPLES_PER_SEC = 20
FRAMES = SAMPLE_RATE // SAMPLES_PER_SEC # update every 0.05 sec
HUE_DELTA = 1 / 32
BUMP_THRESHOLD = 0.2
#UPDATE = 0.1 # Frequency of BLE transmissions (in seconds)
#BINS = [10, 200, 600, 3000, 8000]

#SCALED_BINS = [_ * FRAMES // SAMPLE_RATE for _ in BINS]
#NORM_BINS = [y - x for x, y in zip(SCALED_BINS, SCALED_BINS[1:] + [FRAMES // 2 + 1])]
BLE_STATE = False

def ble_brightness(brightness):
    return bytearray([0x7e, 0x04, 0x01, brightness, 0xff, 0xff, 0xff, 0x00, 0xef])

def ble_pattern(pattern):
    return bytearray([0x7e, 0x05, 0x03, pattern, 0x06, 0xff, 0xff, 0x00, 0xef])

def ble_speed(speed):
    return bytearray([0x7e, 0x04, 0x02, speed, 0xff, 0xff, 0xff, 0x00, 0xef])

def ble_color(r, g, b):
    return bytearray([0x7e, 0x04, 0x05, 0x03, r, g, b, 0x10, 0xef])
    
async def send_ble(client, data):
    #print([hex(_) for _ in data])
    await client.write_gatt_char(ENDPOINT, data)
    
async def handle_ble(que):
    global BLE_STATE
    while True:
        try:
            async with BleakClient(ADDRESS) as client:
                logging.debug("Connected BLE")
                while que.qsize():
                    await que.get()
                BLE_STATE = True
                try:
                    await send_ble(client, ble_brightness(0x64))
                    while True:
                        hue, brightness = await que.get()
                        r, g, b = [int(x*255) for x  in hsv_to_rgb(hue, 1.0, brightness)]
                        await send_ble(client, ble_color(r, g, b))
                finally:
                    logging.debug("Blanking device")
                    await send_ble(client, ble_color(0, 0, 0))
                    BLE_STATE = False
        except Exception as _e:
            logging.error("Got exception: %s", _e)
            pass
        finally:
            logging.debug("Disconnecting BLE")
            BLE_STATE = False

def que_put_nowait(args):
    try:
        if BLE_STATE:
            args[0].put_nowait(tuple(args[1:]))
    except asyncio.QueueFull:
        pass

def parse_audio(loop, que, microphone):
    fft_elems = FRAMES // 2 + 1
    last_time = 0
    last_speed = 0
    last_pattern = 0
    last_volume = 0
    raw_max_vol = 0
    avg_volume = 0
    max_volume = 0.5
    avg_bump = 0
    avg_bump_time = 0
    time_bump = 0
    last_hue = 0
    last_brightness = 0
    hue = 0
    no_sound = 0
    quiet = False
    while True:
        if not BLE_STATE:
            logging.debug("BLE not connected")
            time.sleep(2)
            continue
        if quiet:
            logging.debug("no sound present")
            time.sleep(2)
        quiet = False
        with microphone.recorder(samplerate=SAMPLE_RATE) as mic:
            while BLE_STATE:
                data = mic.record(numframes=FRAMES)
                now = time.time()
                data = data[0:, 0]  # Pick a channel
                orig_volume = np.sqrt(np.mean(data**2))
                if orig_volume == 0:
                    no_sound += 1
                    if no_sound >= 120 * SAMPLES_PER_SEC:
                        quiet = True
                        break
                else:
                    no_sound = 0
                if orig_volume < .0001:
                    orig_volume = 0.0
                raw_max_vol = max(orig_volume, raw_max_vol, 0.001)
                volume = orig_volume / raw_max_vol  # scale to 0-1
                logging.debug(f"BLE: {BLE_STATE} Volume: {volume} Orig: {orig_volume} Max: {raw_max_vol} Quiet: {no_sound}")
                raw_max_vol = raw_max_vol * 0.995
                avg_volume = (volume + avg_volume) / 2
                max_volume = max(max_volume, volume)
                if volume - last_volume > BUMP_THRESHOLD:
                    avg_bump = (avg_bump + (volume - last_volume)) / 2
                    logging.debug(f"Avg_bump: {avg_bump}")

                bump = volume - last_volume > avg_bump * 0.9
                if bump:
                    logging.debug(f"Bump: avg: {avg_volume} volume: {volume}")
                    avg_bump_time = (avg_bump_time + now - time_bump) / 2
                    time_bump = now
                    hue = hue + HUE_DELTA
                    if hue >= 1:
                        hue -= 1.0
                if max_volume == 0:
                    brightness = 0
                else:
                    brightness = volume / max_volume
                max_volume = max_volume * 0.9
                if hue != last_hue or brightness != last_brightness:
                    loop.call_soon_threadsafe(que_put_nowait, (que, hue, brightness))
                last_hue == hue
                last_brightness = brightness

async def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("mic", nargs='?', help="Speaker name")
    parser.add_argument("--debug", action='store_true', help="Debug Logs")
    args = parser.parse_args()
    logging.basicConfig(level=logging.DEBUG if args.debug else logging.INFO)
    mics = sc.all_microphones(include_loopback=True)
    if args.mic:
        mic = next((_ for _ in mics if _.isloopback and args.mic in _.name), None)
    else:
        mic = None
    if not mic:
        logging.error("Select one of the following speakers:")
        for mic in mics:
            if mic.isloopback:
                logging.error("\t%s", mic.name)
        sys.exit(1)
    que = asyncio.Queue(10)
    loop = asyncio.get_event_loop()
    audio = threading.Thread(target=parse_audio, args=(loop, que, mic))
    audio.daemon = True
    audio.start()
    await handle_ble(que)

try:
    asyncio.run(main())
except KeyboardInterrupt:
    pass
