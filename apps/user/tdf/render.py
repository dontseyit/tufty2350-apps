# TdF dashboard drawing - 320x240 HIRES, Tour-yellow on near-black.
# Device globals (screen, color, rom_font, ...) are only touched inside
# functions, so the module compiles/imports cleanly off-device; __init__ calls
# init() once after badge.mode(HIRES) to bake pens, fonts and metrics.

import config as cfg
import data

W, H = 320, 240

P = {}   # pen objects by theme name (+ derived)
F = {}   # fonts
M = {}   # font metrics / layout constants

TABS = ("RACE", "TICKER", "GC", "POINTS", "ROUTE")


def init():
    for name, rgb in cfg.THEME.items():
        P[name] = color.rgb(rgb[0], rgb[1], rgb[2])
    # Three pixel fonts (baked at fixed sizes, no runtime scaling; loaded like
    # hydrate does), a size hierarchy chosen on-device with the fonttest app:
    #   body  - nope     (~h13) : most text
    #   big   - bacteria (~h20) : km-to-go hero number
    #   mid   - smart    (~h16) : focused ticker post
    F["body"] = pixel_font.load("/system/assets/fonts/nope.ppf")
    F["mid"] = pixel_font.load("/system/assets/fonts/smart.ppf")
    F["big"] = pixel_font.load("/system/assets/fonts/bacteria.ppf")
    # measure_text returns FLOATS on-device; keep metrics int or the visible-
    # row counts derived from them become floats and list slicing TypeErrors
    screen.font = F["big"]
    M["big_h"] = int(screen.measure_text("0")[1])
    screen.font = F["mid"]
    M["mid_h"] = int(screen.measure_text("0")[1])
    screen.font = F["body"]
    M["body_h"] = int(screen.measure_text("0")[1])
    M["row_h"] = M["body_h"] + 3
    M["tab_h"] = M["body_h"] + 7


# ---- text helpers -----------------------------------------------------------
def _f(v):
    try:
        return float(v)
    except (TypeError, ValueError):
        return 0.0


def _t(s, x, y, pen):
    screen.pen = pen
    screen.text(s, int(x), int(y))


def _tw(s):
    return screen.measure_text(s)[0]


def _rt(s, right, y, pen):
    _t(s, right - _tw(s), y, pen)


def _fit(s, wmax):
    """Trim s to at most wmax pixels so left text never runs into a
    right-aligned column; a trailing '.' marks the cut."""
    if _tw(s) <= wmax:
        return s
    while s and _tw(s + ".") > wmax:
        s = s[:-1]
    return s + "." if s else ""


def _center(s, y, pen):
    _t(s, (W - _tw(s)) // 2, y, pen)


def _dots(now):
    return "." * (1 + (now // 400) % 3)


def _wrap(t, wmax, maxlines):
    """Greedy word wrap using measure_text; at most maxlines lines."""
    lines = []
    cur = ""
    for w in t.split():
        cand = cur + " " + w if cur else w
        if _tw(cand) <= wmax:
            cur = cand
        else:
            if cur:
                lines.append(cur)
                if len(lines) == maxlines:
                    return lines
            cur = w
    if cur and len(lines) < maxlines:
        lines.append(cur)
    return lines


def _proxy_host():
    u = cfg.PROXY_URL
    if u.startswith("http://"):
        u = u[7:]
    elif u.startswith("https://"):
        u = u[8:]
    return u.split("/")[0]


# ---- tab bar (all pages) ----------------------------------------------------
def _tab_bar(ui, now):
    th = M["tab_h"]
    screen.pen = P["BG"]
    screen.rectangle(0, 0, W, th)
    screen.pen = P["DIM"]
    screen.rectangle(0, th - 1, W, 1)

    # current page as a cycle indicator: < NAME > n/N  (A = prev, C = next)
    name = TABS[ui["page"]]
    _t("<", 3, 3, P["DIM"])
    _t(name, 13, 3, P["YELLOW"])
    rx = 13 + _tw(name) + 5
    _t(">", rx, 3, P["DIM"])
    _t("%d/%d" % (ui["page"] + 1, len(TABS)), rx + 12, 3, P["DIM"])

    # right cluster: [S12] [upd square] [age dot] [age text]
    age = data.age_seconds(now)
    if age is None or data.last_fetch_failed:
        dot = P["RED"]
    elif age < cfg.AGE_OK_S:
        dot = P["GREEN"]
    elif age < cfg.AGE_WARN_S:
        dot = P["YELLOW"]
    else:
        dot = P["RED"]
    atxt = data.fmt_age(age)
    ax = W - 4 - _tw(atxt)
    _t(atxt, ax, 3, P["INK"])
    dy = (th - 6) // 2
    screen.pen = dot
    screen.rectangle(ax - 9, dy, 5, 5)
    sx = ax - 9
    if ui["updating"]:
        screen.pen = P["YELLOW"]
        screen.rectangle(sx - 9, dy, 5, 5)
        sx -= 9
    if data.stage_nr:
        _rt("S%d" % data.stage_nr, sx - 6, 3, P["DIM"])


# ---- RACE page ----------------------------------------------------------------
RIDERS_PER_GROUP = 3   # PCS lists every rider in a group; show a few + a count


def _draw_race(ui, now):
    p = data.payload or {}
    prog = p.get("progress") or {}
    stage = p.get("stage") or {}
    y = M["tab_h"] + 4

    # hero km-to-go line (large font; the yellow number leads the page)
    screen.font = F["big"]
    hero = "%.1f" % _f(prog.get("kmtogo"))
    hw = _tw(hero)
    _t(hero, 8, y, P["YELLOW"])
    screen.font = F["body"]
    _t("KM TO GO", 8 + hw + 7, y + M["big_h"] - M["body_h"] - 1, P["INK"])
    y += M["big_h"] + 3

    # progress bar (kmdone / stage km; prefer the proxy's perc when present)
    perc = _f(prog.get("perc"))
    if perc <= 0:
        maxkm = _f(stage.get("km"))
        perc = 100.0 * _f(prog.get("kmdone")) / maxkm if maxkm > 0 else 0.0
    frac = min(max(perc / 100.0, 0.0), 1.0)
    bx, bw, bh = 8, W - 16, 7
    screen.pen = P["DIM"]
    screen.rectangle(bx, y, bw, bh)
    screen.pen = P["BG"]
    screen.rectangle(bx + 1, y + 1, bw - 2, bh - 2)
    if frac > 0:
        screen.pen = P["YELLOW"]
        screen.rectangle(bx + 1, y + 1, int((bw - 2) * frac), bh - 2)
    y += bh + 3

    # caption: percent + avg speed, or the race status when not racing
    status = str(prog.get("status") or "")
    if status and status != "racing":
        stxt = "NOT STARTED" if status.startswith("notstart") else status.upper()
        _t(stxt, bx, y, P["RED"])
        _rt("%.1f KM DONE" % _f(prog.get("kmdone")), W - 8, y, P["DIM"])
    else:
        _t("%.1f%%" % perc, bx, y, P["INK"])
        _rt("AVG %.1f KM/H" % _f(prog.get("avg")), W - 8, y, P["DIM"])
    y += M["body_h"] + 5

    # groups + riders as one scrollable row list
    rows = []
    for gi, g in enumerate(p.get("groups") or []):
        if not isinstance(g, dict):
            continue
        rows.append(("g", gi, g))
        riders = [r for r in (g.get("riders") or []) if isinstance(r, dict)]
        for r in riders[:RIDERS_PER_GROUP]:
            rows.append(("r", gi, r))

    kp = p.get("next_kp")
    kp_h = (M["body_h"] + 4) if isinstance(kp, dict) else 0
    bottom = H - kp_h - 2
    row_h = M["row_h"]
    visible = (bottom - y) // row_h
    if visible < 1:
        visible = 1
    maxs = len(rows) - visible
    if maxs < 0:
        maxs = 0
    s = min(max(ui["scroll"][cfg.RACE], 0), maxs)
    ui["scroll"][cfg.RACE] = s

    if not rows:
        _t("NO RACE SITUATION YET", 8, y + 4, P["DIM"])
    for kind, gi, item in rows[s:s + visible]:
        if kind == "g":
            label = str(item.get("label") or "?")
            bw2 = _tw(label) + 6
            screen.pen = P["YELLOW"]
            screen.rectangle(8, y, bw2, row_h - 1)
            _t(label, 11, y + 1, P["BG"])
            name = str(item.get("name") or "")
            if not name:
                if label.upper() == "P":
                    name = "PELOTON"
                elif gi == 0:
                    name = "BREAKAWAY"
                else:
                    name = "GROUP " + label
            gap = "LEAD" if gi == 0 else data.fmt_gap(item.get("gap"))
            if item.get("uncertain"):
                gap += "?"
            nx = 8 + bw2 + 6
            rx = W - 8
            _rt(gap, rx, y + 1, P["YELLOW"] if gi == 0 else P["INK"])
            rx -= _tw(gap) + 6
            # group size: PCS lists every rider, we only draw the first few
            cnt = len([r for r in (item.get("riders") or [])
                       if isinstance(r, dict)])
            if cnt:
                ctxt = "%dR" % cnt
                _rt(ctxt, rx, y + 1, P["DIM"])
                rx -= _tw(ctxt) + 6
            _t(_fit(name.upper(), rx - nx), nx, y + 1, P["INK"])
        else:
            nat = str(item.get("nation") or "")
            nm = "%s %s%s" % (item.get("bib", ""),
                              (nat.upper() + " ") if nat else "",
                              item.get("name", ""))
            gc = str(item.get("gc") or "")
            right = ("GC " + gc) if gc else ""
            wmax = W - 8 - 22 - ((_tw(right) + 6) if right else 0)
            _t(_fit(nm, wmax), 22, y + 1, P["DIM"])
            if right:
                _rt(right, W - 8, y + 1, P["DIM"])
        y += row_h

    # bottom line: next keypoint
    if isinstance(kp, dict):
        ky = H - M["body_h"] - 3
        name = str(kp.get("name") or "").upper()
        togo = _f(kp.get("togo"))
        t = kp.get("type")
        if t == "climb":
            cat = str(kp.get("cat") or "")
            head = ("^ C%s " % cat) if cat else "^ "
            ln, gr = _f(kp.get("len")), _f(kp.get("grad"))
            spec = (" %.1fKM@%.1f%%" % (ln, gr)) if ln > 0 else ""
            _t("%s%s IN %.1fKM%s" % (head, name, togo, spec), 8, ky, P["RED"])
        elif t == "sprint":
            _t("> SPRINT %s IN %.1fKM" % (name, togo), 8, ky, P["GREEN"])
        else:
            _t("> %s IN %.1fKM" % (name, togo), 8, ky, P["INK"])


# ---- TICKER page --------------------------------------------------------------
# A vertical "album roll": the focused post is expanded (full wrapped text in
# the mid font, with a yellow header and left accent bar); its neighbours
# collapse to small, dim body-font one-liners. Up/Down move the focus
# (ui["scroll"][TICKER] = focused index, 0 = newest), so the expanded card
# scrolls through the timeline like a reel.
PEEK_UP = 2        # newer posts shown collapsed above the focused card
FOCUS_LINES = 4    # max wrapped lines for the expanded (focused) message


def _post_head(post, now):
    """'148 KM - 2M AGO' header line for a post (falls back to seq)."""
    km = str(post.get("km") or "")
    head = (km + " KM") if km else ""
    atxt = data.fmt_age(data.post_age(post.get("ts", 0), now))
    if atxt != "--":
        head = (head + " - " if head else "") + atxt + " AGO"
    return head or ("POST %s" % post.get("seq", ""))


def _peek(post, y):
    """One small, dim, single-line neighbour in the reel (body font active)."""
    km = str(post.get("km") or "")
    txt = str(post.get("text") or "")
    label = (km + "KM  " if km else "") + txt
    _t(_fit(label, W - 24), 16, y, P["DIM"])


def _draw_ticker(ui, now):
    posts = data.posts
    top = M["tab_h"] + 4
    if not posts:
        _center("NO POSTS YET", 108, P["DIM"])
        ui["scroll"][cfg.TICKER] = 0
        return
    n = len(posts)
    f = min(max(ui["scroll"][cfg.TICKER], 0), n - 1)
    ui["scroll"][cfg.TICKER] = f

    body_h = M["body_h"]
    peek_h = body_h + 3
    line_h = M["mid_h"] + 2
    bottom = H - 4

    # Reel fills from the top edge: no blank band above the newest post, but
    # once you scroll past PEEK_UP the focused card stays put (stable anchor).
    above = min(f, PEEK_UP)
    fy = top + above * peek_h

    # newer neighbours, stacked upward; the furthest (k == above) lands at
    # `top`, just below the tab bar, so the reel never pokes into it
    for k in range(1, above + 1):
        _peek(posts[f - k], fy - k * peek_h)

    # ---- focused card: yellow header + full wrapped message + accent bar ----
    post = posts[f]
    _t(_post_head(post, now), 14, fy, P["YELLOW"])
    _rt("%d/%d" % (f + 1, n), W - 6, fy, P["DIM"])
    ty0 = fy + body_h + 4

    screen.font = F["mid"]
    wmax = W - 16 - 8
    text = str(post.get("text") or "")
    lines = _wrap(text, wmax, FOCUS_LINES)
    used = 0
    for ln in lines:
        used += len(ln.split())
    if lines and used < len(text.split()):
        last = lines[-1]
        while last and _tw(last + "...") > wmax:
            last = last[:-1].rstrip()
        lines[-1] = last + "..."
    ty = ty0
    for ln in lines:
        _t(ln, 16, ty, P["INK"])
        ty += line_h
    screen.font = F["body"]

    # data rows from the event's chart table (ranking/points/GC), if any:
    # small NAME .... value lines under the text; peeks fill whatever remains
    rows = post.get("rows") or []
    if rows:
        ty += 3
    for nm, val in rows:
        if ty + body_h > bottom - 2:
            break
        val = str(val)
        if val:
            _rt(val, W - 8, ty, P["DIM"])
            _t(_fit(str(nm), W - 8 - _tw(val) - 6 - 16), 16, ty, P["DIM"])
        else:
            _t(_fit(str(nm), W - 24), 16, ty, P["DIM"])
        ty += body_h + 2

    # accent bar down the left, spanning header + message + rows as one card
    screen.pen = P["YELLOW"]
    screen.rectangle(8, fy, 3, ty - fy - 2)

    # ---- older neighbours fill the space below to the bottom ----------------
    py = ty + 4
    idx = f + 1
    while idx < n and py + body_h <= bottom:
        _peek(posts[idx], py)
        py += peek_h
        idx += 1


# ---- GC page --------------------------------------------------------------------
def _draw_gc(ui, now):
    p = data.payload or {}
    gc = [r for r in (p.get("gc") or []) if isinstance(r, dict)]
    y = M["tab_h"] + 4
    if data.stage_nr > 1:
        _t("GC AFTER STAGE %d" % (data.stage_nr - 1), 8, y, P["YELLOW"])
    else:
        _t("GC STANDINGS", 8, y, P["YELLOW"])
    y += M["body_h"] + 5

    if not gc:
        _center("NO GC DATA YET", 110, P["DIM"])
        ui["scroll"][cfg.GC] = 0
        return

    row_h = M["row_h"]
    visible = (H - 4 - y) // row_h
    if visible < 1:
        visible = 1
    maxs = len(gc) - visible
    if maxs < 0:
        maxs = 0
    s = min(max(ui["scroll"][cfg.GC], 0), maxs)
    ui["scroll"][cfg.GC] = s

    rank_w = _tw("20") + 8
    for r in gc[s:s + visible]:
        rnk = r.get("rnk", 0)
        try:
            top3 = int(rnk) <= 3
        except (TypeError, ValueError):
            top3 = False
        gap = str(r.get("gap") or "")
        _t(str(rnk), 8, y, P["YELLOW"] if top3 else P["DIM"])
        _t(_fit(str(r.get("name") or ""), W - 8 - _tw(gap) - 6 - (8 + rank_w)),
           8 + rank_w, y, P["INK"])
        _rt(gap, W - 8, y, P["INK"])
        y += row_h


# ---- POINTS page (today's green / KOM points; B toggles class) ----------------
def _draw_points(ui, now):
    p = data.payload or {}
    pts = p.get("points") or {}
    kom = ui.get("pts_kom")
    rows = [r for r in ((pts.get("kom") if kom else pts.get("green")) or [])
            if isinstance(r, (list, tuple)) and len(r) >= 2]
    y = M["tab_h"] + 4
    _t("KOM POINTS TODAY" if kom else "GREEN POINTS TODAY", 8, y, P["YELLOW"])
    _rt("B: GREEN" if kom else "B: KOM", W - 8, y, P["DIM"])
    y += M["body_h"] + 5

    if not rows:
        _center("NO POINTS SCORED YET", 110, P["DIM"])
        ui["scroll"][cfg.POINTS] = 0
        return

    row_h = M["row_h"]
    visible = (H - 4 - y) // row_h
    if visible < 1:
        visible = 1
    maxs = max(0, len(rows) - visible)
    s = min(max(ui["scroll"][cfg.POINTS], 0), maxs)
    ui["scroll"][cfg.POINTS] = s

    rank_w = _tw("20") + 8
    rank = s + 1
    for r in rows[s:s + visible]:
        vtxt = str(r[1])
        _t(str(rank), 8, y, P["YELLOW"] if rank <= 3 else P["DIM"])
        _t(_fit(str(r[0]), W - 8 - _tw(vtxt) - 6 - (8 + rank_w)),
           8 + rank_w, y, P["INK"])
        _rt(vtxt, W - 8, y, P["INK"])
        y += row_h
        rank += 1


# ---- ROUTE page (roadbook: climbs & sprints, passed ones dimmed) --------------
def _draw_route(ui, now):
    p = data.payload or {}
    kps = [k for k in (p.get("keypoints") or []) if isinstance(k, dict)]
    kmdone = _f((p.get("progress") or {}).get("kmdone"))
    y = M["tab_h"] + 4
    _t("ROADBOOK", 8, y, P["YELLOW"])
    total = _f((p.get("stage") or {}).get("km"))
    if total > 0:
        _rt("%.0f KM" % total, W - 8, y, P["DIM"])
    y += M["body_h"] + 5

    if not kps:
        _center("NO ROUTE DATA YET", 110, P["DIM"])
        ui["scroll"][cfg.ROUTE] = 0
        return

    row_h = M["row_h"] + 2
    visible = (H - 4 - y) // row_h
    if visible < 1:
        visible = 1
    maxs = max(0, len(kps) - visible)
    s = min(max(ui["scroll"][cfg.ROUTE], 0), maxs)
    ui["scroll"][cfg.ROUTE] = s

    for k in kps[s:s + visible]:
        km = _f(k.get("km"))
        ahead = km > kmdone
        pen = P["INK"] if ahead else P["DIM"]
        if k.get("type") == "climb":
            cat = str(k.get("cat") or "")
            head = ("^C%s" % cat) if cat else "^"
            hpen = (P["RED"] if ahead else P["DIM"])
            ln, gr = _f(k.get("len")), _f(k.get("grad"))
            right = ("%.1fKM@%.1f%%" % (ln, gr)) if ln > 0 else ""
        else:
            head, hpen, right = ">", (P["GREEN"] if ahead else P["DIM"]), "SPRINT"
        _t(head, 8, y, hpen)
        nx = 8 + _tw("^C9") + 6
        _rt("@%.0f" % km, W - 8, y, P["DIM"])
        rx = W - 8 - _tw("@%.0f" % km) - 8
        if right:
            _rt(right, rx, y, pen)
            rx -= _tw(right) + 6
        _t(_fit(str(k.get("name") or "").upper(), rx - nx), nx, y, pen)
        y += row_h


# ---- overlays -----------------------------------------------------------------
def _banner(ui, now):
    """Thin red strip along the bottom for stale/offline states."""
    if data.warming:
        msg = "PROXY WARMING UP" + _dots(now)
    elif ui["wifi"] == cfg.WIFI_OFF:
        msg = "WIFI OFFLINE - SHOWING LAST DATA"
    elif ui["wifi"] == cfg.WIFI_CONNECTING:
        msg = "CONNECTING " + (ui.get("ssid") or "WIFI") + _dots(now)
    else:
        age = data.age_seconds(now)
        if data.last_fetch_failed or age is None or age > cfg.AGE_WARN_S:
            msg = "STALE DATA - CHECK PROXY"
        else:
            return
    h = M["body_h"] + 4
    screen.pen = P["RED"]
    screen.rectangle(0, H - h, W, h)
    _t(msg, 6, H - h + 2, P["BG"])


def _draw_waiting(ui, now):
    """Before any data at all (no fetch yet, nothing on flash)."""
    if data.warming:
        _center("PROXY WARMING UP" + _dots(now), 104, P["YELLOW"])
    elif ui["wifi"] == cfg.WIFI_CONNECTING:
        _center("CONNECTING WIFI" + _dots(now), 104, P["YELLOW"])
        _center(ui.get("ssid") or "", 104 + M["body_h"] + 5, P["DIM"])
    elif ui["wifi"] == cfg.WIFI_OFF:
        _center("WIFI OFFLINE - RETRYING" + _dots(now), 104, P["RED"])
        _center(ui.get("ssid") or "", 104 + M["body_h"] + 5, P["DIM"])
    else:
        _center("WAITING FOR PROXY", 98, P["YELLOW"])
        _center(_proxy_host(), 98 + M["body_h"] + 5, P["DIM"])


# ---- top-level ------------------------------------------------------------------
def draw(ui, now):
    screen.pen = P["BG"]
    screen.clear()
    screen.font = F["body"]

    if data.payload is None:
        _tab_bar(ui, now)
        _draw_waiting(ui, now)
        return

    page = ui["page"]
    if page == cfg.RACE:
        _draw_race(ui, now)
    elif page == cfg.TICKER:
        _draw_ticker(ui, now)
    elif page == cfg.GC:
        _draw_gc(ui, now)
    elif page == cfg.POINTS:
        _draw_points(ui, now)
    else:
        _draw_route(ui, now)
    _tab_bar(ui, now)
    _banner(ui, now)
