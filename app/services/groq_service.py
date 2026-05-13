import json
import re
from typing import List
from groq import Groq
from app.core.config import settings
from app.core.logger import get_logger

logger = get_logger(__name__)


class GroqService:
    def __init__(self):
        if not settings.GROQ_API_KEY:
            raise RuntimeError(
                "GROQ_API_KEY is not configured. Set it in the environment before calling /run."
            )

        self.client = Groq(api_key=settings.GROQ_API_KEY)
        self.model = settings.GROQ_MODEL

    def _chat(self, system: str, user: str, temperature: float = 0.7) -> str:
        response = self.client.chat.completions.create(
            model=self.model,
            messages=[
                {"role": "system", "content": system},
                {"role": "user", "content": user},
            ],
            temperature=temperature,
            max_tokens=2048,
        )
        return response.choices[0].message.content.strip()

    def generate_thread(self, topic: str) -> List[str]:
        """Generate a Twitter thread (5-8 tweets) on the given topic."""
        system = (
            "You are an expert Twitter content creator. "
            "You write engaging, insightful threads that spark conversation. "
            "Each tweet must be under 280 characters. "
            "Do NOT number the tweets (no '1/' or '1.' prefixes). "
            "Use line breaks naturally. Do NOT use markdown. "
            "Output ONLY a JSON array of tweet strings, nothing else."
        )
        user = (
            f"Write a compelling Twitter thread of {settings.THREAD_MIN_TWEETS} to "
            f"{settings.THREAD_MAX_TWEETS} tweets about: {topic}\n\n"
            "Rules:\n"
            "- First tweet is a strong hook that grabs attention\n"
            "- Each tweet flows naturally to the next\n"
            "- Include a mix of insight, facts, and opinions\n"
            "- Last tweet is a call-to-action or thought-provoking question\n"
            "- Each tweet under 270 characters\n"
            "- Output: JSON array only, e.g. [\"tweet1\", \"tweet2\", ...]"
        )
        raw = self._chat(system, user, temperature=0.8)
        logger.debug(f"Thread raw response: {raw[:200]}")

        # Extract JSON array robustly
        match = re.search(r'\[.*\]', raw, re.DOTALL)
        if not match:
            raise ValueError(f"Could not parse thread JSON from Groq response: {raw[:300]}")
        tweets = json.loads(match.group())

        # Enforce character limits
        validated = []
        for tweet in tweets:
            if len(tweet) > 280:
                tweet = tweet[:277] + "..."
            validated.append(tweet.strip())

        logger.info(f"Generated thread with {len(validated)} tweets for topic: {topic}")
        return validated

    def generate_reply(self, tweet_text: str, topic: str) -> str:
        """Generate a relevant, thoughtful reply to a tweet."""
        system = (
            "You are a thoughtful Twitter user who writes concise, genuine replies. "
            "Never use sycophantic openers like 'Great post!' or 'Love this!'. "
            "Be direct, add value, ask a question or share a perspective. "
            "Output ONLY the reply text, under 250 characters, no quotes."
        )
        user = (
            f"Write a reply to this tweet:\n\"{tweet_text}\"\n\n"
            f"Context: You're interested in {topic}. "
            "Reply must be under 250 characters, genuine, and add value."
        )
        reply = self._chat(system, user, temperature=0.75)
        # Strip surrounding quotes if model added them
        reply = reply.strip('"\'')
        if len(reply) > 250:
            reply = reply[:247] + "..."
        logger.debug(f"Generated reply ({len(reply)} chars)")
        return reply

    def score_account_relevance(self, bio: str, topic: str) -> float:
        """Return 0.0–1.0 relevance score for a Twitter account bio vs topic."""
        system = (
            "You are a relevance scoring engine. "
            "Output ONLY a JSON object with a single key 'score' (float 0.0 to 1.0). "
            "Nothing else."
        )
        user = (
            f"Topic: {topic}\n"
            f"Twitter bio: {bio}\n\n"
            "How relevant is this account to the topic? "
            "Output: {\"score\": <float>}"
        )
        try:
            raw = self._chat(system, user, temperature=0.1)
            match = re.search(r'\{.*?\}', raw, re.DOTALL)
            if match:
                data = json.loads(match.group())
                return float(data.get("score", 0.0))
        except Exception as e:
            logger.warning(f"Score parsing failed: {e}")
        return 0.0

    def extract_search_queries(self, topic: str) -> List[str]:
        """
        Generate 3 plain keyword queries to find relevant Twitter accounts.
        Deliberately simple — no hashtags, no Twitter search operators,
        no filter: / lang: / min_faves: modifiers. Just keywords.
        """
        system = (
            "You generate short keyword search phrases to find Twitter accounts. "
            "Rules:\n"
            "- Output ONLY a JSON array of exactly 3 strings\n"
            "- Each string is 2-4 plain words, NO hashtags, NO special operators\n"
            "- Do NOT use: filter:, lang:, min_faves:, OR, AND, site:, #, @\n"
            "- Think: what words would appear in the bio of an expert on this topic?\n"
            "- Make each query distinct to find different types of accounts\n"
            "- Output format: [\"query1\", \"query2\", \"query3\"] — nothing else"
        )
        user = f"Topic: {topic}"

        raw = self._chat(system, user, temperature=0.3)
        match = re.search(r'\[.*?\]', raw, re.DOTALL)
        if match:
            try:
                queries = json.loads(match.group())
                # Strip any accidental operators that sneak through
                cleaned = []
                for q in queries[:3]:
                    q = re.sub(r'(filter:|lang:|min_faves:|site:|OR |AND )', '', q)
                    q = q.replace('#', '').replace('@', '').strip()
                    if q:
                        cleaned.append(q)
                if cleaned:
                    logger.info(f"Search queries: {cleaned}")
                    return cleaned
            except Exception:
                pass

        # Safe fallback: derive keywords directly from topic words
        words = [w for w in topic.split() if len(w) > 3][:4]
        fallback = [
            topic[:40],
            " ".join(words[:2]) if len(words) >= 2 else topic[:20],
            " ".join(words[-2:]) if len(words) >= 2 else topic[:20],
        ]
        logger.info(f"Using fallback search queries: {fallback}")
        return fallback