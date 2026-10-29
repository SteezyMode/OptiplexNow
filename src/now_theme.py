"""Shared NOW GTK3 palette for optional Python host/client dialogs."""
from pathlib import Path

def install():
    import gi
    gi.require_version("Gtk", "3.0")
    from gi.repository import Gdk, Gtk
    screen = Gdk.Screen.get_default()
    if screen is None:
        return False
    for candidate in (
        Path("/usr/lib/optiplex-now/now-theme.css"),
        Path(__file__).resolve().parent / "now-theme.css",
    ):
        if candidate.is_file():
            provider = Gtk.CssProvider()
            provider.load_from_path(str(candidate))
            Gtk.StyleContext.add_provider_for_screen(
                screen, provider, Gtk.STYLE_PROVIDER_PRIORITY_APPLICATION)
            return True
    return False
