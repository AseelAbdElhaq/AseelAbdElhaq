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
})

def list_repos(user: str):
    repos = []
    url = f"{GITHUB_API}/users/{user}/repos"
    params = {"per_page": 100, "type": "owner", "sort": "pushed", "direction": "desc", "visibility": REPO_VISIBILITY}
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

    for repo in repos:
        if repo.get("archived"):
            continue
        if not REPO_INCLUDE_FORKS and repo.get("fork"):
            continue
        langs = repo_languages(USERNAME, repo["name"])
        for k, v in langs.items():
            if k in SKIP_LANGS:
                continue
            lang_bytes[k] += int(v)

    if not lang_bytes:
        print("No language data found.")
        return

    total = sum(lang_bytes.values())
    filtered = [(name, v) for name, v in lang_bytes.items() if (v * 100.0 / total) >= MIN_PERCENT]
    filtered.sort(key=lambda kv: kv[1], reverse=True)

    labels = [name for name, _ in filtered]
    perc   = [v * 100.0 / total for _, v in filtered]

    # ----- Chart style -----
    widths = np.array(perc) / 100.0
    lefts = np.cumsum(np.insert(widths[:-1], 0, 0))
    cmap = plt.get_cmap("tab20")
    colors = [cmap(i % 20) for i in range(len(widths))]

    fig, ax = plt.subplots(figsize=(8, 3))
    fig.patch.set_facecolor("#F0F8FF")   # light blue background like GitHub card
    ax.set_facecolor("#F0F8FF")

    for w, l, c in zip(widths, lefts, colors):
        ax.barh(y=0, width=w, left=l, height=0.3, color=c)

    ax.set_xlim(0, 1)
    ax.set_ylim(-0.6, 0.6)
    ax.set_yticks([])
    ax.set_xticks([])
    ax.set_frame_on(False)

    # Title
    ax.text(0, 0.55, "All Used Languages", fontsize=12, fontweight="bold", color="#0A66C2")

    # Legend
    handles = [Line2D([0], [0], marker='o', color='none', markerfacecolor=c, markersize=8,
                      label=f"{name} {human_pct(p)}")
               for name, p, c in zip(labels, perc, colors)]
    ax.legend(handles=handles, loc="upper left", bbox_to_anchor=(0, -0.4), frameon=False, ncol=2)

    fig.tight_layout()

    # ----- Save files -----
    out_dir = os.path.join("assets")
    os.makedirs(out_dir, exist_ok=True)

    svg_path = os.path.join(out_dir, "languages.svg")
    png_path = os.path.join(out_dir, "languages.png")

    fig.savefig(svg_path, format="svg", bbox_inches="tight")
    fig.savefig(png_path, format="png", dpi=200, bbox_inches="tight")
    plt.close(fig)

    # Debug output
    print("✅ Chart generated successfully")
    print(f"SVG saved to: {svg_path}, exists? {os.path.exists(svg_path)}")
    print(f"PNG saved to: {png_path}, exists? {os.path.exists(png_path)}")

if __name__ == "__main__":
    main()
