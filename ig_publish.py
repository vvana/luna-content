"""
Publishes due items from ig-queue.json to Instagram via the Graph API.

Runs inside GitHub Actions on a cron schedule (see .github/workflows/
publish.yml). Media files live in this repo under media/ and are served
to Meta as raw.githubusercontent.com URLs.

Queue item format (times are Moscow local, same as tg-queue.json):
    { "when": "2026-08-11T19:00", "type": "reel",
      "file": "media/2026-08-11-zavtra-zatmenie.mp4", "caption": "..." }
    { "when": "2026-08-10T19:00", "type": "carousel",
      "files": ["media/2026-08-10-goroskop/01.png", ...], "caption": "..." }

An item is published when its time has come but no more than
STALE_HOURS ago (so a dead token can't cause a flood of ancient posts
once fixed). Published items get posted=true + media_id.
"""

import json
import os
import time
import urllib.parse
from datetime import datetime, timedelta, timezone
from pathlib import Path

import requests

API = "https://graph.instagram.com/v23.0"
RAW = "https://raw.githubusercontent.com/vvana/luna-content/main/"
MSK = timezone(timedelta(hours=3))
STALE_HOURS = 8
QUEUE = Path(__file__).parent / "ig-queue.json"

TOKEN = os.environ.get("IG_ACCESS_TOKEN", "")
IG_ID = os.environ.get("IG_USER_ID", "")


def api(method: str, path: str, **params) -> dict:
    params["access_token"] = TOKEN
    r = requests.request(method, f"{API}/{path}", params=params, timeout=120)
    data = r.json()
    if "error" in data:
        msg = data["error"].get("message", str(data["error"]))
        raise RuntimeError(f"{path}: {msg}")
    return data


def wait_ready(container_id: str, tries: int = 40):
    """Poll a media container until Meta finishes processing it."""
    for _ in range(tries):
        status = api("GET", container_id, fields="status_code")["status_code"]
        if status == "FINISHED":
            return
        if status == "ERROR":
            raise RuntimeError(f"container {container_id} failed processing")
        time.sleep(10)
    raise RuntimeError(f"container {container_id} still not ready")


def raw_url(repo_path: str) -> str:
    return RAW + urllib.parse.quote(repo_path)


def publish_reel(item: dict) -> str:
    container = api("POST", f"{IG_ID}/media",
                    media_type="REELS",
                    video_url=raw_url(item["file"]),
                    caption=item.get("caption", ""),
                    share_to_feed="true")["id"]
    wait_ready(container)
    return api("POST", f"{IG_ID}/media_publish", creation_id=container)["id"]


def publish_carousel(item: dict) -> str:
    children = []
    for f in item["files"]:
        children.append(api("POST", f"{IG_ID}/media",
                            image_url=raw_url(f),
                            is_carousel_item="true")["id"])
    for cid in children:
        wait_ready(cid, tries=12)
    container = api("POST", f"{IG_ID}/media",
                    media_type="CAROUSEL",
                    children=",".join(children),
                    caption=item.get("caption", ""))["id"]
    wait_ready(container)
    return api("POST", f"{IG_ID}/media_publish", creation_id=container)["id"]


def main():
    if not TOKEN or not IG_ID:
        print("IG_ACCESS_TOKEN / IG_USER_ID secrets not configured yet - "
              "nothing to do")
        return
    queue = json.loads(QUEUE.read_text(encoding="utf-8"))
    now = datetime.now(MSK)
    published = 0
    for item in queue:
        if item.get("posted"):
            continue
        when = datetime.fromisoformat(item["when"]).replace(tzinfo=MSK)
        if when > now:
            continue
        if now - when > timedelta(hours=STALE_HOURS):
            print(f"skip stale: {item['when']} ({item['type']})")
            continue
        print(f"publishing {item['type']} scheduled {item['when']} ...")
        if item["type"] == "reel":
            media_id = publish_reel(item)
        elif item["type"] == "carousel":
            media_id = publish_carousel(item)
        else:
            raise ValueError(f"unknown type {item['type']}")
        item["posted"] = True
        item["media_id"] = media_id
        QUEUE.write_text(json.dumps(queue, ensure_ascii=False, indent=2),
                         encoding="utf-8")
        published += 1
        print(f"  published, media_id={media_id}")
    print(f"done: {published} published")


if __name__ == "__main__":
    main()
