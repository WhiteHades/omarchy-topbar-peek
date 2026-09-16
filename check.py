#!/usr/bin/env python3
"""Live regression check. Moves the pointer and opens/closes the clock popup."""
import json
import argparse
import pathlib
import subprocess
import time

from evdev import UInput, ecodes


def run(*args):
    return subprocess.check_output(args, text=True).strip()


def state():
    return json.loads(run("omarchy", "shell", "topbar-peek", "status"))


def move(x, y, pointer=None):
    run("hyprctl", "eval", f"hl.dispatch(hl.dsp.cursor.move({{ x = {x}, y = {y} }}))")
    if pointer is not None:
        # A compositor warp inside one surface does not send a Qt motion event.
        pointer.write(ecodes.EV_REL, ecodes.REL_X, 1)
        pointer.syn()


def wait_for(predicate):
    deadline = time.monotonic() + 3
    while time.monotonic() < deadline:
        current = state()
        if predicate(current):
            return current
        time.sleep(0.02)
    raise AssertionError(f"Timed out: {current}")


def geometry():
    clients = json.loads(run("hyprctl", "clients", "-j"))
    monitors = json.loads(run("hyprctl", "monitors", "-j"))
    return ({c["address"]: (c["at"], c["size"]) for c in clients},
            {m["name"]: m["reserved"] for m in monitors})


def check_tray(monitor, pointer):
    def panel(s):
        return next(p for p in s["screens"] if p["name"] == monitor["name"])

    tray = panel(state())["tray"]
    if not tray or tray["extent"] == 0:
        print(f"SKIP {monitor['name']}: no native tray drawer items")
        return
    x, y = monitor["x"], monitor["y"]
    move(x + 100, y + round(tray["height"] / 2), pointer)
    wait_for(lambda s: panel(s)["tray"]["progress"] == 0)
    # Enter the collapsed chevron, then traverse the revealed app icons.
    move(x + round(tray["x"] + tray["extent"] + tray["slot"] / 2),
         y + round(tray["y"] + tray["height"] / 2), pointer)
    wait_for(lambda s: panel(s)["tray"]["progress"] == 1)
    for offset in range(round(tray["extent"]), 0, -round(tray["slot"])):
        move(x + round(tray["x"] + offset + tray["slot"] / 2),
             y + round(tray["y"] + tray["height"] / 2), pointer)
        time.sleep(0.2)
        current = state()
        assert panel(current)["tray"]["expanded"], "Native tray lost hover over app icons"
        assert not current["hidden"] or panel(current)["revealed"], "Tray hover lost the bar"
    move(x + 100, y + round(tray["height"] / 2), pointer)
    wait_for(lambda s: panel(s)["tray"]["progress"] == 0)
    # Right-click the chevron to exercise native button and popup delivery.
    for opening in [True, False]:
        move(x + round(tray["x"] + tray["extent"] + tray["slot"] / 2),
             y + round(tray["y"] + tray["height"] / 2), pointer)
        wait_for(lambda s: panel(s)["tray"]["progress"] == 1)
        move(x + round(tray["x"] + tray["slot"] / 2),
             y + round(tray["y"] + tray["height"] / 2), pointer)
        time.sleep(0.1)
        pointer.write(ecodes.EV_KEY, ecodes.BTN_RIGHT, 1)
        pointer.syn()
        pointer.write(ecodes.EV_KEY, ecodes.BTN_RIGHT, 0)
        pointer.syn()
        wait_for(lambda s: panel(s)["tray"]["manageOpen"] == opening)
        if opening:
            move(x + 100, y + 200, pointer)
            time.sleep(0.4)
            current = state()
            assert not current["hidden"] or panel(current)["revealed"], "Tray popup lost the bar"
    move(x + 100, y + round(tray["height"] / 2), pointer)
    wait_for(lambda s: panel(s)["tray"]["progress"] == 0)
    print(f"PASS {monitor['name']}: tray hover, icons, right-click popup, collapse")

def check(monitor_name=None):
    assert state()["position"] == "top", "Set the bar to top before running"
    flag = pathlib.Path.home() / ".local/state/omarchy/toggles/bar-off"
    was_hidden = flag.exists()
    cursor = json.loads(run("hyprctl", "cursorpos", "-j"))
    monitors = json.loads(run("hyprctl", "monitors", "-j"))
    if monitor_name:
        monitors = [m for m in monitors if m["name"] == monitor_name]
        assert monitors, f"Monitor not found: {monitor_name}"
    pointer = UInput({ecodes.EV_KEY: [ecodes.BTN_LEFT, ecodes.BTN_RIGHT],
                      ecodes.EV_REL: [ecodes.REL_X, ecodes.REL_Y]},
                     name="topbar-peek-check")
    time.sleep(0.3)

    def point(x, y):
        move(x, y, pointer)

    try:
        # 'on' enables the bar-off flag in Omarchy 4.0.4.
        run("omarchy", "toggle", "bar", "on")
        wait_for(lambda s: s["hidden"])
        for monitor in monitors:
            name = monitor["name"]
            x, y = monitor["x"] + 100, monitor["y"]

            def panel(s):
                return next(p for p in s["screens"] if p["name"] == name)

            point(x, y + 200)
            wait_for(lambda s: panel(s)["offset"] < 0 and not panel(s)["revealed"])
            time.sleep(0.2)
            hidden_offset = panel(state())["offset"]
            before = geometry()
            point(x, y)
            wait_for(lambda s: panel(s)["offset"] == 0 and panel(s)["revealed"])
            assert flag.exists(), "Hover changed the user's hidden preference"
            assert geometry() == before, "Hover changed client geometry or reserved space"
            # QML animation completion precedes the compositor's frame commit,
            # especially on a headless output. Check the committed placement.
            deadline = time.monotonic() + 3
            while time.monotonic() < deadline:
                layers = json.loads(run("hyprctl", "layers", "-j"))[name]["levels"]["3"]
                if any(w["namespace"] == "omarchy-bar" and w["y"] == y for w in layers):
                    break
                time.sleep(0.02)
            else:
                raise AssertionError((name, "bar did not reach the overlay edge", layers, state(), run("hyprctl", "cursorpos", "-j")))
            physical_width = monitor["height"] if monitor["transform"] % 2 else monitor["width"]
            logical_width = round(physical_width / monitor["scale"])
            for namespace in ["omarchy-bar", "omarchy-topbar-peek-edge"]:
                surface = next(w for w in layers if w["namespace"] == namespace)
                assert (surface["x"], surface["y"], surface["w"]) == (
                    monitor["x"], y, logical_width), ("Scaled surface mismatch", surface)
            for pointer_y in [y + 12, y, y + 12]:
                point(x, pointer_y)
                time.sleep(0.4)
                actual = json.loads(run("hyprctl", "cursorpos", "-j"))
                assert abs(actual["x"] - x) <= 2 and actual["y"] == pointer_y, "Pointer moved during the check; retry while idle"
                assert panel(state())["revealed"], "Crossing onto widgets hid the bar"
            # Re-enter around the hide timer's deadline; a queued timeout
            # must not override a fresh hover event.
            for _ in range(3):
                point(x, y + 40)
                time.sleep(0.08)
                point(x, y + 12)
                time.sleep(0.2)
                assert panel(state())["revealed"], "Re-entry lost to a hide timeout"
            check_tray(monitor, pointer)
            point(x, y + 200)
            wait_for(lambda s: not panel(s)["revealed"] and panel(s)["offset"] == hidden_offset)
            assert geometry() == before, "Hiding changed client geometry or reserved space"
            print(f"PASS {name}: edge, widget hover, overlay, hide, unchanged geometry")

        if not monitor_name:
            # Clock IPC has no output selector. Targeted monitor checks use the
            # actual tray popup clicks above instead.
            first = json.loads(run("hyprctl", "monitors", "-j"))[0]
            point(first["x"] + 100, first["y"])
            wait_for(lambda s: any(p["revealed"] for p in s["screens"]))
            run("omarchy", "shell", "omarchy.clock", "open")
            point(first["x"] + 100, first["y"] + 100)
            time.sleep(0.4)
            assert any(p["revealed"] and p["held"] for p in state()["screens"])
            run("omarchy", "shell", "omarchy.clock", "close")
            wait_for(lambda s: all(not p["revealed"] for p in s["screens"]))
            print("PASS native popup holds the bar open and releases it on close")
        run("omarchy", "toggle", "bar", "off")
        wait_for(lambda s: not s["hidden"] and all(p["offset"] == 0 for p in s["screens"]))
        time.sleep(0.4)
        assert not state()["hidden"], "Pinned bar unexpectedly hid"
        print("PASS normal visible toggle stays pinned")
        for monitor in monitors:
            check_tray(monitor, pointer)
    finally:
        # Switching popouts also dismisses tray management after a failed check.
        run("omarchy", "shell", "omarchy.clock", "open")
        run("omarchy", "shell", "omarchy.clock", "close")
        run("omarchy", "toggle", "bar", "on" if was_hidden else "off")
        pointer.close()
        move(cursor["x"], cursor["y"])


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--monitor", help="check only this output, for mixed-DPI testing")
    parser.add_argument("--appearance", action="store_true",
                        help="also check opaque/transparent bars with desktop background enabled/disabled")
    args = parser.parse_args()
    if not args.appearance:
        check(args.monitor)
    else:
        config = json.loads((pathlib.Path.home() / ".config/omarchy/shell.json").read_text())
        transparent = config.get("bar", {}).get("transparent", False)
        background = "omarchy.background" not in config.get("disabledPlugins", [])
        try:
            for wallpaper in [True, False]:
                run("omarchy", "plugin", "enable" if wallpaper else "disable", "omarchy.background")
                for clear in [False, True]:
                    run("omarchy", "bar", "transparent", str(clear).lower())
                    time.sleep(0.5)
                    print(f"CHECK background={wallpaper}, transparent={clear}", flush=True)
                    check(args.monitor)
        finally:
            run("omarchy", "bar", "transparent", str(transparent).lower())
            run("omarchy", "plugin", "enable" if background else "disable", "omarchy.background")
