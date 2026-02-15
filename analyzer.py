"""
Keyword extraction, heat score (0-100), and verdict logic.

All text processing uses simple regex and built-in Python only —
no NLP libraries (no spaCy, no transformers, no nltk).
"""

import re
import time


# Common English stopwords to strip from user input
STOPWORDS = {
    "a", "an", "the", "and", "or", "but", "in", "on", "at", "to", "for",
    "of", "with", "by", "from", "is", "it", "its", "are", "was", "were",
    "be", "been", "being", "have", "has", "had", "do", "does", "did",
    "will", "would", "shall", "should", "may", "might", "can", "could",
    "not", "no", "nor", "so", "if", "then", "than", "that", "this",
    "these", "those", "what", "which", "who", "whom", "when", "where",
    "why", "how", "all", "each", "every", "both", "few", "more", "most",
    "some", "any", "about", "above", "after", "before", "between",
    "into", "through", "during", "again", "further",
    "once", "here", "there", "just", "also", "very", "too", "much",
    "many", "such", "own", "same", "other", "up", "out", "off",
}

# Topic synonym clusters — words that are INTERCHANGEABLE for relevance.
#
# Design rules:
# 1. Only group words that mean roughly the same thing. "married" and
#    "divorce" are same-domain but OPPOSITE intent — separate clusters.
# 2. Don't expand generic/common words. "over", "under", "years", "long"
#    are too common — they match nearly any post and destroy filtering.
#    Only expand words that are specific enough to be meaningful.
# 3. Synonyms should be words you'd actually substitute in a search.
#    "married" → "wedding" makes sense. "over" → "more" does not.
TOPIC_SYNONYMS = {
    "married": ["wedding", "marriage", "engaged", "engagement", "propose",
                 "proposal", "marry"],
    "divorce": ["breakup", "separated", "separation", "custody",
                 "annulment"],
    "win": ["winner", "champion", "victory", "won", "winning"],
    "election": ["vote", "voting", "ballot", "polls", "elected"],
    "president": ["presidential", "presidency", "potus"],
    "ban": ["banned", "prohibit", "restrict", "restriction"],
    "resign": ["resignation", "step down", "quit", "retired", "retirement"],
    "die": ["death", "dead", "killed", "passed away", "obituary"],
    "war": ["conflict", "invasion", "military", "troops"],
    "trade": ["traded", "trading", "transfer"],
    "fire": ["fired", "terminated", "sacked", "dismissed"],
    "hire": ["hired", "hiring", "appointment", "appointed"],
    "ipo": ["listing", "stock", "shares", "offering"],
    "regulation": ["regulate", "regulated", "legislation",
                    "policy"],
}

# Words that are too generic to expand. They appear in synonym clusters
# of other words but should NOT trigger expansion on their own.
# "over/under" only means something in a betting context, not as standalone.
# "years/long/more/less" match nearly everything and destroy filtering.
_GENERIC_WORDS = {
    "over", "under", "years", "long", "more", "less", "above", "below",
    "price", "cost", "deal", "bill", "fire", "split", "wed", "won",
    "public", "law", "rules", "block", "attack", "quit",
}


def _expand_topic_words(topic_keywords):
    """Expand topic keywords with synonyms for richer search + filtering.

    Only expands words that are specific enough to be meaningful.
    Generic words like "over", "under", "years" are kept as-is because
    expanding them produces common words ("more", "long", "less") that
    match nearly any post and destroy filtering precision.

    Returns the original keywords plus any synonym matches.
    """
    expanded = set(topic_keywords)
    for kw in topic_keywords:
        # Don't expand generic/common words — they'd match everything
        if kw in _GENERIC_WORDS:
            continue
        if kw in TOPIC_SYNONYMS:
            expanded.update(TOPIC_SYNONYMS[kw])
        # Also check if the keyword is itself a synonym of something
        for root, syns in TOPIC_SYNONYMS.items():
            if kw in syns:
                expanded.add(root)
                expanded.update(syns)
    return expanded


def _word_in_text(word, text):
    """Check if `word` appears in `text` as a whole word (word-boundary match).

    Uses regex \\b word boundaries to prevent 'wed' matching 'wednesday',
    'war' matching 'award', 'win' matching 'window', etc.

    Both `word` and `text` should already be lowercase.
    """
    # Multi-word phrases (e.g. "step down", "how long") — use simple substring
    # since the spaces already act as natural boundaries
    if " " in word:
        return word in text
    return re.search(r'\b' + re.escape(word) + r'\b', text) is not None


def _count_word_hits(words, text):
    """Count how many words from `words` appear as whole words in `text`."""
    return sum(1 for w in words if _word_in_text(w, text))


def extract_keywords(text):
    """Extract meaningful keywords from natural language input.

    Strips stopwords, punctuation, and short tokens. Returns lowercase
    keywords preserving input order.

    Args:
        text: Raw user input string.

    Returns:
        List of keyword strings (lowercase, deduplicated, order-preserved).
    """
    # Keep only alphanumeric chars and spaces
    cleaned = re.sub(r"[^a-zA-Z0-9\s]", " ", text)
    tokens = cleaned.lower().split()

    seen = set()
    keywords = []
    for token in tokens:
        if len(token) < 2:
            continue
        if token in STOPWORDS:
            continue
        if token not in seen:
            seen.add(token)
            keywords.append(token)

    return keywords


def _detect_name_pairs(text):
    """Detect likely multi-word proper names (consecutive capitalized words).

    e.g. "Taylor Swift Travis Kelce marriage" → ["Taylor Swift", "Travis Kelce"]

    Splits long runs of capitalized words into 2-word pairs (first + last name),
    since most proper names are two words. Filters out sentence-starter words.
    """
    # Words that are often capitalized at sentence start but aren't names
    false_starts = {
        "will", "can", "could", "should", "would", "may", "might", "shall",
        "do", "does", "did", "is", "are", "was", "were", "has", "have",
        "had", "the", "what", "which", "who", "when", "where", "why", "how",
        "if", "my", "our", "his", "her", "its", "not", "and", "but", "for",
    }

    # Find runs of capitalized words in the original text
    raw_runs = re.findall(r'\b([A-Z][a-z]+(?:\s+[A-Z][a-z]+)+)\b', text)

    cleaned = []
    for run in raw_runs:
        words = run.split()
        # Strip leading false-start words
        while words and words[0].lower() in false_starts:
            words = words[1:]

        # Split into 2-word name pairs
        # "Taylor Swift Travis Kelce" → ["Taylor Swift", "Travis Kelce"]
        # "Taylor Swift" → ["Taylor Swift"]
        # "Kim Kardashian" → ["Kim Kardashian"]
        i = 0
        while i < len(words) - 1:
            cleaned.append(f"{words[i]} {words[i + 1]}")
            i += 2
        # If odd word left over (e.g. "Taylor Swift Kim"), it's dropped
        # since a single word isn't a name pair

    return cleaned


def generate_search_queries(text):
    """Generate 2-3 Reddit search query variants from user input.

    Uses synonym expansion to create differentiated queries that capture
    the specific topic angle. e.g. "married" also searches for "wedding",
    "engagement", etc.

    Args:
        text: Raw user input string.

    Returns:
        List of 2-3 query strings for Reddit search.
    """
    keywords = extract_keywords(text)

    if not keywords:
        return [text.strip()]

    # Detect multi-word names from original (pre-lowered) text
    name_pairs = _detect_name_pairs(text)

    # If we found proper name pairs, build smarter queries
    if name_pairs:
        # Quote each name as a phrase
        quoted_names = [f'"{name}"' for name in name_pairs]
        quoted_str = " ".join(quoted_names)

        # Identify topic keywords (keywords not part of any name)
        name_words = set()
        for name in name_pairs:
            for word in name.lower().split():
                name_words.add(word)
        topic_keywords = [kw for kw in keywords if kw not in name_words]

        # Strip generic/betting-mechanic words from Reddit queries.
        # Words like "over", "under", "years" are market-structure terms
        # that pollute Reddit search results. The substantive topic words
        # (e.g. "married") are what matter for finding discussion.
        substantive_topics = [kw for kw in topic_keywords
                              if kw not in _GENERIC_WORDS]

        queries = []

        # Query 1: quoted names + substantive topic keywords only
        if substantive_topics:
            queries.append(f"{quoted_str} {' '.join(substantive_topics)}")
        else:
            queries.append(quoted_str)

        # Query 2: quoted names + synonym-expanded substantive topic words
        if substantive_topics:
            alt_words = []
            for kw in substantive_topics:
                syns = TOPIC_SYNONYMS.get(kw, [])
                if syns:
                    alt_words.append(syns[0])
                else:
                    alt_words.append(kw)
            alt_query = f"{quoted_str} {' '.join(alt_words)}"
            if alt_query not in queries:
                queries.append(alt_query)

        # Query 3: just the quoted names (broadest)
        if quoted_str not in queries:
            queries.append(quoted_str)

        # Guarantee at least 2
        if len(queries) == 1:
            queries.append(" ".join(keywords))

        return queries[:3]

    # Fallback: no proper names detected, use simple keyword approach
    queries = []
    full_query = " ".join(keywords)
    queries.append(full_query)

    # Synonym-expanded variant (skip generic words)
    expanded_words = []
    for kw in keywords:
        if kw in _GENERIC_WORDS:
            expanded_words.append(kw)
        else:
            syns = TOPIC_SYNONYMS.get(kw, [])
            if syns:
                expanded_words.append(syns[0])
            else:
                expanded_words.append(kw)
    alt_query = " ".join(expanded_words)
    if alt_query != full_query:
        queries.append(alt_query)
    elif len(keywords) <= 4:
        queries.append(f'"{full_query}"')

    # Guarantee at least 2
    if len(queries) == 1:
        queries.append(f'"{full_query}"')

    return queries[:3]


def _extract_relevant_segment(title_lower, name_pairs_lower):
    """Extract the portion of a title that's actually about the named entities.

    Clickbait/aggregator posts jam multiple unrelated stories into one title:
      "Kody Brown BANKRUPT!! Blake's Wedding! Taylor Swift's Texts!
       Travis Kelce's Advice! And More!"

    We only want to check topic words against the part that mentions our
    names, not against "Blake's Wedding" or "3 Years" which are about
    other people entirely.

    For SHORT titles (≤100 chars), skip segmentation entirely — they're
    almost always about one topic. Segmentation only kicks in for long
    titles that are likely aggregating multiple stories.
    """
    if not name_pairs_lower:
        return title_lower

    # Short titles are almost always about one topic — don't segment
    if len(title_lower) <= 100:
        return title_lower

    # Split on sentence-ending punctuation that separates distinct items:
    # single !, single ?, |, —, –, ;, and multi-punctuation (!!, ??, !?!?)
    # Also split on aggregator phrases ("plus,", "and more", "also:")
    # We do NOT split on . alone (too common in abbreviations / normal prose)
    segments = re.split(
        r'[!?;]+|[|—–]|\bplus[,:]?\s|\band more\b|\balso:\s',
        title_lower,
    )

    relevant_parts = []
    for seg in segments:
        seg = seg.strip()
        if not seg:
            continue
        if any(name in seg for name in name_pairs_lower):
            relevant_parts.append(seg)

    if relevant_parts:
        return " ".join(relevant_parts)

    # Fallback: if no segments matched (names split across segments),
    # use the full title
    return title_lower


def filter_relevant_posts(posts, text):
    """Filter Reddit posts to only those relevant to the query.

    Uses synonym expansion to understand topic intent. A post about
    "wedding" is relevant to a query about "married". A post about
    "Super Bowl" is NOT relevant to "married" even if it mentions
    the same person.

    For clickbait/aggregator titles that jam multiple stories together,
    topic words are only checked against the segment of the title that
    actually mentions the named entities.

    Relevance rules:
    - If multiple name pairs: post must have both names, OR one name +
      a topic/synonym match in the title.
    - If one name pair: must contain the name pair.
    - If no name pairs: must contain at least 2 keywords or synonyms.

    Args:
        posts: List of post dicts with 'title' key.
        text: Original user input (for name detection).

    Returns:
        Filtered list of post dicts.
    """
    if not posts:
        return posts

    name_pairs = _detect_name_pairs(text)
    keywords = extract_keywords(text)

    # Lowercase name pairs for matching
    name_pairs_lower = [name.lower() for name in name_pairs]

    # Topic keywords = keywords not part of any detected name
    name_words = set()
    for name in name_pairs:
        for word in name.lower().split():
            name_words.add(word)
    topic_keywords = [kw for kw in keywords if kw not in name_words]

    # Expand topic keywords with synonyms for smarter matching
    expanded_topics = _expand_topic_words(topic_keywords)

    # Determine how strict the topic matching should be.
    # More topic keywords = more specific query = stricter filtering.
    #
    # BUT: generic/betting-mechanic words ("over", "under", "years") don't
    # count toward specificity — they inflate the keyword count without
    # adding meaningful topic signal. Only count substantive topic words.
    #
    # "Taylor Swift Travis Kelce married" → 1 substantive → require 1 hit
    # "Taylor Swift Travis Kelce married over under years" → still 1
    #   substantive ("married") → require 1 hit, not 2
    # "Taylor Swift Travis Kelce divorce settlement custody" → 3 substantive
    #   → require 2 hits for stricter angle matching
    substantive_topic_count = sum(
        1 for kw in topic_keywords if kw not in _GENERIC_WORDS
    )
    if substantive_topic_count >= 3:
        min_topic_hits = 2
    else:
        min_topic_hits = 1

    multiple_names = len(name_pairs_lower) >= 2

    filtered = []
    for post in posts:
        title_lower = post.get("title", "").lower()

        # Count how many name pairs appear in the FULL title
        name_hits = sum(
            1 for name in name_pairs_lower if name in title_lower
        )

        # For topic matching, only look at segments of the title that
        # actually mention our names. This prevents clickbait aggregator
        # titles from matching topic words about unrelated people.
        # e.g. "Blake's Wedding! Taylor Swift's Texts!" — "wedding" is
        # about Blake, not about Taylor Swift.
        relevant_text = _extract_relevant_segment(
            title_lower, name_pairs_lower
        )
        topic_hits = _count_word_hits(expanded_topics, relevant_text)

        if multiple_names:
            if name_hits >= 2 and topic_hits >= min_topic_hits:
                filtered.append(post)
            elif name_hits >= 2 and not topic_keywords:
                filtered.append(post)
            elif name_hits == 1 and topic_hits >= min_topic_hits:
                filtered.append(post)
        elif name_pairs_lower:
            if name_hits >= 1 and (topic_hits >= min_topic_hits
                                   or not topic_keywords):
                filtered.append(post)
        else:
            kw_hits = _count_word_hits(keywords, title_lower)
            if kw_hits >= 2 or (kw_hits >= 1 and topic_hits >= 1):
                filtered.append(post)

    return filtered


def compute_heat_score(posts):
    """Compute a 0-100 heat score from Reddit search results.

    Scoring breakdown (from spec):
        - Post count     (0-25 pts): min(count / 40, 1) * 25
        - Total upvotes  (0-25 pts): min(total_score / 5000, 1) * 25
        - Comment volume  (0-25 pts): min(total_comments / 2000, 1) * 25
        - Subreddit spread(0-15 pts): min(num_subreddits / 8, 1) * 15
        - Recency         (0-10 pts): fraction of posts from last 7 days * 10

    Args:
        posts: List of post dicts with keys: score, num_comments,
               subreddit, created_utc.

    Returns:
        Dict with: score (int 0-100), label (str), breakdown (dict),
        top_posts (list of top 5 by score).
    """
    if not posts:
        return {
            "score": 0,
            "label": "No Discussion",
            "breakdown": {
                "post_count": 0,
                "total_score": 0,
                "total_comments": 0,
                "subreddit_count": 0,
                "recency_pct": 0.0,
                "count_pts": 0.0,
                "score_pts": 0.0,
                "comment_pts": 0.0,
                "spread_pts": 0.0,
                "recency_pts": 0.0,
            },
            "top_posts": [],
        }

    post_count = len(posts)
    total_score = sum(p.get("score", 0) for p in posts)
    total_comments = sum(p.get("num_comments", 0) for p in posts)
    subreddits = set(p.get("subreddit", "") for p in posts)
    subreddit_count = len(subreddits)

    # Recency: fraction of posts from the last 7 days
    now = time.time()
    seven_days_ago = now - (7 * 24 * 60 * 60)
    recent_count = sum(
        1 for p in posts if p.get("created_utc", 0) > seven_days_ago
    )
    recency_pct = recent_count / post_count if post_count > 0 else 0.0

    # Score components
    count_pts = min(post_count / 40, 1.0) * 25
    score_pts = min(total_score / 5000, 1.0) * 25
    comment_pts = min(total_comments / 2000, 1.0) * 25
    spread_pts = min(subreddit_count / 8, 1.0) * 15
    recency_pts = recency_pct * 10

    heat = count_pts + score_pts + comment_pts + spread_pts + recency_pts
    heat = round(heat)

    # Clamp to 0-100
    heat = max(0, min(100, heat))

    # Label
    if heat >= 70:
        label = "Very Hot"
    elif heat >= 50:
        label = "Hot"
    elif heat >= 30:
        label = "Moderate"
    elif heat > 0:
        label = "Low"
    else:
        label = "No Discussion"

    # Top posts by score
    sorted_posts = sorted(posts, key=lambda p: p.get("score", 0), reverse=True)
    top_posts = sorted_posts[:5]

    return {
        "score": heat,
        "label": label,
        "breakdown": {
            "post_count": post_count,
            "total_score": total_score,
            "total_comments": total_comments,
            "subreddit_count": subreddit_count,
            "recency_pct": round(recency_pct, 3),
            "count_pts": round(count_pts, 2),
            "score_pts": round(score_pts, 2),
            "comment_pts": round(comment_pts, 2),
            "spread_pts": round(spread_pts, 2),
            "recency_pts": round(recency_pts, 2),
        },
        "top_posts": top_posts,
    }


def generate_verdict(polymarket_matches, heat_result):
    """Generate a launch verdict from Polymarket matches + Reddit heat.

    Verdict matrix (from spec):
        | Polymarket       | Reddit Heat | Verdict                      |
        |------------------|-------------|------------------------------|
        | No match         | High (70+)  | STRONG LAUNCH                |
        | No match         | Med (30-70) | WORTH CONSIDERING            |
        | No match         | Low (<30)   | LOW PRIORITY                 |
        | Similar exists   | High        | ADJACENT OPPORTUNITY         |
        | Exact match      | Any         | ALREADY COVERED              |

    Args:
        polymarket_matches: List of match dicts from find_matching_markets().
            Each has 'overlap_ratio' (0-1) and 'hits' fields.
        heat_result: Dict from compute_heat_score() with 'score' key.

    Returns:
        Dict with: verdict (str), emoji (str), description (str),
        match_type (str).
    """
    heat_score = heat_result.get("score", 0)

    # Determine Polymarket coverage level
    # "exact" requires near-perfect overlap (95%+) because keyword matching
    # can't distinguish different markets about the same people/topics.
    # e.g. "Will Swift & Kelce marry?" vs "Swift Kelce years married over/under"
    # share most keywords but are completely different market questions.
    if polymarket_matches:
        best_match = polymarket_matches[0]
        overlap = best_match.get("overlap_ratio", 0)
        hits = best_match.get("hits", 0)

        if overlap >= 0.95 and hits >= 3:
            match_type = "exact"
        elif overlap >= 0.4 and hits >= 2:
            match_type = "similar"
        else:
            match_type = "none"
    else:
        match_type = "none"

    # Apply verdict matrix
    if match_type == "exact":
        return {
            "verdict": "ALREADY COVERED",
            "emoji": "\U0001f534",  # red circle
            "description": "Market exists — this topic is already covered on Polymarket.",
            "match_type": match_type,
        }

    if match_type == "similar" and heat_score >= 30:
        return {
            "verdict": "ADJACENT OPPORTUNITY",
            "emoji": "\U0001f535",  # blue circle
            "description": "A related market exists, but there may be a niche angle available.",
            "match_type": match_type,
        }

    if match_type == "similar" and heat_score < 30:
        return {
            "verdict": "LOW PRIORITY",
            "emoji": "\u26aa",  # white circle
            "description": "Similar market exists and Reddit demand is low.",
            "match_type": match_type,
        }

    # No match — verdict depends on heat
    if heat_score >= 70:
        return {
            "verdict": "STRONG LAUNCH",
            "emoji": "\U0001f7e2",  # green circle
            "description": "High demand on Reddit with no Polymarket coverage — strong launch candidate.",
            "match_type": match_type,
        }

    if heat_score >= 30:
        return {
            "verdict": "WORTH CONSIDERING",
            "emoji": "\U0001f7e1",  # yellow circle
            "description": "Moderate Reddit interest with no existing coverage — worth exploring.",
            "match_type": match_type,
        }

    return {
        "verdict": "LOW PRIORITY",
        "emoji": "\u26aa",  # white circle
        "description": "Insufficient Reddit demand to justify a new market.",
        "match_type": match_type,
    }


# ---------------------------------------------------------------------------
# Standalone test
# ---------------------------------------------------------------------------
if __name__ == "__main__":
    print("=" * 60)
    print("ANALYZER TESTS")
    print("=" * 60)

    # --- Test 1: extract_keywords ---
    print("\n--- extract_keywords ---")
    test_input = "Will Taylor Swift and Travis Kelce get married in 2026?"
    kw = extract_keywords(test_input)
    print(f"Input:    {test_input}")
    print(f"Keywords: {kw}")
    assert "taylor" in kw
    assert "swift" in kw
    assert "travis" in kw
    assert "kelce" in kw
    assert "married" in kw
    assert "2026" in kw
    assert "and" not in kw
    assert "in" not in kw
    assert "will" not in kw
    print("PASS\n")

    # --- Test 2: generate_search_queries ---
    print("--- generate_search_queries ---")
    queries = generate_search_queries(test_input)
    print(f"Input:   {test_input}")
    print(f"Queries: {queries}")
    assert len(queries) >= 2
    assert len(queries) <= 3
    # Should detect "Taylor Swift" and "Travis Kelce" as name pairs
    assert any('"Taylor Swift"' in q for q in queries), \
        "Should quote 'Taylor Swift' as a phrase"
    assert any('"Travis Kelce"' in q for q in queries), \
        "Should quote 'Travis Kelce' as a phrase"
    print("PASS\n")

    # Test with no proper names
    print("--- generate_search_queries (no names) ---")
    queries2 = generate_search_queries("bitcoin price 200k prediction")
    print(f"Input:   bitcoin price 200k prediction")
    print(f"Queries: {queries2}")
    assert len(queries2) >= 2
    assert len(queries2) <= 3
    print("PASS\n")

    # --- Test 3: compute_heat_score with empty data ---
    print("--- compute_heat_score (empty) ---")
    result = compute_heat_score([])
    print(f"Score: {result['score']}, Label: {result['label']}")
    assert result["score"] == 0
    assert result["label"] == "No Discussion"
    print("PASS\n")

    # --- Test 4: compute_heat_score with mock data ---
    print("--- compute_heat_score (mock data) ---")
    now = time.time()
    mock_posts = [
        # 20 posts across 5 subreddits, mix of recent and older
        {"score": 500, "num_comments": 150, "subreddit": "nfl",
         "created_utc": now - 86400},  # 1 day ago
        {"score": 300, "num_comments": 80, "subreddit": "taylorswift",
         "created_utc": now - 172800},  # 2 days ago
        {"score": 1200, "num_comments": 400, "subreddit": "entertainment",
         "created_utc": now - 259200},  # 3 days ago
        {"score": 200, "num_comments": 50, "subreddit": "sports",
         "created_utc": now - 345600},  # 4 days ago
        {"score": 150, "num_comments": 30, "subreddit": "popculture",
         "created_utc": now - 432000},  # 5 days ago
        {"score": 800, "num_comments": 200, "subreddit": "nfl",
         "created_utc": now - 518400},  # 6 days ago
        {"score": 100, "num_comments": 20, "subreddit": "taylorswift",
         "created_utc": now - 604800},  # 7 days ago (boundary)
        {"score": 50, "num_comments": 10, "subreddit": "entertainment",
         "created_utc": now - 864000},  # 10 days ago
        {"score": 400, "num_comments": 90, "subreddit": "sports",
         "created_utc": now - 43200},   # 12 hours ago
        {"score": 250, "num_comments": 60, "subreddit": "popculture",
         "created_utc": now - 7200},    # 2 hours ago
    ]

    result = compute_heat_score(mock_posts)
    bd = result["breakdown"]

    print(f"Posts: {bd['post_count']}")
    print(f"Total score: {bd['total_score']}")
    print(f"Total comments: {bd['total_comments']}")
    print(f"Subreddits: {bd['subreddit_count']}")
    print(f"Recency %: {bd['recency_pct']}")
    print()
    print(f"Count pts:   {bd['count_pts']:.2f} / 25")
    print(f"Score pts:   {bd['score_pts']:.2f} / 25")
    print(f"Comment pts: {bd['comment_pts']:.2f} / 25")
    print(f"Spread pts:  {bd['spread_pts']:.2f} / 15")
    print(f"Recency pts: {bd['recency_pts']:.2f} / 10")
    print(f"TOTAL:       {result['score']} / 100")
    print(f"Label:       {result['label']}")

    # Verify math manually:
    # 10 posts: min(10/40, 1) * 25 = 0.25 * 25 = 6.25
    expected_count = min(10 / 40, 1.0) * 25
    assert bd["count_pts"] == round(expected_count, 2), \
        f"count_pts: expected {expected_count}, got {bd['count_pts']}"

    # total_score = 3950: min(3950/5000, 1) * 25 = 0.79 * 25 = 19.75
    expected_score = min(3950 / 5000, 1.0) * 25
    assert bd["score_pts"] == round(expected_score, 2), \
        f"score_pts: expected {expected_score}, got {bd['score_pts']}"

    # total_comments = 1090: min(1090/2000, 1) * 25 = 0.545 * 25 = 13.625
    expected_comment = min(1090 / 2000, 1.0) * 25
    assert bd["comment_pts"] == round(expected_comment, 2), \
        f"comment_pts: expected {expected_comment}, got {bd['comment_pts']}"

    # 5 subreddits: min(5/8, 1) * 15 = 0.625 * 15 = 9.375
    expected_spread = min(5 / 8, 1.0) * 15
    assert bd["spread_pts"] == round(expected_spread, 2), \
        f"spread_pts: expected {expected_spread}, got {bd['spread_pts']}"

    assert result["score"] > 0
    print("PASS\n")

    # --- Test 5: generate_verdict matrix ---
    print("--- generate_verdict ---")

    # No match + high heat
    v = generate_verdict([], {"score": 85})
    print(f"{v['emoji']} {v['verdict']}: {v['description']}")
    assert v["verdict"] == "STRONG LAUNCH"

    # No match + medium heat
    v = generate_verdict([], {"score": 50})
    print(f"{v['emoji']} {v['verdict']}: {v['description']}")
    assert v["verdict"] == "WORTH CONSIDERING"

    # No match + low heat
    v = generate_verdict([], {"score": 15})
    print(f"{v['emoji']} {v['verdict']}: {v['description']}")
    assert v["verdict"] == "LOW PRIORITY"

    # Exact match (95%+ overlap required)
    v = generate_verdict(
        [{"overlap_ratio": 1.0, "hits": 4}],
        {"score": 85},
    )
    print(f"{v['emoji']} {v['verdict']}: {v['description']}")
    assert v["verdict"] == "ALREADY COVERED"

    # High overlap but below exact threshold → similar, not exact
    v = generate_verdict(
        [{"overlap_ratio": 0.83, "hits": 5}],
        {"score": 85},
    )
    print(f"{v['emoji']} {v['verdict']}: {v['description']}")
    assert v["verdict"] == "ADJACENT OPPORTUNITY"

    # Similar match + high heat
    v = generate_verdict(
        [{"overlap_ratio": 0.5, "hits": 2}],
        {"score": 75},
    )
    print(f"{v['emoji']} {v['verdict']}: {v['description']}")
    assert v["verdict"] == "ADJACENT OPPORTUNITY"

    # Similar match + low heat
    v = generate_verdict(
        [{"overlap_ratio": 0.5, "hits": 2}],
        {"score": 10},
    )
    print(f"{v['emoji']} {v['verdict']}: {v['description']}")
    assert v["verdict"] == "LOW PRIORITY"

    print("\nPASS — All verdicts correct")
    print("\n" + "=" * 60)
    print("ALL TESTS PASSED")
    print("=" * 60)
