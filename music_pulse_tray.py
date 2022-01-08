"""Wrapper to create a windows sys-tray application"""
# Icon from: Designed by Razzan99 (Image #28932927 at VectorStock.com)
# To build a standalone executable using pyinstaller, the runtime-hooks must be patched
# In the pyinstaller hooks/rthooks dir, modify pyi_rth_pkgres.py and pyi_rth_win32comgenpy.py
# to add:
#   import soundcard
#   import bleak
# As per https://github.com/pyinstaller/pyinstaller/issues/6198
# Note that soundcard MUST be imported before bleak to prevent a COM error
# Executable can then be built via:
#   pyinstaller music_pulse_tray.py -F -i ringtones.ico --add-binary "ringtones.ico;."

import asyncio
import sys
import threading
import ctypes
import win32gui
import win32con
import logging
from SysTray import SysTrayIcon
from music_pulse import main as music_pulse

def bye(sysTrayIcon):
    show(sysTrayIcon)
    print('Bye, then.')

def show(sysTrayIcon):
    the_program_to_hide = ctypes.windll.kernel32.GetConsoleWindow()
    win32gui.ShowWindow(the_program_to_hide, win32con.SW_SHOW)

def hide(sysTrayIcon):
    the_program_to_hide = ctypes.windll.kernel32.GetConsoleWindow()
    win32gui.ShowWindow(the_program_to_hide, win32con.SW_HIDE)

def toggle_debug(sysTrayIcon):
    if logging.root.level == logging.DEBUG:
        logging.root.setLevel(logging.INFO)
    else:
        logging.root.setLevel(logging.DEBUG)
def run_music_pulse(event):
    try:
        asyncio.run(music_pulse(event))
    except SystemExit:
        event.STATE = False
        event.set()
    except Exception:
        logging.exception("Music Pulse failed")
        event.STATE = False
        event.set()

def main():
    event = threading.Event()
    event.STATE = True
    icon = os.path.join(os.path.dirname(os.path.abspath(__file__)), "music_pulse.ico")
    hover_text = "Music Pulse"

    menu_options = (("Show Console", None, show),
                   ("Hide Console", None, hide),
                   ("Toggle Debug", None, toggle_debug),
                   )
    mp = threading.Thread(target=run_music_pulse, args=(event,))
    mp.daemon = True
    mp.start()
    event.wait()
    if not event.STATE:
        sys.exit(1)
    if logging.root.level != logging.DEBUG:
        hide(None)
    SysTrayIcon(icon, hover_text, menu_options, on_quit=bye, default_menu_index=1)

main()
