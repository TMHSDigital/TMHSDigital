"""Rewrite the TOP-REPOS block in README.md with the user's 3 most-starred repos.

Ranks public, non-fork repos owned by the user (excluding the profile repo) by
stars, ties broken by name. Star counts in the badges are rendered live by
shields.io, so README.md only changes when the top 3 or their order changes.
"""
import json
import os
import re
import sys
import urllib.parse
import urllib.request

USER = "TMHSDigital"
COUNT = 3
README = os.path.join(os.path.dirname(__file__), "..", "..", "README.md")
START, END = "<!-- TOP-REPOS:START -->", "<!-- TOP-REPOS:END -->"
LABEL = (
    '<picture><source media="(prefers-color-scheme: dark)" srcset="assets/label-top-projects-dark.svg" />'
    '<img src="assets/label-top-projects-light.svg" alt="Top projects" /></picture>'
)


def fetch_repos():
    token = os.environ.get("GH_TOKEN") or os.environ.get("GITHUB_TOKEN")
    repos, page = [], 1
    while True:
        url = f"https://api.github.com/users/{USER}/repos?type=owner&per_page=100&page={page}"
        req = urllib.request.Request(url, headers={"Accept": "application/vnd.github+json"})
        if token:
            req.add_header("Authorization", f"Bearer {token}")
        with urllib.request.urlopen(req) as resp:
            batch = json.load(resp)
        if not batch:
            return repos
        repos.extend(batch)
        page += 1


def badge(name):
    q = urllib.parse.urlencode(
        {
            "style": "flat-square",
            "label": f"{name} ★",
            "labelColor": "1e1e2e",
            "color": "00A0F0",
        },
        quote_via=urllib.parse.quote,
    )
    src = f"https://img.shields.io/github/stars/{USER}/{name}?{q}"
    return (
        f'<a href="https://github.com/{USER}/{name}">'
        f'<img src="{src.replace("&", "&amp;")}" alt="{name} stars" /></a>'
    )


def main():
    repos = [
        r for r in fetch_repos()
        if not r["fork"] and not r["private"] and r["name"].lower() != USER.lower()
    ]
    if len(repos) < COUNT:
        sys.exit(f"expected at least {COUNT} repos, got {len(repos)}")
    top = sorted(repos, key=lambda r: (-r["stargazers_count"], r["name"].lower()))[:COUNT]
    for r in top:
        print(f'{r["stargazers_count"]:>5}  {r["name"]}')

    block = (
        f"{START}\n<table align=\"center\"><tr><td align=\"center\">\n"
        f"{LABEL}\n<br>\n"
        + "&nbsp;\n".join(badge(r["name"]) for r in top)
        + f"\n</td></tr></table>\n{END}"
    )
    with open(README, encoding="utf-8") as f:
        text = f.read()
    pattern = re.compile(re.escape(START) + r".*?" + re.escape(END), re.S)
    if not pattern.search(text):
        sys.exit("TOP-REPOS markers not found in README.md")
    new = pattern.sub(lambda _: block, text)
    if new != text:
        with open(README, "w", encoding="utf-8", newline="\n") as f:
            f.write(new)
        print("README.md updated")
    else:
        print("README.md unchanged")


if __name__ == "__main__":
    main()
