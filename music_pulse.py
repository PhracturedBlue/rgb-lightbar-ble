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
FRAMES = SAMPLE_RATE // 20  # update every 0.05 sec
HUE_DELTA = 1 / 32
BUMP_THRESHOLD = 0.2
#UPDATE = 0.1 # Frequency of BLE transmissions (in seconds)
#BINS = [10, 200, 600, 3000, 8000]

#SCALED_BINS = [_ * FRAMES // SAMPLE_RATE for _ in BINS]
#NORM_BINS = [y - x for x, y in zip(SCALED_BINS, SCALED_BINS[1:] + [FRAMES // 2 + 1])]


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
    async with BleakClient(ADDRESS) as client:
        await send_ble(client, ble_brightness(0x64))
        try:
            while True:
                hue, brightness = await que.get()
                r, g, b = [int(x*255) for x  in hsv_to_rgb(hue, 1.0, brightness)]
                await send_ble(client, ble_color(r, g, b))

                #pattern, speed = await que.get()
                #if pattern is not None:
                #    await send_ble(client, ble_pattern(pattern))
                #if speed is not None:
                #    await send_ble(client, ble_speed(speed))
        except:
            await send_ble(client, ble_color(0, 0, 0))


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
    hue = 0

    with microphone.recorder(samplerate=SAMPLE_RATE) as mic:
      while True:
        data = mic.record(numframes=FRAMES)
        now = time.time()
        data = data[0:, 0]  # Pick a channel
        orig_volume = np.sqrt(np.mean(data**2))
        if orig_volume < .0001:
            orig_volume = 0.0
        raw_max_vol = max(orig_volume, raw_max_vol, 0.001)
        volume = orig_volume / raw_max_vol  # scale to 0-1
        logging.debug(f"Volume: {volume} Orig: {orig_volume} Max: {raw_max_vol}")
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
        loop.call_soon_threadsafe(que.put_nowait, (hue, brightness))
        #last_time = now
        #maxval = np.amax(data)
        #fft = np.absolute(np.fft.rfft(data))
        #hist = np.add.reduceat(fft, SCALED_BINS)
        #hist2 = hist / NORM_BINS
        #maxidx = np.argmax(hist2)
        #pattern = 0x19 + 2*maxidx
        #speed = min(0x64, int(maxval / 0.5 * 0x64))
        #loop.call_soon_threadsafe(que.put_nowait, (pattern, speed))
        #loop.call_soon_threadsafe(que.put_nowait, (
        #    None if pattern == last_pattern else pattern,
        #    None if speed == last_speed else speed))
        #last_pattern = pattern
        #last_speed = speed
        # fig, ax = plt.subplots()
        # xf = np.linspace(0.0, 2400, len(fft))
        # ax.bar([str(_) for _ in BINS], hist2)
        # breakpoint()
        # plt.show()

async def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("mic", nargs='?', help="Speaker name")
    args = parser.parse_args()
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
    que = asyncio.Queue()
    loop = asyncio.get_event_loop()
    audio = threading.Thread(target=parse_audio, args=(loop, que, mic))
    audio.daemon = True
    audio.start()
    await handle_ble(que)
        
asyncio.run(main())
