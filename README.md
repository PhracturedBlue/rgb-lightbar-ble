# RGB Lightbar control
This is an example program for controlling an inexpensive lightbar (RGBIC MATICOD: https://www.amazon.com/dp/B09KBQZKNW)
via python.

It flashes the lightbar to music being played over the speakers.

This lightbar communicates over BLE.  Internally it has 32 NeoPixel LEDs, a small LiPo battery and
charge circuitry.  The microcontroller has had all markings ground off, but is in an SOIC-16 package (something very rare for a uC with BLE functionality).

#BLE commands
The BLE commands are sent to endpoint 0x0009 (characteristic: 0000fff3-0000-1000-8000-00805f9b34fb)

The following commands have been decoded:
 * Power Off: 7e0404000000ff00ef
 * RGB:       7e070503RRGGBB10ef
 * Pattern:   7e0503XX06ffff00ef 00 <= XX <= 64
 * Freeze:    7e0503XX07ffff00ef 00 <= XX <= 64
 * Bightness: 7e0401XX..ffff00ef 00 <= XX <= 64, .. has no impact (00 - ff)
 * Speed:     7e0402XXffffff00ef 00 <= XX <= 64
 * Freeze:    7e0402ffffffff00efi
 * B/W?:      7e070501XX....10ef

the 2nd and last 2 bytes seem to have no impact

#Releasing
on Windows, run `pyinstall -F music_pulse.py` to build a standalone executable

