import ctypes
import ctypes.util
from ctypes import (
    CFUNCTYPE, POINTER, Structure, Union, byref, c_char_p, c_double, c_int, c_long, c_ubyte, c_uint, c_ulong, c_void_p,
)


# Minimal ctypes bindings for libX11, libXi (XInput2) and libXtst (XTest)

def _load(name):
    path = ctypes.util.find_library(name)
    if not path:
        raise OSError(f"lib{name} not found; install the {name} runtime library")
    return ctypes.CDLL(path)


xlib = _load("X11")
xi = _load("Xi")
xtst = _load("Xtst")

Display_p = c_void_p
Window = c_ulong
Atom = c_ulong
Time = c_ulong
Bool = c_int

# Core event types and masks
KeyPress = 2
GenericEvent = 35

ShiftMask = 1 << 0
LockMask = 1 << 1
ControlMask = 1 << 2
Mod1Mask = 1 << 3  # Alt
Mod2Mask = 1 << 4  # Num Lock
Mod4Mask = 1 << 6  # Super

GrabModeAsync = 1

# XInput2
XIAllDevices = 0
XIAllMasterDevices = 1

XI_RawKeyPress = 13
XI_RawKeyRelease = 14
XI_RawButtonPress = 15
XI_RawMotion = 17

XIMasterPointer = 1
XISlavePointer = 3
XIFloatingSlave = 5

XIValuatorClass = 2
XIModeAbsolute = 1

XIAttachSlave = 3
XIDetachSlave = 4


class XKeyEvent(Structure):
    _fields_ = [
        ("type", c_int),
        ("serial", c_ulong),
        ("send_event", Bool),
        ("display", Display_p),
        ("window", Window),
        ("root", Window),
        ("subwindow", Window),
        ("time", Time),
        ("x", c_int),
        ("y", c_int),
        ("x_root", c_int),
        ("y_root", c_int),
        ("state", c_uint),
        ("keycode", c_uint),
        ("same_screen", Bool),
    ]


class XGenericEventCookie(Structure):
    _fields_ = [
        ("type", c_int),
        ("serial", c_ulong),
        ("send_event", Bool),
        ("display", Display_p),
        ("extension", c_int),
        ("evtype", c_int),
        ("cookie", c_uint),
        ("data", c_void_p),
    ]


class XEvent(Union):
    _fields_ = [
        ("type", c_int),
        ("xkey", XKeyEvent),
        ("xcookie", XGenericEventCookie),
        ("pad", c_long * 24),
    ]


class XErrorEvent(Structure):
    _fields_ = [
        ("type", c_int),
        ("display", Display_p),
        ("resourceid", c_ulong),
        ("serial", c_ulong),
        ("error_code", c_ubyte),
        ("request_code", c_ubyte),
        ("minor_code", c_ubyte),
    ]


class XIEventMask(Structure):
    _fields_ = [
        ("deviceid", c_int),
        ("mask_len", c_int),
        ("mask", POINTER(c_ubyte)),
    ]


class XIValuatorState(Structure):
    _fields_ = [
        ("mask_len", c_int),
        ("mask", POINTER(c_ubyte)),
        ("values", POINTER(c_double)),
    ]


class XIRawEvent(Structure):
    _fields_ = [
        ("type", c_int),
        ("serial", c_ulong),
        ("send_event", Bool),
        ("display", Display_p),
        ("extension", c_int),
        ("evtype", c_int),
        ("time", Time),
        ("deviceid", c_int),
        ("sourceid", c_int),
        ("detail", c_int),
        ("flags", c_int),
        ("valuators", XIValuatorState),
        ("raw_values", POINTER(c_double)),
    ]


class XIAnyClassInfo(Structure):
    _fields_ = [
        ("type", c_int),
        ("sourceid", c_int),
    ]


class XIValuatorClassInfo(Structure):
    _fields_ = [
        ("type", c_int),
        ("sourceid", c_int),
        ("number", c_int),
        ("label", Atom),
        ("min", c_double),
        ("max", c_double),
        ("value", c_double),
        ("resolution", c_int),
        ("mode", c_int),
    ]


class XIDeviceInfo(Structure):
    _fields_ = [
        ("deviceid", c_int),
        ("name", c_char_p),
        ("use", c_int),
        ("attachment", c_int),
        ("enabled", Bool),
        ("num_classes", c_int),
        ("classes", POINTER(POINTER(XIAnyClassInfo))),
    ]


class XIAddMasterInfo(Structure):
    _fields_ = [
        ("type", c_int),
        ("name", c_char_p),
        ("send_core", Bool),
        ("enable", Bool),
    ]


class XIAttachSlaveInfo(Structure):
    _fields_ = [
        ("type", c_int),
        ("deviceid", c_int),
        ("new_master", c_int),
    ]


class XIDetachSlaveInfo(Structure):
    _fields_ = [
        ("type", c_int),
        ("deviceid", c_int),
    ]


class XIAnyHierarchyChangeInfo(Union):
    _fields_ = [
        ("type", c_int),
        ("add", XIAddMasterInfo),
        ("attach", XIAttachSlaveInfo),
        ("detach", XIDetachSlaveInfo),
    ]


XErrorHandler = CFUNCTYPE(c_int, Display_p, POINTER(XErrorEvent))


def _fn(lib, name, restype, *argtypes):
    f = getattr(lib, name)
    f.restype = restype
    f.argtypes = list(argtypes)
    return f


XInitThreads = _fn(xlib, "XInitThreads", c_int)
XOpenDisplay = _fn(xlib, "XOpenDisplay", Display_p, c_char_p)
XCloseDisplay = _fn(xlib, "XCloseDisplay", c_int, Display_p)
XDefaultRootWindow = _fn(xlib, "XDefaultRootWindow", Window, Display_p)
XDefaultScreen = _fn(xlib, "XDefaultScreen", c_int, Display_p)
XDisplayWidth = _fn(xlib, "XDisplayWidth", c_int, Display_p, c_int)
XDisplayHeight = _fn(xlib, "XDisplayHeight", c_int, Display_p, c_int)
XConnectionNumber = _fn(xlib, "XConnectionNumber", c_int, Display_p)
XFlush = _fn(xlib, "XFlush", c_int, Display_p)
XSync = _fn(xlib, "XSync", c_int, Display_p, Bool)
XPending = _fn(xlib, "XPending", c_int, Display_p)
XNextEvent = _fn(xlib, "XNextEvent", c_int, Display_p, POINTER(XEvent))
XGetEventData = _fn(xlib, "XGetEventData", Bool, Display_p, POINTER(XGenericEventCookie))
XFreeEventData = _fn(xlib, "XFreeEventData", None, Display_p, POINTER(XGenericEventCookie))
XQueryExtension = _fn(xlib, "XQueryExtension", Bool, Display_p, c_char_p, POINTER(c_int), POINTER(c_int), POINTER(c_int))
XStringToKeysym = _fn(xlib, "XStringToKeysym", c_ulong, c_char_p)
XKeysymToKeycode = _fn(xlib, "XKeysymToKeycode", c_ubyte, Display_p, c_ulong)
XGrabKey = _fn(xlib, "XGrabKey", c_int, Display_p, c_int, c_uint, Window, Bool, c_int, c_int)
XUngrabKey = _fn(xlib, "XUngrabKey", c_int, Display_p, c_int, c_uint, Window)
XQueryPointer = _fn(
    xlib, "XQueryPointer", Bool,
    Display_p, Window, POINTER(Window), POINTER(Window), POINTER(c_int), POINTER(c_int), POINTER(c_int), POINTER(c_int), POINTER(c_uint))
XSetErrorHandler = _fn(xlib, "XSetErrorHandler", c_void_p, XErrorHandler)

XIQueryVersion = _fn(xi, "XIQueryVersion", c_int, Display_p, POINTER(c_int), POINTER(c_int))
XISelectEvents = _fn(xi, "XISelectEvents", c_int, Display_p, Window, POINTER(XIEventMask), c_int)
XIQueryDevice = _fn(xi, "XIQueryDevice", POINTER(XIDeviceInfo), Display_p, c_int, POINTER(c_int))
XIFreeDeviceInfo = _fn(xi, "XIFreeDeviceInfo", None, POINTER(XIDeviceInfo))
XIChangeHierarchy = _fn(xi, "XIChangeHierarchy", c_int, Display_p, POINTER(XIAnyHierarchyChangeInfo), c_int)

XTestQueryExtension = _fn(xtst, "XTestQueryExtension", Bool, Display_p, POINTER(c_int), POINTER(c_int), POINTER(c_int), POINTER(c_int))
XTestFakeMotionEvent = _fn(xtst, "XTestFakeMotionEvent", c_int, Display_p, c_int, c_int, c_int, c_ulong)
XTestFakeButtonEvent = _fn(xtst, "XTestFakeButtonEvent", c_int, Display_p, c_uint, Bool, c_ulong)
XTestFakeKeyEvent = _fn(xtst, "XTestFakeKeyEvent", c_int, Display_p, c_uint, Bool, c_ulong)


# X errors (such as a key already grabbed by another app) are ignored instead of exiting the process
@XErrorHandler
def _ignore_error(display, event):
    return 0


def init():
    XInitThreads()
    XSetErrorHandler(_ignore_error)


def open_display():
    display = XOpenDisplay(None)
    if not display:
        raise RuntimeError("Can't open the X display. MouseMe needs an X11 session (not Wayland).")
    return display


def keycode(display, keysym_name):
    return XKeysymToKeycode(display, XStringToKeysym(keysym_name.encode()))


def query_pointer(display):
    root = XDefaultRootWindow(display)
    root_ret, child = Window(), Window()
    x, y, wx, wy = c_int(), c_int(), c_int(), c_int()
    mask = c_uint()
    XQueryPointer(display, root, byref(root_ret), byref(child), byref(x), byref(y), byref(wx), byref(wy), byref(mask))
    return x.value, y.value


def has_extensions(display):
    opcode, event, error = c_int(), c_int(), c_int()
    if not XQueryExtension(display, b"XInputExtension", byref(opcode), byref(event), byref(error)):
        return False

    major, minor = c_int(2), c_int(2)
    if XIQueryVersion(display, byref(major), byref(minor)) != 0:
        return False

    return bool(XTestQueryExtension(display, byref(event), byref(error), byref(major), byref(minor)))


def xi_opcode(display):
    opcode, event, error = c_int(), c_int(), c_int()
    XQueryExtension(display, b"XInputExtension", byref(opcode), byref(event), byref(error))
    return opcode.value


class Device:
    def __init__(self, info):
        self.id = info.deviceid
        self.name = info.name.decode(errors="replace")
        self.use = info.use
        self.attachment = info.attachment
        self.absolute = False

        for i in range(info.num_classes):
            cls = info.classes[i].contents
            if cls.type == XIValuatorClass:
                valuator = ctypes.cast(info.classes[i], POINTER(XIValuatorClassInfo)).contents
                if valuator.number in (0, 1) and valuator.mode == XIModeAbsolute:
                    self.absolute = True

    @property
    def is_xtest(self):
        return "XTEST" in self.name


def devices(display):
    count = c_int()
    infos = XIQueryDevice(display, XIAllDevices, byref(count))
    try:
        return [Device(infos[i]) for i in range(count.value)]
    finally:
        XIFreeDeviceInfo(infos)


def change_hierarchy(display, changes):
    if not changes:
        return

    array = (XIAnyHierarchyChangeInfo * len(changes))()
    for i, change in enumerate(changes):
        array[i] = change

    XIChangeHierarchy(display, array, len(changes))
    XSync(display, False)


def detach(device_id):
    change = XIAnyHierarchyChangeInfo()
    change.detach = XIDetachSlaveInfo(XIDetachSlave, device_id)
    return change


def attach(device_id, master_id):
    change = XIAnyHierarchyChangeInfo()
    change.attach = XIAttachSlaveInfo(XIAttachSlave, device_id, master_id)
    return change
