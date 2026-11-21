"""Render a contribution-streak card (dark + light SVG) from the GitHub GraphQL API.

Usage: python3 streak_card.py <out_dir>
Needs GH_TOKEN (or GITHUB_TOKEN). Writes streak-dark.svg and streak-light.svg.

Streak rules match the common streak-stats convention: days are UTC dates from
the contribution calendar; a current streak is not broken by today having no
contributions yet.
"""
import datetime as dt
import json
import os
import sys
import urllib.request

USER = "TMHSDigital"
API = "https://api.github.com/graphql"

THEMES = {
    "dark": {"bg": "1e1e2e", "text": "ffffff", "accent": "00A0F0", "muted": "8b949e", "rule": "3d444d", "border": "1e1e2e"},
    "light": {"bg": "ffffff", "text": "1f2328", "accent": "0077B6", "muted": "59636e", "rule": "d1d9e0", "border": "d1d9e0"},
}


def gql(query, variables):
    token = os.environ.get("GH_TOKEN") or os.environ.get("GITHUB_TOKEN")
    if not token:
        sys.exit("GH_TOKEN is not set")
    req = urllib.request.Request(
        API,
        data=json.dumps({"query": query, "variables": variables}).encode(),
        headers={"Authorization": f"Bearer {token}", "Content-Type": "application/json"},
    )
    with urllib.request.urlopen(req) as resp:
        body = json.load(resp)
    if body.get("errors"):
        sys.exit(f"GraphQL error: {body['errors']}")
    return body["data"]


def contribution_days():
    created = gql("query($u:String!){user(login:$u){createdAt}}", {"u": USER})["user"]["createdAt"]
    start_year = int(created[:4])
    today = dt.datetime.now(dt.timezone.utc).date()
    q = """query($u:String!,$from:DateTime!,$to:DateTime!){user(login:$u){
      contributionsCollection(from:$from,to:$to){contributionCalendar{
        weeks{contributionDays{date contributionCount}}}}}}"""
    days = {}
    for year in range(start_year, today.year + 1):
        data = gql(q, {"u": USER, "from": f"{year}-01-01T00:00:00Z", "to": f"{year}-12-31T23:59:59Z"})
        cal = data["user"]["contributionsCollection"]["contributionCalendar"]
        for week in cal["weeks"]:
            for d in week["contributionDays"]:
                date = dt.date.fromisoformat(d["date"])
                if date <= today:
                    days[date] = d["contributionCount"]
    return [(d, days[d]) for d in sorted(days)], today


def stats(days, today):
    total = sum(c for _, c in days)
    first = next((d for d, c in days if c > 0), today)

    longest = (0, None, None)
    run_start, run_len = None, 0
    for d, c in days:
        if c > 0:
            run_start = d if run_len == 0 else run_start
            run_len += 1
            if run_len > longest[0]:
                longest = (run_len, run_start, d)
        else:
            run_len = 0

    current = (0, None, None)
    idx = len(days) - 1
    if idx >= 0 and days[idx][0] == today and days[idx][1] == 0:
        idx -= 1  # today not contributed yet: streak still alive through yesterday
    end = days[idx][0] if idx >= 0 else None
    n = 0
    while idx >= 0 and days[idx][1] > 0:
        n += 1
        idx -= 1
    if n:
        current = (n, days[idx + 1][0], end)
    return total, first, current, longest


def fmt_date(d, today):
    return f"{d:%b} {d.day}" + ("" if d.year == today.year else f", {d.year}")


def fmt_range(start, end, today):
    if not start:
        return ""
    return f"{fmt_date(start, today)} - {fmt_date(end, today)}" if start != end else fmt_date(start, today)


def esc(s):
    return s.replace("&", "&amp;").replace("<", "&lt;").replace(">", "&gt;")


def render(theme, total, first, current, longest, today):
    c = THEMES[theme]
    font = "'Segoe UI', Ubuntu, 'Helvetica Neue', Arial, sans-serif"
    first_label = f"{first:%b} {first.day}, {first.year}"
    cur_range = fmt_range(current[1], current[2], today)
    long_range = fmt_range(longest[1], longest[2], today)
    W, H = 495, 195
    # Ring: r=40, centered at (247.5, 71); dash gap rotated to the top for the flame.
    circ = 2 * 3.14159265 * 40
    gap = 30
    return f"""<svg xmlns="http://www.w3.org/2000/svg" width="{W}" height="{H}" viewBox="0 0 {W} {H}" role="img" aria-label="GitHub contribution streak: {total:,} total contributions, current streak {current[0]} days, longest streak {longest[0]} days">
<title>{total:,} contributions, current streak {current[0]}, longest streak {longest[0]}</title>
<style>
.n{{font:700 28px {font};fill:#{c['text']}}}
.l{{font:400 14px {font};fill:#{c['text']}}}
.a{{font:700 14px {font};fill:#{c['accent']}}}
.d{{font:400 12px {font};fill:#{c['muted']}}}
</style>
<rect x="0.5" y="0.5" width="{W - 1}" height="{H - 1}" rx="6" fill="#{c['bg']}" stroke="#{c['border']}"/>
<line x1="165" y1="28" x2="165" y2="170" stroke="#{c['rule']}" stroke-width="1"/>
<line x1="330" y1="28" x2="330" y2="170" stroke="#{c['rule']}" stroke-width="1"/>
<g text-anchor="middle">
<text class="n" x="82.5" y="79">{total:,}</text>
<text class="l" x="82.5" y="114">Total Contributions</text>
<text class="d" x="82.5" y="143">{esc(first_label)} - Present</text>
<circle cx="247.5" cy="71" r="40" fill="none" stroke="#{c['accent']}" stroke-width="5" stroke-linecap="round"
 stroke-dasharray="{circ - gap:.1f} {gap}" transform="rotate({-90 + gap / circ * 180:.1f} 247.5 71)"/>
<path transform="translate(247.5 31)" fill="#{c['accent']}" d="M0-10C4-5 7-2 7 3 7 8 4 11 0 11-4 11-7 8-7 3-7-1-4-3-3-7-2-3-1-2 1-1 1-4 1-7 0-10Z"/>
<text class="n" x="247.5" y="81">{current[0]}</text>
<text class="a" x="247.5" y="138">Current Streak</text>
<text class="d" x="247.5" y="160">{esc(cur_range)}</text>
<text class="n" x="412.5" y="79">{longest[0]}</text>
<text class="l" x="412.5" y="114">Longest Streak</text>
<text class="d" x="412.5" y="143">{esc(long_range)}</text>
</g>
</svg>
"""


def main():
    out = sys.argv[1] if len(sys.argv) > 1 else "dist"
    os.makedirs(out, exist_ok=True)
    days, today = contribution_days()
    total, first, current, longest = stats(days, today)
    print(f"total={total} first={first} current={current} longest={longest}")
    for theme in THEMES:
        with open(os.path.join(out, f"streak-{theme}.svg"), "w", encoding="utf-8", newline="\n") as f:
            f.write(render(theme, total, first, current, longest, today))


if __name__ == "__main__":
    main()
