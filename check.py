#!/usr/bin/env python3
"""Live regression check. Moves the pointer and opens/closes the clock popup."""
import json
import pathlib
import subprocess
import time


def run(*args):
    return subprocess.check_output(args, text=True).strip()


def state():
    return json.loads(run("omarchy", "shell", "peek", "status"))


def move(x, y):
    run("hyprctl", "eval", f"hl.dispatch(hl.dsp.cursor.move({{ x = {x}, y = {y} }}))")


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


if __name__ == "__main__":
    assert state()["position"] == "top", "Set the bar to top before running"
    flag = pathlib.Path.home() / ".local/state/omarchy/toggles/bar-off"
    was_hidden = flag.exists()
    cursor = json.loads(run("hyprctl", "cursorpos", "-j"))
    monitors = json.loads(run("hyprctl", "monitors", "-j"))
    try:
        # 'on' enables the bar-off flag in Omarchy 4.0.4.
        run("omarchy", "toggle", "bar", "on")
        wait_for(lambda s: s["hidden"])
        for monitor in monitors:
            name = monitor["name"]
            x, y = monitor["x"] + 100, monitor["y"]

            def panel(s):
                return next(p for p in s["screens"] if p["name"] == name)

            move(x, y + 200)
            wait_for(lambda s: panel(s)["offset"] < 0 and not panel(s)["revealed"])
            time.sleep(0.2)
            hidden_offset = panel(state())["offset"]
            before = geometry()
            move(x, y)
            wait_for(lambda s: panel(s)["offset"] == 0 and panel(s)["revealed"])
            assert flag.exists(), "Hover changed the user's hidden preference"
            assert geometry() == before, "Hover changed client geometry or reserved space"
            layers = json.loads(run("hyprctl", "layers", "-j"))[name]["levels"]["3"]
            assert any(w["namespace"] == "omarchy-bar" and w["y"] == y for w in layers)
            move(x, y + 12)
            time.sleep(0.35)
            assert panel(state())["revealed"], "Crossing onto widgets hid the bar"
            move(x, y + 200)
            wait_for(lambda s: not panel(s)["revealed"] and panel(s)["offset"] == hidden_offset)
            assert geometry() == before, "Hiding changed client geometry or reserved space"
            print(f"PASS {name}: edge, widget hover, overlay, hide, unchanged geometry")

        # Native IPC exercises the same popup lifecycle as a widget click.
        first = monitors[0]
        move(first["x"] + 100, first["y"])
        wait_for(lambda s: any(p["revealed"] for p in s["screens"]))
        run("omarchy", "shell", "omarchy.clock", "open")
        move(first["x"] + 100, first["y"] + 100)
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
    finally:
        run("omarchy", "shell", "omarchy.clock", "close")
        run("omarchy", "toggle", "bar", "on" if was_hidden else "off")
        move(cursor["x"], cursor["y"])
