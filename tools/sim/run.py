#!/usr/bin/env python3
"""
Desktop simulator/launcher for Tufty 2350 badgeware apps.

Runs an app's real, unmodified source on the desktop via the badgeware shim,
in a live pygame window you can interact with -- so you can iterate on
snarky_sciuridae (or any badgeware app) without flashing/rebooting the badge.

Usage:
    python tools/sim/run.py                       # runs snarky_sciuridae
    python tools/sim/run.py --app apps/user/clock
    python tools/sim/run.py --scale 5 --speed 1

Controls (printed on start):
    A / S / D  (or 1 / 2 / 3) -> badge buttons A / B / C
    + / -                     -> speed time up / down (watch stats decay / death)
    T                         -> cycle time-of-day (day -> dusk -> night)
    L                         -> hot-reload the app source (edit + see instantly)
    P                         -> save a screenshot
    ESC / window close        -> quit (fires the app's on_exit)
"""

import argparse
import os
import sys

import pygame

# Import the shim from this file's own directory.
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import badgeware_sim as bw

REPO_ROOT = os.path.abspath(os.path.join(os.path.dirname(__file__), "..", ".."))

# Physical key -> badge button. Two comfortable options per button.
KEYMAP = {
    pygame.K_a: bw.BUTTON_A, pygame.K_1: bw.BUTTON_A,
    pygame.K_s: bw.BUTTON_B, pygame.K_2: bw.BUTTON_B,
    pygame.K_d: bw.BUTTON_C, pygame.K_3: bw.BUTTON_C,
    pygame.K_UP: bw.BUTTON_UP, pygame.K_DOWN: bw.BUTTON_DOWN,
}

TIME_OF_DAY = [("day", 12), ("dusk", 20), ("night", 2)]


def load_app(app_dir):
    """(Re)execute the app's __init__.py with a fresh module namespace."""
    # Drop any app-local modules (ui, vpet, ...) so edits are picked up on reload.
    for name in list(sys.modules):
        mod = sys.modules.get(name)
        f = getattr(mod, "__file__", None)
        if f and os.path.abspath(f).startswith(app_dir + os.sep):
            del sys.modules[name]

    src_path = os.path.join(app_dir, "__init__.py")
    with open(src_path) as f:
        source = f.read()

    g = {"__name__": "__main__", "__file__": src_path}
    exec(compile(source, src_path, "exec"), g)  # noqa: S102 - trusted local app
    return bw.get_callback(), g


def main():
    ap = argparse.ArgumentParser(description="Tufty badgeware desktop simulator")
    ap.add_argument("--app", default="apps/factory/snarky_sciuridae",
                    help="app directory (relative to repo root or absolute)")
    ap.add_argument("--scale", type=int, default=4, help="window upscale factor")
    ap.add_argument("--speed", type=float, default=1.0, help="initial time scale")
    ap.add_argument("--fps", type=int, default=30, help="frame rate cap")
    ap.add_argument("--data", default=os.path.join(REPO_ROOT, "tdf_cache.json"),
                    help="JSON fixture the fake `requests` serves (networked apps)")
    ap.add_argument("--wifi", choices=("on", "off"), default="on",
                    help="fake wifi: 'on' associates instantly, 'off' stays offline")
    args = ap.parse_args()

    app_dir = args.app
    if not os.path.isabs(app_dir):
        app_dir = os.path.join(REPO_ROOT, app_dir)
    app_dir = os.path.abspath(app_dir)
    if not os.path.isdir(app_dir):
        sys.exit(f"No such app directory: {app_dir}")

    # Wire the shim to the desktop filesystem and a local State file.
    bw.SYSTEM_ROOT = REPO_ROOT
    bw.FLASH_ROOT = os.path.join(os.path.dirname(__file__), ".sim_flash")
    bw.State.configure(os.path.join(os.path.dirname(__file__), ".sim_state.json"))

    # Network stubs for apps that import wifi/requests/secrets (e.g. tdf). The
    # stubs/ dir is on sys.path so those imports resolve to fakes; env vars tell
    # them how to behave. Harmless for apps that never import them (snarky).
    # Front of the path so our `secrets` wins over the CPython stdlib `secrets`.
    sys.path.insert(0, os.path.join(os.path.dirname(__file__), "stubs"))
    os.environ["SIM_WIFI"] = args.wifi
    if os.path.isfile(args.data):
        os.environ["SIM_HTTP_DATA"] = args.data

    pygame.init()
    pygame.display.set_caption("Tufty sim")
    # Render the canvas at scale x the device resolution (supersample) so text
    # and shapes are crisp; the window shows it 1:1.
    bw.set_render_scale(args.scale)
    win = pygame.display.set_mode(
        (bw.screen.width * args.scale, bw.screen.height * args.scale)
    )
    clock = pygame.time.Clock()

    bw.install()
    os.chdir(app_dir)  # relative asset loads ("assets/...") resolve from here
    sys.path.insert(0, app_dir)

    update, app_globals = load_app(app_dir)
    if update is None:
        sys.exit("App did not call run(update); nothing to simulate.")

    # An app may switch resolution on boot (badge.mode(HIRES) -> 320x240);
    # resize the window to match the canvas the app actually chose.
    want = (bw.screen.width * args.scale, bw.screen.height * args.scale)
    if win.get_size() != want:
        win = pygame.display.set_mode(want)

    speed = args.speed
    tod_index = 0
    app_name = os.path.basename(app_dir)
    print(f"Running '{app_name}'  scale={args.scale}  speed={speed}x")
    print("Controls: A/S/D (or 1/2/3)=buttons  +/-=speed  T=time-of-day  "
          "L=reload  P=screenshot  ESC=quit")

    running = True
    while running:
        real_dt = clock.tick(args.fps)  # ms since last frame (real time)

        pressed, released = set(), set()
        for event in pygame.event.get():
            if event.type == pygame.QUIT:
                running = False
            elif event.type == pygame.KEYDOWN:
                if event.key == pygame.K_ESCAPE:
                    running = False
                elif event.key in (pygame.K_PLUS, pygame.K_EQUALS):
                    speed = min(speed * 2, 240)
                    print(f"speed = {speed:g}x")
                elif event.key == pygame.K_MINUS:
                    speed = max(speed / 2, 0.125)
                    print(f"speed = {speed:g}x")
                elif event.key == pygame.K_t:
                    tod_index = (tod_index + 1) % len(TIME_OF_DAY)
                    label, bw.rtc.hour = TIME_OF_DAY[tod_index]
                    print(f"time of day = {label} (hour {bw.rtc.hour})")
                elif event.key == pygame.K_l:
                    g = bw.get_app_globals()
                    if g and callable(g.get("on_exit")):
                        g["on_exit"]()
                    update, app_globals = load_app(app_dir)
                    print("reloaded app source")
                elif event.key == pygame.K_p:
                    shot = os.path.join(os.path.dirname(__file__),
                                        f"screenshot_{bw.badge.ticks}.png")
                    pygame.image.save(win, shot)
                    print(f"saved {shot}")
                elif event.key in KEYMAP:
                    pressed.add(KEYMAP[event.key])
            elif event.type == pygame.KEYUP:
                if event.key in KEYMAP:
                    released.add(KEYMAP[event.key])

        held = {b for k, b in KEYMAP.items() if pygame.key.get_pressed()[k]}
        bw.badge.set_frame_input(pressed, held, released)
        bw.badge.advance(real_dt * speed)

        # Fresh frame: opaque black under the app's own draw calls.
        bw.screen.clear((0, 0, 0, 255))
        if update:
            update()

        # The canvas is already rendered at window resolution; show it 1:1.
        if bw.screen.surface.get_size() == win.get_size():
            win.blit(bw.screen.surface, (0, 0))
        else:
            win.blit(pygame.transform.scale(bw.screen.surface, win.get_size()), (0, 0))
        pygame.display.flip()

    g = bw.get_app_globals()
    if g and callable(g.get("on_exit")):
        g["on_exit"]()
    pygame.quit()


if __name__ == "__main__":
    main()
