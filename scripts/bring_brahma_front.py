import ctypes
from ctypes import wintypes
import sys

EnumWindows = ctypes.windll.user32.EnumWindows
EnumWindowsProc = ctypes.WINFUNCTYPE(ctypes.c_bool, ctypes.c_void_p, ctypes.c_void_p)
GetWindowText = ctypes.windll.user32.GetWindowTextW
GetWindowTextLength = ctypes.windll.user32.GetWindowTextLengthW
IsWindowVisible = ctypes.windll.user32.IsWindowVisible
SetForegroundWindow = ctypes.windll.user32.SetForegroundWindow
ShowWindow = ctypes.windll.user32.ShowWindow

results = []

def foreach_window(hwnd, lParam):
    if not IsWindowVisible(hwnd):
        return True
    length = GetWindowTextLength(hwnd)
    if length == 0:
        return True
    buf = ctypes.create_unicode_buffer(length + 1)
    GetWindowText(hwnd, buf, length + 1)
    title = buf.value
    if 'Brahma AI - Lite' in title:
        results.append(hwnd)
        return False
    return True

EnumWindows(EnumWindowsProc(foreach_window), 0)
if not results:
    print('No window found')
    sys.exit(1)

hwnd = results[0]
SW_SHOWMAXIMIZED = 3
try:
    ShowWindow(hwnd, SW_SHOWMAXIMIZED)
    SetForegroundWindow(hwnd)
    print('Brought to front')
except Exception as e:
    print('Error:', e)
    sys.exit(2)
