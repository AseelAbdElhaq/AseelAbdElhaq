#!/usr/bin/env python3
import os, sys, requests
from collections import defaultdict

# -------- Config --------
GITHUB_API = "https://api.github.com"
TOKEN = os.getenv("GITHUB_TOKEN")
USERNAME = os.getenv("USERNAME")  # e.g., "AseelAbdElhaq"
REPO_INCLUDE_FORKS = os.getenv("INCLUDE_FORKS", "false").lower() == "true"
REPO_VISIBILITY = os.getenv("VISIBILITY", "all")  # "all" | "public" | "private"
TOP_N = int(os.getenv("TOP_N", "10"))  # how many languages to show
# ------------------------

if not TOKEN or not USERNAME:
    print("ERROR: GITHUB_TOKEN and USERNAME env vars are required.", file=sys.stderr)
    sys.exit(1)

# Use a non-interactive backend before importing pyplot
import matplotlib
matplotlib.use("Agg")
import matplotlib.pyplot as plt

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
    return f"{x:.1f}%"

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
            lang_bytes[k] += int(v)

    if not lang_bytes:
        print("No language data found.")
        return

    total = sum(lang_bytes.values())
    items = sorted(lang_bytes.items(), key=lambda kv: kv[1], reverse=True)
    # keep top N; rest => "Other"
    top = items[:TOP_N]
    others = items[TOP_N:]
    other_sum = sum(v for _, v in others)
    if other_sum > 0:
        top.append(("Other", other_sum))

    labels = [name for name, _ in top]
    sizes = [v for _, v in top]
    perc = [v * 100.0 / total for v in sizes]
    label_fmt = [f"{labels[i]} ({human_pct(perc[i])})" for i in range(len(labels))]

    # Ensure output dir
    out_dir = os.path.join("assets")
    os.makedirs(out_dir, exist_ok=True)
    svg_path = os.path.join(out_dir, "languages.svg")
    png_path = os.path.join(out_dir, "languages.png")

    # Pie chart
    plt.figure(figsize=(7, 7))
    wedges, _texts = plt.pie(sizes, startangle=90)
    plt.legend(wedges, label_fmt, title="Languages", loc="center left", bbox_to_anchor=(1, 0.5))
    plt.title(f"{owner}'s Most Used Languages (by code size)")
    plt.tight_layout()
    plt.savefig(svg_path, format="svg", bbox_inches="tight")
    plt.savefig(png_path, format="png", dpi=200, bbox_inches="tight")
    plt.close()

    # Markdown summary (optional)
    lines = ["# Auto-Updated Language Breakdown", f"_Analyzed {considered} repositories (owner repos, forks={'included' if REPO_INCLUDE_FORKS else 'excluded'})._", ""]
    for name, v in items[:TOP_N]:
        pct = (v * 100.0 / total)
        lines.append(f"- **{name}** — {human_pct(pct)}")
    if other_sum > 0:
        lines.append(f"- **Other** — {human_pct(other_sum * 100.0 / total)}")
    with open(os.path.join(out_dir, "languages.md"), "w", encoding="utf-8") as f:
        f.write("\n".join(lines) + "\n")

    print(f"Wrote {svg_path}, {png_path}, and assets/languages.md")

if __name__ == "__main__":
    main()
