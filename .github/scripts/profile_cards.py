"""Render the README Metrics cards as theme-aware, lightly animated SVGs.

Usage: python3 profile_cards.py <out_dir>
Needs GH_TOKEN (or GITHUB_TOKEN). For each theme (dark, light) writes:
  streak-<theme>.svg    total contributions, current and longest streak
  overview-<theme>.svg  activity counts and top languages
  activity-<theme>.svg  weekly contributions over the last 52 weeks

All cards are 740px wide to line up with the contribution snake. Animations are
CSS-only (they run inside <img>) and are disabled under prefers-reduced-motion.

Conventions: streak days are UTC calendar dates and a current streak is not
broken by today having no contributions yet. Stars and languages count public,
non-fork repos the user owns; languages are weighted by bytes; commits come
from the commit search API.
"""
import datetime as dt
import json
import os
import sys
import urllib.request

USER = "TMHSDigital"
W = 740
TOP_LANGS = 8
FONT = "'Segoe UI', Ubuntu, 'Helvetica Neue', Arial, sans-serif"

THEMES = {
    "dark": {"bg": "1e1e2e", "text": "ffffff", "accent": "00A0F0", "muted": "8b949e",
             "rule": "3d444d", "border": "1e1e2e", "track": "2d2d3f"},
    "light": {"bg": "ffffff", "text": "1f2328", "accent": "0077B6", "muted": "59636e",
              "rule": "d1d9e0", "border": "d1d9e0", "track": "eaeef2"},
}


# ---------------------------------------------------------------- data

def request(url, payload=None):
    token = os.environ.get("GH_TOKEN") or os.environ.get("GITHUB_TOKEN")
    if not token:
        sys.exit("GH_TOKEN is not set")
    headers = {"Authorization": f"Bearer {token}", "Accept": "application/vnd.github+json"}
    data = None
    if payload is not None:
        data = json.dumps(payload).encode()
        headers["Content-Type"] = "application/json"
    with urllib.request.urlopen(urllib.request.Request(url, data=data, headers=headers)) as resp:
        return json.load(resp)


def gql(query, variables):
    body = request("https://api.github.com/graphql", {"query": query, "variables": variables})
    if body.get("errors"):
        sys.exit(f"GraphQL error: {body['errors']}")
    return body["data"]


def contribution_days():
    created = gql("query($u:String!){user(login:$u){createdAt}}", {"u": USER})["user"]["createdAt"]
    today = dt.datetime.now(dt.timezone.utc).date()
    q = """query($u:String!,$from:DateTime!,$to:DateTime!){user(login:$u){
      contributionsCollection(from:$from,to:$to){contributionCalendar{
        weeks{contributionDays{date contributionCount}}}}}}"""
    days = {}
    for year in range(int(created[:4]), today.year + 1):
        cal = gql(q, {"u": USER, "from": f"{year}-01-01T00:00:00Z", "to": f"{year}-12-31T23:59:59Z"})
        for week in cal["user"]["contributionsCollection"]["contributionCalendar"]["weeks"]:
            for d in week["contributionDays"]:
                date = dt.date.fromisoformat(d["date"])
                if date <= today:
                    days[date] = d["contributionCount"]
    return [(d, days[d]) for d in sorted(days)], today


def streaks(days, today):
    total = sum(c for _, c in days)
    first = next((d for d, c in days if c > 0), today)
    longest, run_start, run_len = (0, None, None), None, 0
    for d, c in days:
        if c > 0:
            run_start = d if run_len == 0 else run_start
            run_len += 1
            if run_len > longest[0]:
                longest = (run_len, run_start, d)
        else:
            run_len = 0
    current, idx = (0, None, None), len(days) - 1
    if idx >= 0 and days[idx][0] == today and days[idx][1] == 0:
        idx -= 1  # today not contributed yet: streak still alive through yesterday
    end, n = (days[idx][0] if idx >= 0 else None), 0
    while idx >= 0 and days[idx][1] > 0:
        n += 1
        idx -= 1
    if n:
        current = (n, days[idx + 1][0], end)
    return total, first, current, longest


def weekly(days, weeks=52):
    """Sum the last weeks*7 days into weeks, oldest first. Returns [(start_date, count)]."""
    tail = days[-weeks * 7:]
    return [(tail[i][0], sum(c for _, c in tail[i:i + 7])) for i in range(0, len(tail), 7)]


def repo_stats():
    q = """query($u:String!,$after:String){user(login:$u){
      pullRequests{totalCount} issues{totalCount}
      repositoriesContributedTo(first:1,contributionTypes:[COMMIT,ISSUE,PULL_REQUEST,REPOSITORY]){totalCount}
      repositories(first:100,after:$after,ownerAffiliations:OWNER,isFork:false,privacy:PUBLIC){
        totalCount pageInfo{hasNextPage endCursor}
        nodes{stargazerCount languages(first:10,orderBy:{field:SIZE,direction:DESC}){
          edges{size node{name color}}}}}}}"""
    stars, langs, after = 0, {}, None
    while True:
        user = gql(q, {"u": USER, "after": after})["user"]
        repos = user["repositories"]
        for r in repos["nodes"]:
            stars += r["stargazerCount"]
            for e in r["languages"]["edges"]:
                size, color = langs.get(e["node"]["name"], (0, e["node"]["color"]))
                langs[e["node"]["name"]] = (size + e["size"], color)
        if not repos["pageInfo"]["hasNextPage"]:
            break
        after = repos["pageInfo"]["endCursor"]
    commits = request(f"https://api.github.com/search/commits?q=author:{USER}&per_page=1")["total_count"]
    total_bytes = sum(s for s, _ in langs.values()) or 1
    top = sorted(langs.items(), key=lambda kv: -kv[1][0])[:TOP_LANGS]
    return {
        "repos": repos["totalCount"],
        "stars": stars,
        "commits": commits,
        "prs": user["pullRequests"]["totalCount"],
        "issues": user["issues"]["totalCount"],
        "contributed": user["repositoriesContributedTo"]["totalCount"],
        "langs": [(n, s / total_bytes * 100, col) for n, (s, col) in top],
    }


# ---------------------------------------------------------------- helpers

def esc(s):
    return str(s).replace("&", "&amp;").replace("<", "&lt;").replace(">", "&gt;").replace('"', "&quot;")


def short(n):
    return f"{n / 1000:.1f}k".replace(".0k", "k") if n >= 1000 else str(n)


def fmt_date(d, today):
    return f"{d:%b} {d.day}" + ("" if d.year == today.year else f", {d.year}")


def fmt_range(start, end, today):
    if not start:
        return "No active streak"
    return f"{fmt_date(start, today)} - {fmt_date(end, today)}" if start != end else fmt_date(start, today)


def frame(c, h, label, body, extra_css=""):
    return f"""<svg xmlns="http://www.w3.org/2000/svg" width="{W}" height="{h}" viewBox="0 0 {W} {h}" role="img" aria-label="{esc(label)}">
<title>{esc(label)}</title>
<style>
.h{{font:700 13px {FONT};fill:#{c['accent']};letter-spacing:.06em;text-transform:uppercase}}
.n{{font:700 30px {FONT};fill:#{c['text']}}}
.l{{font:400 13px {FONT};fill:#{c['text']}}}
.v{{font:700 13px {FONT};fill:#{c['text']}}}
.a{{font:700 14px {FONT};fill:#{c['accent']}}}
.d{{font:400 12px {FONT};fill:#{c['muted']}}}
.f{{animation:fu .7s cubic-bezier(.2,.7,.2,1) both}}
@keyframes fu{{from{{opacity:0;transform:translateY(6px)}}to{{opacity:1;transform:none}}}}
{extra_css}
@media (prefers-reduced-motion:reduce){{*{{animation:none!important}}}}
</style>
<rect x="0.5" y="0.5" width="{W - 1}" height="{h - 1}" rx="8" fill="#{c['bg']}" stroke="#{c['border']}"/>
{body}
</svg>
"""


def delay(i, step=0.08, base=0.05):
    return f' style="animation-delay:{base + i * step:.2f}s"'


# ---------------------------------------------------------------- cards

def streak_card(c, total, first, current, longest, today):
    H, cx, cy, r = 200, W / 2, 78, 44
    circ = 2 * 3.14159265 * r
    gap = 32
    arc = circ - gap
    rot = -90 + gap / circ * 180
    css = (f".ring{{stroke-dasharray:{arc:.1f} {circ:.1f};animation:draw 1.4s .2s cubic-bezier(.3,.7,.2,1) both}}"
           f"@keyframes draw{{from{{stroke-dashoffset:{arc:.1f}}}to{{stroke-dashoffset:0}}}}"
           ".flame{animation:fu .6s 1.2s both}")
    col = [W / 6, W / 2, W * 5 / 6]
    body = f"""<line x1="{W / 3:.1f}" y1="34" x2="{W / 3:.1f}" y2="166" stroke="#{c['rule']}"/>
<line x1="{W * 2 / 3:.1f}" y1="34" x2="{W * 2 / 3:.1f}" y2="166" stroke="#{c['rule']}"/>
<g text-anchor="middle">
<g class="f"{delay(0)}><text class="n" x="{col[0]:.1f}" y="88">{total:,}</text>
<text class="l" x="{col[0]:.1f}" y="120">Total Contributions</text>
<text class="d" x="{col[0]:.1f}" y="146">{esc(f"{first:%b} {first.day}, {first.year}")} - Present</text></g>
<circle cx="{cx}" cy="{cy}" r="{r}" fill="none" stroke="#{c['track']}" stroke-width="6"/>
<circle class="ring" cx="{cx}" cy="{cy}" r="{r}" fill="none" stroke="#{c['accent']}" stroke-width="6" stroke-linecap="round" transform="rotate({rot:.1f} {cx} {cy})"/>
<g transform="translate({cx} {cy - r}) scale(1.15)"><path class="flame" fill="#{c['accent']}" d="M0-10C4-5 7-2 7 3 7 8 4 11 0 11-4 11-7 8-7 3-7-1-4-3-3-7-2-3-1-2 1-1 1-4 1-7 0-10Z"/></g>
<g class="f"{delay(2)}><text class="n" x="{cx}" y="89">{current[0]}</text>
<text class="a" x="{cx}" y="150">Current Streak</text>
<text class="d" x="{cx}" y="172">{esc(fmt_range(current[1], current[2], today))}</text></g>
<g class="f"{delay(4)}><text class="n" x="{col[2]:.1f}" y="88">{longest[0]}</text>
<text class="l" x="{col[2]:.1f}" y="120">Longest Streak</text>
<text class="d" x="{col[2]:.1f}" y="146">{esc(fmt_range(longest[1], longest[2], today))}</text></g>
</g>"""
    label = f"{total:,} total contributions; current streak {current[0]} days; longest streak {longest[0]} days"
    return frame(c, H, label, body, css)


def overview_card(c, s):
    H = 200
    rows = [
        ("Original repos", short(s["repos"])),
        ("Stars earned", short(s["stars"])),
        ("Commits", short(s["commits"])),
        ("Pull requests", short(s["prs"])),
        ("Issues", short(s["issues"])),
        ("Contributed to (last year)", short(s["contributed"])),
    ]
    left = "\n".join(
        f'<g class="f"{delay(i, 0.06)}><text class="l" x="32" y="{70 + i * 21}">{esc(k)}</text>'
        f'<text class="v" x="300" y="{70 + i * 21}" text-anchor="end">{v}</text></g>'
        for i, (k, v) in enumerate(rows)
    )
    bx, bw = 362, 346
    shown = sum(p for _, p, _ in s["langs"]) or 1
    x, segs = bx, []
    for i, (_, pct, color) in enumerate(s["langs"]):
        w = bw * pct / shown
        segs.append(f'<rect class="seg" x="{x:.2f}" y="52" width="{w:.2f}" height="10" fill="{color or "#" + c["muted"]}"{delay(i, 0.07, 0.2)}/>')
        x += w
    half = (len(s["langs"]) + 1) // 2
    lang_rows = []
    for i, (name, pct, color) in enumerate(s["langs"]):
        colx = bx + (0 if i < half else bw / 2 + 12)
        y = 92 + (i % half) * 24
        right = colx + bw / 2 - 12
        lang_rows.append(
            f'<g class="f"{delay(i, 0.05, 0.3)}><circle cx="{colx + 5}" cy="{y - 4}" r="5" fill="{color or "#" + c["muted"]}"/>'
            f'<text class="l" x="{colx + 17}" y="{y}">{esc(name)}</text>'
            f'<text class="d" x="{right:.1f}" y="{y}" text-anchor="end">{pct:.1f}%</text></g>'
        )
    css = (".seg{transform-box:fill-box;transform-origin:left;animation:grow .9s cubic-bezier(.3,.7,.2,1) both}"
           "@keyframes grow{from{transform:scaleX(0)}to{transform:none}}")
    body = f"""<line x1="332" y1="34" x2="332" y2="166" stroke="#{c['rule']}"/>
<text class="h" x="32" y="40">Activity</text>
{left}
<text class="h" x="{bx}" y="40">Top Languages</text>
<clipPath id="bar"><rect x="{bx}" y="52" width="{bw}" height="10" rx="5"/></clipPath>
<rect x="{bx}" y="52" width="{bw}" height="10" rx="5" fill="#{c['track']}"/>
<g clip-path="url(#bar)">{''.join(segs)}</g>
{chr(10).join(lang_rows)}"""
    summary = ", ".join(f"{n} {p:.1f}%" for n, p, _ in s["langs"])
    label = (f"{s['repos']} original repos, {s['stars']} stars, {s['commits']} commits, {s['prs']} pull requests, "
             f"{s['issues']} issues. Top languages: {summary}")
    return frame(c, H, label, body, css)


def activity_card(c, weeks, today):
    H = 200
    x0, x1, top, base = 32, W - 32, 62, 160
    n = len(weeks)
    step = (x1 - x0) / n
    bw = max(step - 3, 2)
    peak = max((v for _, v in weeks), default=0) or 1
    year_total = sum(v for _, v in weeks)
    busiest = max(weeks, key=lambda w: w[1]) if weeks else (today, 0)
    bars, months, last_label_x = [], [], -999
    for i, (start, v) in enumerate(weeks):
        x = x0 + i * step + (step - bw) / 2
        h = max((base - top) * v / peak, 2)
        fill = f"#{c['accent']}" if v else f"#{c['track']}"
        op = "" if v == 0 else f' fill-opacity="{0.35 + 0.65 * v / peak:.2f}"'
        bars.append(f'<rect class="bar" x="{x:.1f}" y="{base - h:.1f}" width="{bw:.1f}" height="{h:.1f}" rx="2" fill="{fill}"{op}'
                    f' style="animation-delay:{0.1 + i * 0.012:.3f}s"/>')
        prev = weeks[i - 1][0] if i else None
        if (prev is None or start.month != prev.month) and x - last_label_x > 34:
            months.append(f'<text class="d" x="{x:.1f}" y="{base + 20}">{start:%b}</text>')
            last_label_x = x
    for frac in (0.5, 1.0):
        y = base - (base - top) * frac
        months.append(f'<line x1="{x0}" y1="{y:.1f}" x2="{x1}" y2="{y:.1f}" stroke="#{c["rule"]}" stroke-dasharray="2 4"/>')
    css = (".bar{transform-box:fill-box;transform-origin:bottom;animation:rise .8s cubic-bezier(.3,.7,.2,1) both}"
           "@keyframes rise{from{transform:scaleY(0)}to{transform:none}}")
    body = f"""<text class="h" x="{x0}" y="40">Last 12 months</text>
<g class="f"{delay(1)}><text class="d" x="{x1}" y="40" text-anchor="end"><tspan class="v">{year_total:,}</tspan> contributions  ·  busiest week <tspan class="v">{busiest[1]:,}</tspan> ({esc(fmt_date(busiest[0], today))})</text></g>
{chr(10).join(months)}
<line x1="{x0}" y1="{base + 0.5}" x2="{x1}" y2="{base + 0.5}" stroke="#{c['rule']}"/>
{chr(10).join(bars)}"""
    label = f"{year_total:,} contributions in the last 52 weeks; busiest week {busiest[1]:,} starting {busiest[0]:%b} {busiest[0].day}"
    return frame(c, H, label, body, css)


# ---------------------------------------------------------------- main

def main():
    out = sys.argv[1] if len(sys.argv) > 1 else "dist"
    os.makedirs(out, exist_ok=True)
    days, today = contribution_days()
    total, first, current, longest = streaks(days, today)
    weeks = weekly(days)
    s = repo_stats()
    print(f"total={total} current={current[0]} longest={longest[0]} last52w={sum(v for _, v in weeks)}")
    print({k: v for k, v in s.items() if k != "langs"}, [(n, round(p, 1)) for n, p, _ in s["langs"]])
    for theme, c in THEMES.items():
        cards = {
            "streak": streak_card(c, total, first, current, longest, today),
            "overview": overview_card(c, s),
            "activity": activity_card(c, weeks, today),
        }
        for name, svg in cards.items():
            with open(os.path.join(out, f"{name}-{theme}.svg"), "w", encoding="utf-8", newline="\n") as f:
                f.write(svg)


if __name__ == "__main__":
    main()
