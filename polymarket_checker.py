"""
Polymarket Gamma API client with local keyword search over cached events.

Fetches all active events from the Gamma API, handles the JSON-string-in-JSON
quirk for outcomePrices/outcomes, and provides keyword matching against event
titles and market questions.
"""

import json
import requests
import streamlit as st

GAMMA_API_URL = "https://gamma-api.polymarket.com/events"


@st.cache_data(ttl=1800)
def load_all_events():
    """Fetch all active Polymarket events with pagination. Cached for 30 min."""
    all_events = []
    offset = 0

    while True:
        resp = requests.get(
            GAMMA_API_URL,
            params={
                "active": "true",
                "closed": "false",
                "limit": 100,
                "offset": offset,
            },
            timeout=30,
        )
        resp.raise_for_status()
        events = resp.json()

        if not events:
            break

        all_events.extend(events)

        if len(events) < 100:
            break

        offset += 100

    return all_events


def parse_market_fields(market):
    """Parse JSON-string fields (outcomePrices, outcomes) into real lists."""
    parsed = {}

    for field in ("outcomePrices", "outcomes"):
        raw = market.get(field)
        if isinstance(raw, str):
            try:
                parsed[field] = json.loads(raw)
            except (json.JSONDecodeError, TypeError):
                parsed[field] = []
        elif isinstance(raw, list):
            parsed[field] = raw
        else:
            parsed[field] = []

    return parsed


def find_matching_markets(keywords, events):
    """Find Polymarket markets whose titles/questions contain input keywords.

    Args:
        keywords: List of keyword strings to match.
        events: List of event dicts from load_all_events().

    Returns:
        List of match dicts sorted by overlap_ratio descending.
    """
    if not keywords:
        return []

    keyword_set = set(kw.lower() for kw in keywords if kw.strip())
    if not keyword_set:
        return []

    # For single-keyword queries, allow 1 hit; otherwise require 2 to filter noise
    min_hits = 1 if len(keyword_set) == 1 else 2

    matches = []

    for event in events:
        event_title = event.get("title", "")
        event_text = event_title.lower()

        for market in event.get("markets", []):
            question = market.get("question", "")
            full_text = f"{event_text} {question.lower()}"

            hits = sum(1 for kw in keyword_set if kw in full_text)
            if hits < min_hits:
                continue

            parsed = parse_market_fields(market)
            overlap_ratio = hits / len(keyword_set)

            matches.append({
                "event_title": event_title,
                "question": question,
                "outcomes": parsed["outcomes"],
                "outcome_prices": parsed["outcomePrices"],
                "volume": market.get("volume", 0),
                "volume_24hr": market.get("volume24hr", 0),
                "slug": market.get("slug", ""),
                "overlap_ratio": overlap_ratio,
                "hits": hits,
            })

    matches.sort(key=lambda x: (-x["overlap_ratio"], -x["hits"]))
    return matches


if __name__ == "__main__":
    # Standalone test: fetch events and print 5 sample titles + prices.
    # Bypasses st.cache_data since Streamlit isn't running.
    print("Fetching active Polymarket events...")

    all_events = []
    offset = 0

    while True:
        resp = requests.get(
            GAMMA_API_URL,
            params={
                "active": "true",
                "closed": "false",
                "limit": 100,
                "offset": offset,
            },
            timeout=30,
        )
        resp.raise_for_status()
        events = resp.json()

        if not events:
            break

        all_events.extend(events)

        if len(events) < 100:
            break

        offset += 100

    print(f"\nTotal events fetched: {len(all_events)}\n")

    count = 0
    for event in all_events:
        if count >= 5:
            break
        print(f"Event: {event.get('title', 'N/A')}")
        for market in event.get("markets", []):
            parsed = parse_market_fields(market)
            outcomes = parsed["outcomes"]
            prices = parsed["outcomePrices"]
            pairs = []
            for i in range(len(outcomes)):
                price = prices[i] if i < len(prices) else "?"
                pairs.append(f"{outcomes[i]}: {price}")
            print(f"  Market: {market.get('question', 'N/A')}")
            print(f"  Prices: {', '.join(pairs)}")
            print(f"  Volume: {market.get('volume', 'N/A')}")
        print()
        count += 1
