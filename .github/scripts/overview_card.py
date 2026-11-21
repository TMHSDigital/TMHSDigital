"""Render a combined activity + top-languages card (dark + light SVG).

Usage: python3 overview_card.py <out_dir>
Needs GH_TOKEN (or GITHUB_TOKEN). Writes overview-dark.svg and overview-light.svg,
sized and styled to match streak-*.svg from streak_card.py.

Counts follow github-readme-stats conventions: stars and languages over public,
non-fork repos the user owns; commits from the commit search API; languages
weighted by bytes.
"""
import json
import os
import sys
import urllib.request

USER = "TMHSDigital"
TOP_LANGS = 6

THEMES = {
    "dark": {"bg": "1e1e2e", "text": "ffffff", "accent": "00A0F0", "muted": "8b949e",
             "rule": "3d444d", "border": "1e1e2e", "track": "2d2d3f"},
    "light": {"bg": "ffffff", "text": "1f2328", "accent": "0077B6", "muted": "59636e",
              "rule": "d1d9e0", "border": "d1d9e0", "track": "eaeef2"},
}


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


def collect():
    q = """query($u:String!,$after:String){user(login:$u){
      pullRequests{totalCount} issues{totalCount}
      repositoriesContributedTo(first:1,contributionTypes:[COMMIT,ISSUE,PULL_REQUEST,REPOSITORY]){totalCount}
      repositories(first:100,after:$after,ownerAffiliations:OWNER,isFork:false,privacy:PUBLIC){
        pageInfo{hasNextPage endCursor}
        nodes{stargazerCount languages(first:10,orderBy:{field:SIZE,direction:DESC}){
          edges{size node{name color}}}}}}}"""
    stars, langs, after, user = 0, {}, None, None
    while True:
        user = gql(q, {"u": USER, "after": after})["user"]
        repos = user["repositories"]
        for r in repos["nodes"]:
            stars += r["stargazerCount"]
            for e in r["languages"]["edges"]:
                name = e["node"]["name"]
                size, color = langs.get(name, (0, e["node"]["color"]))
                langs[name] = (size + e["size"], color)
        if not repos["pageInfo"]["hasNextPage"]:
            break
        after = repos["pageInfo"]["endCursor"]
    commits = request(f"https://api.github.com/search/commits?q=author:{USER}&per_page=1")["total_count"]
    total_bytes = sum(s for s, _ in langs.values()) or 1
    top = sorted(langs.items(), key=lambda kv: -kv[1][0])[:TOP_LANGS]
    top = [(name, size / total_bytes * 100, color) for name, (size, color) in top]
    return {
        "stars": stars,
        "commits": commits,
        "prs": user["pullRequests"]["totalCount"],
        "issues": user["issues"]["totalCount"],
        "contributed": user["repositoriesContributedTo"]["totalCount"],
        "langs": top,
    }


def short(n):
    return f"{n / 1000:.1f}k".replace(".0k", "k") if n >= 1000 else str(n)


def esc(s):
    return s.replace("&", "&amp;").replace("<", "&lt;").replace(">", "&gt;")


def render(theme, s):
    c = THEMES[theme]
    font = "'Segoe UI', Ubuntu, 'Helvetica Neue', Arial, sans-serif"
    W, H = 495, 195
    rows = [
        ("Stars earned", short(s["stars"])),
        ("Commits", short(s["commits"])),
        ("Pull requests", short(s["prs"])),
        ("Issues", short(s["issues"])),
        ("Contributed to (last year)", short(s["contributed"])),
    ]
    left = "\n".join(
        f'<text class="l" x="28" y="{66 + i * 25}">{esc(k)}</text>'
        f'<text class="v" x="222" y="{66 + i * 25}" text-anchor="end">{v}</text>'
        for i, (k, v) in enumerate(rows)
    )

    bx, bw = 272, 196
    x, segs = bx, []
    shown = sum(p for _, p, _ in s["langs"]) or 1
    for name, pct, color in s["langs"]:
        w = bw * pct / shown
        segs.append(f'<rect x="{x:.2f}" y="46" width="{w:.2f}" height="8" fill="{color or "#" + c["muted"]}"/>')
        x += w
    lang_rows = "\n".join(
        f'<circle cx="{bx + 4}" cy="{77 + i * 19}" r="4" fill="{color or "#" + c["muted"]}"/>'
        f'<text class="l" x="{bx + 14}" y="{81 + i * 19}">{esc(name)}</text>'
        f'<text class="p" x="{bx + bw}" y="{81 + i * 19}" text-anchor="end">{pct:.1f}%</text>'
        for i, (name, pct, color) in enumerate(s["langs"])
    )
    summary = ", ".join(f"{n} {p:.1f}%" for n, p, _ in s["langs"])
    return f"""<svg xmlns="http://www.w3.org/2000/svg" width="{W}" height="{H}" viewBox="0 0 {W} {H}" role="img" aria-label="GitHub activity: {s['stars']} stars, {s['commits']} commits, {s['prs']} pull requests, {s['issues']} issues. Top languages: {esc(summary)}">
<title>GitHub activity and top languages</title>
<style>
.h{{font:700 14px {font};fill:#{c['accent']}}}
.l{{font:400 13px {font};fill:#{c['text']}}}
.v{{font:700 13px {font};fill:#{c['text']}}}
.p{{font:400 12px {font};fill:#{c['muted']}}}
</style>
<rect x="0.5" y="0.5" width="{W - 1}" height="{H - 1}" rx="6" fill="#{c['bg']}" stroke="#{c['border']}"/>
<line x1="247.5" y1="28" x2="247.5" y2="170" stroke="#{c['rule']}" stroke-width="1"/>
<text class="h" x="28" y="36">Activity</text>
{left}
<text class="h" x="{bx}" y="36">Top Languages</text>
<clipPath id="bar"><rect x="{bx}" y="46" width="{bw}" height="8" rx="4"/></clipPath>
<rect x="{bx}" y="46" width="{bw}" height="8" rx="4" fill="#{c['track']}"/>
<g clip-path="url(#bar)">
{chr(10).join(segs)}
</g>
{lang_rows}
</svg>
"""


def main():
    out = sys.argv[1] if len(sys.argv) > 1 else "dist"
    os.makedirs(out, exist_ok=True)
    s = collect()
    print({k: v for k, v in s.items() if k != "langs"}, [(n, round(p, 1)) for n, p, _ in s["langs"]])
    for theme in THEMES:
        with open(os.path.join(out, f"overview-{theme}.svg"), "w", encoding="utf-8", newline="\n") as f:
            f.write(render(theme, s))


if __name__ == "__main__":
    main()
