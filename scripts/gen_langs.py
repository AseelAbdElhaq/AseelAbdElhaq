#!/usr/bin/env python3
import os, sys, requests
from collections import defaultdict

# -------- Config via env --------
GITHUB_API     = "https://api.github.com"
TOKEN          = os.getenv("GITHUB_TOKEN")
USERNAME       = os.getenv("USERNAME")                # e.g., "AseelAbdElhaq"
REPO_INCLUDE_FORKS = os.getenv("INCLUDE_FORKS", "true").lower() == "true"
REPO_VISIBILITY    = os.getenv("VISIBILITY", "all")   # "all" | "public" | "private"
TOP_N          = int(os.getenv("TOP_N", "25"))        # keep many; we filter by percent anyway
MIN_PERCENT    = float(os.getenv("MIN_PERCENT", "1.0"))  # drop tiny languages (< this %)
SKIP_LANGS     = {s.strip() for s in os.getenv("SKIP_LANGS", "").split(",") if s.strip()}
# --------------------------------

if not TOKEN or not USERNAME:
    print("ERROR: GITHUB_TOKEN and USERNAME env vars are required.", file=sys.stderr)
    sys.exit(1)

# Use a non-interactive backend before importing pyplot
import matplotlib
matplotlib.use("Agg")
import matplotlib.pyplot as plt
from matplotlib.lines import Line2D
import matplotlib.patches as patches
import numpy as np

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
        # pagination via Link header
        url = None
        if "link" in r.headers:
            for part in r.headers["link"].split(","):
                if 'rel="next"' in part:
                    url = part[part.find("<")+1:part.find(">")]
                    params = {}  # already embedded in next link
                    break
    return repos

def repo_languages(owner: str, repo: str):
    r = session.get(f"{GITHUB_API}/repos/{owner}/{repo}/languages", timeout=30)
    r.raise_for_status()
    return r.json()  # { "Python": 1234, "C": 567, ... }

def human_pct(x: float) -> str:
    # round to 2 decimals for legend
    return f"{x:.2f}%"

def main():
    owner = USERNAME
    repos = list_repos(owner)
    if not repos:
        print("No repositories found for user:", owner)
        return

    lang_bytes = defaultdict(int)
    considered = 0

    for repo in repos:
        if repo.get("archived"):
            continue
        if not REPO_INCLUDE_FORKS and repo.get("fork"):
            continue
        langs = repo_languages(owner, repo["name"])
        if langs:
            considered += 1
        for k, v in langs.items():
            if k in SKIP_LANGS:
                continue
            lang_bytes[k] += int(v)

    if not lang_bytes:
        print("No language data found.")
        return

    # Sort and compute percentages
    total = sum(lang_bytes.values())
    items = sorted(lang_bytes.items(), key=lambda kv: kv[1], reverse=True)[:TOP_N]
    # Filter out tiny/noise languages
    filtered = [(name, v) for name, v in items if (v * 100.0 / total) >= MIN_PERCENT]
    if not filtered:
        filtered = items  # fallback, just in case MIN_PERCENT too high

    labels = [name for name, _ in filtered]
    sizes  = [v for _, v in filtered]
    perc   = [v * 100.0 / total for v in sizes]

    # ----- Build stacked horizontal bar (like your example) -----
    # Normalize widths to 1.0
    widths = np.array(perc) / 100.0
    lefts = np.cumsum(np.insert(widths[:-1], 0, 0))

    # Colors: use tab20 cycling to keep it pleasant
    cmap = plt.get_cmap("tab20")
    colors = [cmap(i % 20) for i in range(len(widths))]

    # Figure style: wide, short bar
    fig, ax = plt.subplots(figsize=(10, 2.2))
    # Draw the stacked bar
    for w, l, c in zip(widths, lefts, colors):
        ax.barh(y=0, width=w, left=l, height=0.35, color=c)

    # Remove axes for a clean card look
    ax.set_xlim(0, 1)
    ax.set_ylim(-0.5, 0.5)
    ax.set_yticks([])
    ax.set_xticks([])
    ax.set_frame_on(False)

    # Title
    ax.set_title("All Used Languages in Account", pad=16, fontsize=12)

    # Legend with round dots and percentages (HTML, JavaScript, Java etc.)
    handles = []
    for name, p, c in zip(labels, perc, colors):
        handles.append(Line2D([0], [0], marker='o', color='none', markerfacecolor=c, markersize=10,
                              label=f"{name} {human_pct(p)}"))
    # Place legend below the bar, multiple columns if many items
    ncol = 2 if len(handles) <= 6 else 3
    leg = ax.legend(handles=handles, loc="upper left",
                    bbox_to_anchor=(0.0, -0.25), frameon=False, ncol=ncol, handlelength=1.0)

    fig.tight_layout()
    # ------------------------------------------------------------

    # Ensure output dir
    out_dir = os.path.join("assets")
    os.makedirs(out_dir, exist_ok=True)
    svg_path = os.path.join(out_dir, "languages.svg")
    png_path = os.path.join(out_dir, "languages.png")

    fig.savefig(svg_path, format="svg", bbox_inches="tight")
    fig.savefig(png_path, format="png", dpi=200, bbox_inches="tight")
    plt.close(fig)

    # Markdown summary (optional)
    lines = ["# Auto-Updated Language Breakdown",
             f"_Analyzed {considered} repositories (forks included, archived excluded)._", ""]
    for name, p in zip(labels, perc):
        lines.append(f"- **{name}** — {human_pct(p)}")
    with open(os.path.join(out_dir, "languages.md"), "w", encoding="utf-8") as f:
        f.write("\n".join(lines) + "\n")

    print(f"Wrote {svg_path}, {png_path}, and assets/languages.md")

if __name__ == "__main__":
    main()
