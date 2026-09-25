import argparse
import atexit
import os
import signal
import sys

from . import x11

_ICON = os.path.join(os.path.dirname(os.path.abspath(__file__)), "icon.png")


def main():
    parser = argparse.ArgumentParser(prog="mouseme", description="MouseMe for Linux (X11)")
    parser.add_argument("--debug", action="store_true", help="print the position of every left click, for finding QI coordinates")
    args = parser.parse_args()

    if os.environ.get("XDG_SESSION_TYPE") == "wayland" or (os.environ.get("WAYLAND_DISPLAY") and not os.environ.get("DISPLAY")):
        sys.exit("MouseMe needs an X11 session. Log out and pick \"Ubuntu on Xorg\" on the login screen.")

    # Must come before GTK opens its own display connection
    x11.init()

    display = x11.open_display()
    try:
        if not x11.has_extensions(display):
            sys.exit("MouseMe needs the X server's XInput2 and XTEST extensions.")
    finally:
        x11.XCloseDisplay(display)

    import gi
    gi.require_version("Gtk", "3.0")
    gi.require_version("Gdk", "3.0")
    from gi.repository import GLib, Gtk

    from .engine import Engine
    from .event_tap import EventTap
    from .main_window import MainWindow
    from .settings import Settings

    GLib.set_prgname("mouseme")
    GLib.set_application_name("MouseMe")

    engine = Engine(debug=args.debug)
    engine.event_tap = EventTap(
        on_key_down=lambda key: engine.post(engine.handle_key_down, key),
        on_left_click=lambda x, y, injected: engine.post(engine.handle_left_click, x, y, injected),
    )
    engine.start_thread()
    engine.event_tap.start()

    # Never leave the physical mouse detached or QI keys grabbed once MouseMe exits
    atexit.register(engine.call, engine.release_input)

    window = MainWindow(engine, Settings(), icon_path=_ICON)
    engine.controller = window
    window.show_all()

    for sig in (signal.SIGINT, signal.SIGTERM, signal.SIGHUP):
        GLib.unix_signal_add(GLib.PRIORITY_DEFAULT, sig, Gtk.main_quit)

    Gtk.main()


if __name__ == "__main__":
    main()
