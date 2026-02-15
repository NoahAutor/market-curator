"""
Reddit .json endpoint client with rate limiting.

Searches Reddit via public .json endpoints (no API key needed).
Enforces a 7-second minimum delay between ALL requests and handles
429 rate-limit responses with Retry-After backoff.
"""

import time
import requests

REDDIT_SEARCH_URL = "https://www.reddit.com/search.json"
MIN_DELAY = 7  # seconds between requests


class RedditChecker:
    def __init__(self, status_callback=None):
        self.session = requests.Session()
        self.session.headers.update({
            "User-Agent": "PolymarketValidator/1.0"
        })
        self._last_request = 0
        self._status_callback = status_callback

    def _report_status(self, message):
        """Report status to UI callback if available, otherwise print."""
        if self._status_callback:
            self._status_callback(message)
        else:
            print(message)

    def _rate_limit(self):
        """Enforce 7-second minimum delay between requests."""
        elapsed = time.time() - self._last_request
        if elapsed < MIN_DELAY:
            time.sleep(MIN_DELAY - elapsed)

    def search(self, query, sort="relevance", timeframe="month", limit=50,
               _retries=0):
        """Search Reddit and return parsed post dicts.

        Args:
            query: Search query string.
            sort: One of 'relevance', 'top', 'new'.
            timeframe: One of 'week', 'month', 'year', 'all'.
            limit: Max results per request (max 100).

        Returns:
            List of post dicts with: title, score, num_comments,
            upvote_ratio, subreddit, created_utc, permalink, id.

        Raises:
            requests.RequestException: On network errors or after max retries.
        """
        self._rate_limit()

        resp = self.session.get(
            REDDIT_SEARCH_URL,
            params={"q": query, "sort": sort, "t": timeframe, "limit": limit},
            timeout=15,
        )
        self._last_request = time.time()

        # Handle rate limiting with retry cap
        if resp.status_code == 429:
            if _retries >= 2:
                self._report_status(
                    "Reddit rate limit: max retries reached, skipping query."
                )
                return []
            retry_after = int(resp.headers.get("Retry-After", 60))
            self._report_status(
                f"Reddit rate limited. Retrying in {retry_after}s..."
            )
            time.sleep(retry_after)
            return self.search(query, sort, timeframe, limit,
                               _retries=_retries + 1)

        resp.raise_for_status()
        return self._parse_posts(resp.json())

    def _parse_posts(self, data):
        """Extract post dicts from Reddit .json response."""
        posts = []
        children = data.get("data", {}).get("children", [])

        for child in children:
            if child.get("kind") != "t3":
                continue
            post = child["data"]
            posts.append({
                "id": post.get("id", ""),
                "title": post.get("title", ""),
                "score": post.get("score", 0),
                "num_comments": post.get("num_comments", 0),
                "upvote_ratio": post.get("upvote_ratio", 0.0),
                "subreddit": post.get("subreddit", ""),
                "created_utc": post.get("created_utc", 0),
                "permalink": post.get("permalink", ""),
            })

        return posts

    def multi_search(self, query):
        """Run the same query with three sort orders and deduplicate.

        Searches with sort=relevance (month), sort=top (month), and
        sort=new (week), then deduplicates by post ID.

        Args:
            query: Search query string.

        Returns:
            List of unique post dicts, sorted by score descending.
        """
        seen_ids = set()
        combined = []

        search_configs = [
            {"sort": "relevance", "timeframe": "month"},
            {"sort": "top", "timeframe": "month"},
            {"sort": "new", "timeframe": "week"},
        ]

        for config in search_configs:
            try:
                posts = self.search(
                    query,
                    sort=config["sort"],
                    timeframe=config["timeframe"],
                )
                for post in posts:
                    if post["id"] not in seen_ids:
                        seen_ids.add(post["id"])
                        combined.append(post)
            except requests.RequestException as e:
                self._report_status(
                    f"Reddit search failed ({config['sort']}): {e}"
                )
                continue

        combined.sort(key=lambda p: p["score"], reverse=True)
        return combined


if __name__ == "__main__":
    print("Searching Reddit for 'Taylor Swift Travis Kelce'...")
    print(f"(3 searches with {MIN_DELAY}s delay between each)\n")

    checker = RedditChecker()
    results = checker.multi_search("Taylor Swift Travis Kelce")

    print(f"Total unique posts found: {len(results)}\n")
    print("Top 5 results:")
    print("-" * 70)

    for post in results[:5]:
        print(f"  r/{post['subreddit']} | score: {post['score']} | "
              f"comments: {post['num_comments']}")
        print(f"  {post['title']}")
        print(f"  https://reddit.com{post['permalink']}")
        print()
