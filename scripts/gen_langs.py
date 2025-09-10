#!/usr/bin/env python3
import os, sys, requests
from collections import defaultdict
import matplotlib
matplotlib.use("Agg")
import matplotlib.pyplot as plt
from matplotlib.lines import Line2D
import numpy as np

# -------- Config via env --------
GITHUB_API     = "https://api.github.com"
TOKEN          = os.getenv("GITHUB_TOKEN")
USERNAME       = os.getenv("USERNAME")
REPO_INCLUDE_FORKS = os.getenv("INCLUDE_FORKS", "true").lower() == "true"
REPO_VISIBILITY    = os.getenv("VISIBILITY", "all")
TOP_N          = int(os.getenv("TOP_N", "25"))
MIN_PERCENT    = float(os.getenv("MIN_PERCENT", "1.0"))
SKIP_LANGS     = {s.strip() for s in os.getenv("SKIP_LANGS", "").split(",") if s.strip()}
# --------------------------------

if not TOKEN or not USERNAME:
    print("ERROR: GITHUB_TOKEN and USERNAME env vars are required.", file=sys.stderr)
    sys.exit(1)

session = requests.Session()
session.headers.update({
    "Authorization": f"Bearer {TOKEN}",
    "Accept": "application/vnd.github+json",
    "X-GitHub-Api-Version": "2022-11-28",
})

def list_repos(user: str):
    repos = []
    url = f"{GITHUB_API}/users/{user}/repos"
    params = {
        "per_page": 100,
        "type": "owner",
        "sort": "pushed",
        "direction": "desc",
        "visibility": REPO_VISIBILITY,
    }
    while url:
        r = session.get(url, params=params, timeout=30)
        r.raise_for_status()
        repos.extend(r.json())
        url = None
        if "link" in r.headers:
            for part in r.headers["link"].split(","):
                if 'rel="next"' in part:
                    url = part[part.find("<")+1:part.find(">")]
                    params = {}
                    break
    return repos

def repo_languages(owner: str, repo: str):
    r = session.get(f"{GITHUB_API}/repos/{owner}/{repo}/languages", timeout=30)
    r.raise_for_status()
    return r.json()

def human_pct(x: float) -> str:
    return f"{x:.2f}%"

def main():
    repos = list_repos(USERNAME)
    lang_bytes = defaultdict(int)
    considered = 0

    for repo in repos:
        if repo.get("archived"):
            continue
        if not REPO_INCLUDE_FORKS and repo.get("fork"):
            continue
        langs = repo_languages(USERNAME, repo["name"])
        if langs:
            considered += 1
        for k, v in langs.items():
            if k in SKIP_LANGS:
                continue
            lang_bytes[k] += int(v)

    if not lang_bytes:
        print("No language data found.")
        return

    total = sum(lang_bytes.values())
    items = sorted(lang_bytes.items(), key=lambda kv: kv[1], reverse=True)[:TOP_N]
    filtered = [(name, v) for name, v in items if (v * 100.0 / total) >= MIN_PERCENT]
    if not filtered:
        filtered = items

    labels = [name for name, _ in filtered]
    perc   = [v * 100.0 / total for _, v in filtered]

    # Stacked bar chart (progress-bar style)
    widths = np.array(perc) / 100.0
    lefts = np.cumsum(np.insert(widths[:-1], 0, 0))
    cmap = plt.get_cmap("tab20")
    colors = [cmap(i % 20) for i in range(len(widths))]

    fig, ax = plt.subplots(figsize=(10, 2.2))
    for w, l, c in zip(widths, lefts, colors):
        ax.barh(y=0, width=w, left=l, height=0.35, color=c)

    ax.set_xlim(0, 1)
    ax.set_ylim(-0.5, 0.5)
    ax.set_yticks([])
    ax.set_xticks([])
    ax.set_frame_on(False)
    ax.set_title("All Used Languages in Account", pad=16, fontsize=12)

    handles = [Line2D([0], [0], marker='o', color='none', markerfacecolor=c, markersize=10,
                      label=f"{name} {human_pct(p)}")
               for name, p, c in zip(labels, perc, colors)]
    ncol = 2 if len(handles) <= 6 else 3
    ax.legend(handles=handles, loc="upper left",
              bbox_to_anchor=(0.0, -0.25), frameon=False, ncol=ncol, handlelength=1.0)

    fig.tight_layout()

    out_dir = os.path.join("assets")
    os.makedirs(out_dir, exist_ok=True)
    fig.savefig(os.path.join(out_dir, "languages.svg"), format="svg", bbox_inches="tight")
    fig.savefig(os.path.join(out_dir, "languages.png"), format="png", dpi=200, bbox_inches="tight")
    plt.close(fig)

    print("✅ Languages chart updated successfully")

if __name__ == "__main__":
    main()
