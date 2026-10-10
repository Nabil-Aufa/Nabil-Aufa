#!/usr/bin/env python3
"""Build the animated / auto-updating banners for the profile README.

  assets/my-stack.svg  background from Figma + two looping rows of tech logos
  assets/stats.svg     background from Figma + live GitHub numbers in Coolvetica

Run locally:   python scripts/build_svgs.py --contrib 638 --current 5 --longest 21
Run in CI:     GITHUB_TOKEN=... python scripts/build_svgs.py --user Nabil-Aufa
"""
import argparse, base64, datetime as dt, json, os, re, urllib.request
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
ASSETS, SCRIPTS = ROOT / "assets", ROOT / "scripts"
W, H = 1200, 660  # Figma frame size (both banners use this coordinate space)


def b64(path):
    return base64.b64encode(path.read_bytes()).decode()


# ---------------------------------------------------------------- my stack
BAND_Y, BAND_H = 462.87, 145.39  # gray glass band in the Figma frame
SLOT, SIZE, PERIOD = 120, 52, 1200
ROWS = [  # (logo indices, x offset, center y, direction)
    (range(0, 10), 30, BAND_Y + 38, "left"),
    (range(10, 20), 90, BAND_Y + BAND_H - 38, "right"),
]


def logo_svg(i, path, x, y):
    s = path.read_text()
    s = re.sub(r"<\?xml[^>]*>", "", s)
    # namespace ids so gradients/masks of different logos never collide
    pre = f"l{i}"
    s = re.sub(r'id="([^"]+)"', lambda m: f'id="{pre}{m.group(1)}"', s)
    s = re.sub(r"url\(#([^)]+)\)", lambda m: f"url(#{pre}{m.group(1)})", s)
    s = re.sub(r'(xlink:)?href="#([^"]+)"', lambda m: f'href="#{pre}{m.group(2)}"', s)
    s = re.sub(r'\swidth="[^"]*"', "", s, count=1)
    s = re.sub(r'\sheight="[^"]*"', "", s, count=1)
    return s.replace("<svg", f'<svg x="{x:.1f}" y="{y:.1f}" width="{SIZE}" height="{SIZE}"', 1)


def build_stack():
    logos = sorted((SCRIPTS / "logos").glob("*.svg"))
    rows = []
    for r, (idx, off, cy, direction) in enumerate(ROWS):
        parts = []
        for copy in range(2):  # two copies side by side = seamless loop
            for k, li in enumerate(idx):
                x = off + copy * PERIOD + k * SLOT - SIZE / 2
                parts.append(logo_svg(f"{r}{copy}{k}", logos[li], x, cy - SIZE / 2))
        rows.append(f'<g class="row {direction}"><g filter="url(#shadow)">{"".join(parts)}</g></g>')
    svg = f"""<svg xmlns="http://www.w3.org/2000/svg" xmlns:xlink="http://www.w3.org/1999/xlink" width="{W}" height="{H}" viewBox="0 0 {W} {H}">
<style>
.row{{animation-duration:28s;animation-timing-function:linear;animation-iteration-count:infinite}}
.left{{animation-name:toLeft}}
.right{{animation-name:toRight}}
@keyframes toLeft{{from{{transform:translateX(0)}}to{{transform:translateX(-{PERIOD}px)}}}}
@keyframes toRight{{from{{transform:translateX(-{PERIOD}px)}}to{{transform:translateX(0)}}}}
</style>
<defs><filter id="shadow" x="-10%" y="-40%" width="120%" height="180%"><feDropShadow dx="3" dy="5" stdDeviation="4" flood-color="#000" flood-opacity=".35"/></filter>
<clipPath id="frame"><rect width="{W}" height="{H}"/></clipPath></defs>
<image width="{W}" height="{H}" href="data:image/png;base64,{b64(ASSETS / 'stack-bg.png')}"/>
<g clip-path="url(#frame)">{"".join(rows)}</g>
</svg>"""
    (ASSETS / "my-stack.svg").write_text(svg)


# ---------------------------------------------------------------- stats
FONT = json.loads((SCRIPTS / "coolvetica-glyphs.json").read_text())
NUM_SIZE = 59.921016693115234
NUM_RIGHT = 1081  # right edge of the number text boxes in Figma
NUM_TOPS = [153, 245, 337]
NUM_BOX_H = 59
RED = "#FB0004"


def number_path(text, right, top):
    s = NUM_SIZE / FONT["upm"]
    asc, desc = FONT["ascent"] * s, -FONT["descent"] * s
    baseline = top + (NUM_BOX_H - (asc + desc)) / 2 + asc
    width = sum(FONT["glyphs"][c]["adv"] for c in text) * s
    x, out = right - width, []
    for c in text:
        g = FONT["glyphs"][c]
        out.append(f'<path transform="translate({x:.2f} {baseline:.2f}) scale({s:.5f} {-s:.5f})" d="{g["d"]}"/>')
        x += g["adv"] * s
    return "".join(out)


def build_stats(contrib, current, longest):
    nums = "".join(number_path(f"{v:,}", NUM_RIGHT, t) for v, t in zip((contrib, current, longest), NUM_TOPS))
    svg = f"""<svg xmlns="http://www.w3.org/2000/svg" width="{W}" height="460" viewBox="0 0 {W} 460">
<image width="{W}" height="460" href="data:image/png;base64,{b64(ASSETS / 'stats-bg.png')}"/>
<g fill="{RED}">{nums}</g>
</svg>"""
    (ASSETS / "stats.svg").write_text(svg)



# ---------------------------------------------------------------- link buttons
BUTTONS = {  # file name -> label (links live in README.md)
    "forepay": "FOREPAY", "sterun": "STERUN", "sterish": "STERISH",
    "corolary": "COROLARY", "nokturn": "NOKTURN", "aksesin": "AKSESIN",
    "email": "EMAIL", "github": "GITHUB", "instagram": "INSTAGRAM",
}
BTN_H, BTN_SIZE, BTN_PAD = 64, 34, 26  # matches the glass buttons in the Connect banner


def text_paths(text, x, baseline, size):
    s = size / FONT["upm"]
    out = []
    for c in text:
        g = FONT["glyphs"][c]
        if g["d"]:
            out.append(f'<path transform="translate({x:.2f} {baseline:.2f}) scale({s:.5f} {-s:.5f})" d="{g["d"]}"/>')
        x += g["adv"] * s
    return "".join(out), x


def build_button(name, label):
    s = BTN_SIZE / FONT["upm"]
    text_w = sum(FONT["glyphs"][c]["adv"] for c in label) * s
    arrow = FONT["capHeight"] * s
    w = round(BTN_PAD + text_w + 10 + arrow + BTN_PAD)
    pad = 10  # room for the drop shadow
    W_, H_ = w + pad * 2, BTN_H + pad * 2
    baseline = pad + BTN_H / 2 + FONT["capHeight"] * s / 2
    glyphs, x = text_paths(label, pad + BTN_PAD, baseline, BTN_SIZE)
    ax, ay = x + 10, baseline - arrow  # arrow box: top-left corner
    svg = f"""<svg xmlns="http://www.w3.org/2000/svg" width="{W_}" height="{H_}" viewBox="0 0 {W_} {H_}">
<defs>
<linearGradient id="sky" x1="0" y1="0" x2="0" y2="1"><stop offset="0" stop-color="#3f86e0"/><stop offset=".6" stop-color="#8fc0f2"/><stop offset="1" stop-color="#dcefff"/></linearGradient>
<linearGradient id="glass" x1="0" y1="0" x2="0" y2="1"><stop offset="0" stop-color="#a7adb7" stop-opacity=".62"/><stop offset="1" stop-color="#727782" stop-opacity=".74"/></linearGradient>
<linearGradient id="shine" x1="0" y1="0" x2="0" y2="1"><stop offset="0" stop-color="#fff" stop-opacity=".55"/><stop offset=".5" stop-color="#fff" stop-opacity="0"/></linearGradient>
<filter id="blur" x="-20%" y="-50%" width="140%" height="200%"><feGaussianBlur stdDeviation="7"/></filter>
<filter id="shadow" x="-20%" y="-40%" width="140%" height="180%"><feDropShadow dx="0" dy="4" stdDeviation="4" flood-color="#000" flood-opacity=".3"/></filter>
<clipPath id="pill"><rect x="{pad}" y="{pad}" width="{w}" height="{BTN_H}" rx="{BTN_H * .28:.1f}"/></clipPath>
</defs>
<g filter="url(#shadow)"><rect x="{pad}" y="{pad}" width="{w}" height="{BTN_H}" rx="{BTN_H * .28:.1f}" fill="#7c818b"/></g>
<g clip-path="url(#pill)">
<rect x="{pad}" y="{pad}" width="{w}" height="{BTN_H}" fill="url(#sky)"/>
<g filter="url(#blur)" fill="#fff" opacity=".85"><ellipse cx="{pad + w * .2:.0f}" cy="{pad + 46}" rx="{w * .22:.0f}" ry="16"/><ellipse cx="{pad + w * .75:.0f}" cy="{pad + 52}" rx="{w * .25:.0f}" ry="18"/></g>
<rect x="{pad}" y="{pad}" width="{w}" height="{BTN_H}" fill="url(#glass)"/>
<rect x="{pad}" y="{pad}" width="{w}" height="{BTN_H / 2}" fill="url(#shine)"/>
</g>
<rect x="{pad + .75}" y="{pad + .75}" width="{w - 1.5}" height="{BTN_H - 1.5}" rx="{BTN_H * .28 - .75:.1f}" fill="none" stroke="#fff" stroke-opacity=".55" stroke-width="1.5"/>
<g fill="#fff">{glyphs}</g>
<path d="M{ax + arrow * .12:.1f} {ay + arrow * .88:.1f} L{ax + arrow * .88:.1f} {ay + arrow * .12:.1f} M{ax + arrow * .3:.1f} {ay + arrow * .12:.1f} H{ax + arrow * .88:.1f} V{ay + arrow * .7:.1f}" fill="none" stroke="#fff" stroke-width="{BTN_SIZE * .07:.1f}" stroke-linecap="butt"/>
</svg>"""
    (ASSETS / "buttons").mkdir(exist_ok=True)
    (ASSETS / "buttons" / f"{name}.svg").write_text(svg)


def build_buttons():
    for name, label in BUTTONS.items():
        build_button(name, label)

# ---------------------------------------------------------------- GitHub data
def gql(query, token, **variables):
    req = urllib.request.Request(
        "https://api.github.com/graphql",
        data=json.dumps({"query": query, "variables": variables}).encode(),
        headers={"Authorization": f"bearer {token}", "Content-Type": "application/json"},
    )
    data = json.load(urllib.request.urlopen(req))
    if "errors" in data:
        raise SystemExit(data["errors"])
    return data["data"]


def fetch_stats(user, token):
    created = gql("query($u:String!){user(login:$u){createdAt}}", token, u=user)["user"]["createdAt"]
    q = """query($u:String!,$f:DateTime!,$t:DateTime!){user(login:$u){contributionsCollection(from:$f,to:$t){
           contributionCalendar{totalContributions weeks{contributionDays{date contributionCount}}}}}}"""
    today = dt.datetime.now(dt.timezone.utc)
    days, start = {}, dt.datetime.fromisoformat(created.replace("Z", "+00:00"))
    while start < today:  # the API returns at most one year per call
        end = min(start + dt.timedelta(days=365), today)
        cal = gql(q, token, u=user, f=start.isoformat(), t=end.isoformat())["user"]["contributionsCollection"]["contributionCalendar"]
        for w in cal["weeks"]:
            for d in w["contributionDays"]:
                days[d["date"]] = d["contributionCount"]
        start = end
    last_year = gql(
        "query($u:String!){user(login:$u){contributionsCollection{contributionCalendar{totalContributions}}}}", token, u=user
    )["user"]["contributionsCollection"]["contributionCalendar"]["totalContributions"]

    ordered = sorted(days)
    longest = run = 0
    for d in ordered:
        run = run + 1 if days[d] > 0 else 0
        longest = max(longest, run)
    current, i = 0, len(ordered) - 1
    if i >= 0 and days[ordered[i]] == 0:  # today not counted yet: streak still alive
        i -= 1
    while i >= 0 and days[ordered[i]] > 0:
        current += 1
        i -= 1
    return last_year, current, longest


if __name__ == "__main__":
    ap = argparse.ArgumentParser()
    ap.add_argument("--user", default="Nabil-Aufa")
    ap.add_argument("--contrib", type=int)
    ap.add_argument("--current", type=int)
    ap.add_argument("--longest", type=int)
    ap.add_argument("--skip-stack", action="store_true")
    a = ap.parse_args()
    build_buttons()
    if not a.skip_stack:
        build_stack()
    if a.contrib is not None:
        stats = (a.contrib, a.current or 0, a.longest or 0)
    else:
        stats = fetch_stats(a.user, os.environ["GITHUB_TOKEN"])
    build_stats(*stats)
    print("contributions=%d current=%d longest=%d" % stats)
