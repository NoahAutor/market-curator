# Market Curator

A market gap analysis tool for Polymarket. Describe a prediction market idea in plain English, and Market Curator checks whether it already exists on Polymarket, measures how much people are talking about it on Reddit, and tells you whether it's worth launching.

Built by **Noah Autor**.

---

## What It Does

1. **Describe a market idea** — *"Taylor Swift Travis Kelce married"*, *"Bitcoin 200k 2026"*, whatever
2. **Polymarket check** — pulls all active events from the Gamma API and searches for existing coverage
3. **Reddit check** — hits Reddit across multiple subreddits and sort orders to gauge real discussion volume
4. **Verdict** — combines both signals into a launch recommendation:

| Verdict | What It Means |
|---------|---------------|
| **STRONG LAUNCH** | Lots of Reddit discussion, nothing on Polymarket — clear gap |
| **WORTH CONSIDERING** | Decent interest, no existing market |
| **ADJACENT OPPORTUNITY** | Related market exists, but there's a niche angle |
| **ALREADY COVERED** | Market already lives on Polymarket |
| **LOW PRIORITY** | Not enough demand to justify launching |

The basic question this answers: *"Is this topic hot enough to launch? Does a market already exist? Is there an angle we're missing?"*

## How It Works

### Polymarket (Gamma API)

All active events are fetched from the [Gamma API](https://gamma-api.polymarket.com) (public, no auth), paginated in batches of 100, and cached for 30 minutes. Keyword matching runs client-side against the cached data, scoring each market by keyword overlap to separate exact matches from loosely related coverage.

### Reddit (.json endpoints)

Reddit's public `.json` endpoints (no API key) are queried with 2–3 search variants per idea across relevance, top, and new sort orders. A relevance filter strips clickbait and aggregator noise by segmenting long titles and only checking topic words against the part that actually mentions the entities you care about.

Results feed into a **heat score (0–100)**:

| Component | Max Pts | Measures |
|-----------|:-------:|----------|
| Post count | 25 | How much discussion exists |
| Upvotes | 25 | How much people care |
| Comments | 25 | How deep the engagement goes |
| Subreddit spread | 15 | Whether it's crossed into multiple communities |
| Recency (7d) | 10 | Whether it's trending right now |

### Verdict Logic

Coverage level (none / similar / exact) is crossed against heat (high / medium / low) to produce one of the five verdicts above.

## Quick Start

```bash
pip install -r requirements.txt
streamlit run app.py
```

Opens at `http://localhost:8501`. No API keys, no database, no setup.

### Dependencies

```
streamlit
requests
```

That's it. No NLP libraries, no database, no auth.

## Project Structure

```
app.py                  Streamlit UI — search, verdict display, session history
analyzer.py             Keyword extraction, synonym expansion, heat scoring, verdict logic
polymarket_checker.py   Gamma API client + local keyword search over cached events
reddit_checker.py       Reddit .json client with rate limiting and 429 backoff
requirements.txt        streamlit, requests
.streamlit/config.toml  Dark theme config
```

## Design Decisions

- **No NLP libraries** — keywords are extracted with regex and a stopword list. Synonyms come from a hand-tuned lookup table. Keeps things lightweight and easy to reason about.
- **No database** — session history lives in `st.session_state`. This is a triage tool, not a data warehouse.
- **No API keys** — both Polymarket's Gamma API and Reddit's `.json` endpoints are public. Zero config to get running.
- **Synchronous requests** — Reddit caps you at ~10 req/min unauthenticated. Each lookup takes 20–30 seconds through the full pipeline, which is fine for interactive use.

---

*Noah Autor — [GitHub](https://github.com/NoahAutor)*
