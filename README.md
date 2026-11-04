# Kilix Power Controls

The Kilix GUI for desktop power preferences. It replaces the Xfce settings
window while using the existing desktop power service. Opening the app makes
no changes. Apply writes only edited preferences; Reload discards the power
draft and reads the current settings.

Pages cover button actions, separate plugged-in and battery lid/sleep/profile
policies, critical battery behavior, display power, dimming, and power-supply
devices. Sleep actions and power profiles depend on hardware and system support.
The **Screen Lock** page is shared with Pleb Display Settings. Its Save button
stores per-user automatic lock preferences for the next login; manual locking
remains available. `kilix tui screen-lock` edits those same preferences.

Launch with `kilix power-controls` or `pleb devices power` for a Kilix app pane.
`kilix-power-controls --native` opens a window on the current display; `--show`
prints power preferences without opening a window. Install through the pinned
Kilix content catalog (`kilix app install kilix-power-controls`).

Requires Linux/X11, Python 3, Tk, python3-dbus, xfconf, the desktop power service,
and Pleb with the shared Screen Lock settings module. Inside a private app
display, the host desktop bus must be available as `PLEB_DESKTOP_BUS_ADDRESS`.
No privileged command, daemon restart, suspend or power-off occurs in this app.

Setting keys and action values follow the
[Xfce 4.20 power service configuration](https://github.com/xfce-mirror/xfce4-power-manager/blob/xfce4-power-manager-4.20.0/common/xfpm-config.h)
and its [action enums](https://github.com/xfce-mirror/xfce4-power-manager/blob/xfce4-power-manager-4.20.0/common/xfpm-enum-glib.h).
Unrecognized settings are preserved. If another window changes an edited
preference, Apply asks you to reload instead of overwriting it. A failed write
attempts to restore the previous values and reports any restoration failure.

Run tests with `/usr/bin/python3 -m unittest discover -s tests -v`.
