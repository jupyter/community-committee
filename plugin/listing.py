#!/usr/bin/env python3
# With many thanks, based on work by Chris Holdgraf
#   https://github.com/choldgraf/choldgraf.github.io/blob/35f2a24818ec73304a9769153796a952c0ec2561/src/blogpost.py

import argparse
import json
import sys
from pathlib import Path

import pandas as pd
from feedgen.feed import FeedGenerator
from yaml import safe_load

ROOT = Path(__file__).parent.parent
LISTING_DIR = ROOT / "meeting-notes"
SUMMARY_WORDS = 50

DEFAULTS = {"number": 0}
PLUGIN_SPEC = {
    "name": "A document listing",
    "directives": [
        {
            "name": "listing",
            "doc": "A listing of documents as cards, sorted by date.",
            "arg": {},
            "options": {
                "number": {
                    "type": "int",
                    "doc": "The number of posts to include (default: 0, or all posts)",
                },
            },
        },
    ],
}


def aggregate_posts() -> list[dict]:
    """Aggregate all posts from the markdown and ipynb files."""
    posts = []
    for ifile in LISTING_DIR.rglob("**/*.md"):
        if "drafts" in str(ifile):
            continue

        text = ifile.read_text()
        try:
            _, meta, content = text.split("---", 2)
        except Exception:
            print(f"Skipping file with malformed frontmatter: {ifile}", file=sys.stderr)
            continue

        # Load in YAML metadata
        meta = safe_load(meta)
        meta["path"] = ifile.relative_to(ROOT).with_suffix("")
        if "title" not in meta:
            lines = text.splitlines()
            for ii in lines:
                if ii.strip().startswith("#"):
                    meta["title"] = ii.replace("#", "").strip()
                    break

        # Summarize content
        skip_lines = ["#", "--", "%", "++"]
        content = "\n".join(
            ii
            for ii in content.splitlines()
            if not any(ii.startswith(char) for char in skip_lines)
        )
        words = " ".join(content.split(" ")[:SUMMARY_WORDS])
        if "author" not in meta or not meta["author"]:
            meta["author"] = "TODO: Get from myst.yml"
        meta["content"] = meta.get("description", words)
        posts.append(meta)

    if not posts:
        return pd.DataFrame()

    posts = pd.DataFrame(posts)
    # TODO: Why do we care about TZ?
    posts["date"] = pd.to_datetime(posts["date"]).dt.tz_localize("US/Pacific")
    posts = posts.dropna(subset=["date"])
    return posts.sort_values("date", ascending=False)


def cards_from_posts(posts, /) -> list[dict]:
    def ast_text(value, **kwargs):
        return {"type": "text", "value": value, **kwargs}

    def ast_strong(children, **kwargs):
        return {"type": "strong", "children": children, **kwargs}

    cards = []
    for _, irow in posts.iterrows():
        cards.append(
            {
                "type": "card",
                "url": f"{irow['path'].with_suffix('')}",
                "children": [
                    {"type": "cardTitle", "children": [ast_text(irow["title"])]},
                    {"type": "paragraph", "children": [ast_text(irow["content"])]},
                    {
                        "type": "footer",
                        "children": [
                            ast_strong([ast_text("Date: ")]),
                            ast_text(f"{irow['date']:%B %d, %Y} | "),
                            ast_strong([ast_text("Author: ")]),
                            ast_text(f"{irow['author'][0]['name']}"),
                        ],
                    },
                ],
            },
        )
    return cards


def write_feeds(*, posts) -> None:
    """Generate RSS and Atom feeds and write them as XML."""
    # TODO: Get URL from myst.yaml
    base_url = "https://example.com"

    fg = FeedGenerator()

    fg.id(base_url)
    fg.title("TODO: Get title from myst.yaml")
    fg.author(
        {
            "name": "TODO: Get author from individual posts",
            "email": "TODO: Get email from individual posts",
        },
    )
    fg.link(href=base_url, rel="alternate")
    fg.logo("TODO: Get logo from myst.yaml")
    fg.subtitle("TODO: Get description from myst.yaml")
    # TODO: This link is going to be wrong because it doesn't take into account
    #       LISTING_DIR
    fg.link(href=f"{base_url}/rss.xml", rel="self")
    fg.language("en")

    # Add all posts
    for _, irow in posts.iterrows():
        fe = fg.add_entry()
        fe.id(f"{base_url}/{irow['path']}")
        fe.published(irow["date"])
        fe.title(irow["title"])
        fe.link(href=f"{base_url}/{irow['path']}")
        fe.content(content=irow["content"])

    # Write an RSS feed with latest posts
    # TODO: Only write this to the build output, don't commit it
    fg.atom_file(LISTING_DIR / "atom.xml", pretty=True)
    fg.rss_file(LISTING_DIR / "rss.xml", pretty=True)


def print_result(content, /):
    """Write result as JSON to stdout.

    :param content: content to write to stdout
    """

    # Format result and write to stdout
    json.dump(content, sys.stdout, indent=2)
    # Successfully exit
    raise SystemExit(0)


def run_directive(name, /) -> None:
    """Execute a directive with the given name and data

    :param name: name of the directive to run
    """
    assert name == "listing"

    data = json.load(sys.stdin)

    opts = data["node"].get("options", {})

    posts = aggregate_posts()
    write_feeds(posts=posts)

    cards = cards_from_posts(posts)
    number = int(opts.get("number", DEFAULTS["number"]))
    output = cards if number == 0 else cards[:number]
    print_result(output)


if __name__ == "__main__":
    parser = argparse.ArgumentParser()
    group = parser.add_mutually_exclusive_group()
    group.add_argument("--role")
    group.add_argument("--directive")
    group.add_argument("--transform")
    args = parser.parse_args()

    if args.directive:
        run_directive(args.directive)
    elif args.transform:
        raise NotImplementedError
    elif args.role:
        raise NotImplementedError
    else:
        print_result(PLUGIN_SPEC)