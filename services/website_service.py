from __future__ import annotations

import html
import re
from dataclasses import dataclass

import aiohttp

from core.config import AppConfig

TAG_RE = re.compile(r"<[^>]+>")
SCRIPT_RE = re.compile(r"<script.*?</script>|<style.*?</style>", re.IGNORECASE | re.DOTALL)
SPACE_RE = re.compile(r"\s+")


@dataclass(frozen=True, slots=True)
class LookupSnippet:
    source_type: str
    title: str
    url: str
    excerpt: str


class WebsiteService:
    def __init__(self, config: AppConfig) -> None:
        self.config = config
        self.urls = [config.superior_website_url]

    async def fetch_site_snippets(self, query: str, limit: int = 2) -> list[LookupSnippet]:
        snippets: list[LookupSnippet] = []
        async with aiohttp.ClientSession(
            timeout=aiohttp.ClientTimeout(total=self.config.llm_timeout_seconds)
        ) as session:
            for url in self.urls:
                try:
                    async with session.get(url) as response:
                        if response.status != 200:
                            continue
                        body = await response.text()
                except aiohttp.ClientError:
                    continue

                text = html_to_text(body)
                excerpt = score_and_extract_excerpt(text=text, query=query)
                if excerpt:
                    snippets.append(
                        LookupSnippet(
                            source_type="website",
                            title="Superior.Trade official site",
                            url=url,
                            excerpt=excerpt,
                        )
                    )
                if len(snippets) >= limit:
                    break
        return snippets


def html_to_text(body: str) -> str:
    without_scripts = SCRIPT_RE.sub(" ", body)
    text = TAG_RE.sub(" ", without_scripts)
    return SPACE_RE.sub(" ", html.unescape(text)).strip()


def score_and_extract_excerpt(text: str, query: str, window: int = 360) -> str:
    lower_text = text.lower()
    tokens = [token.lower() for token in re.findall(r"[a-zA-Z0-9][a-zA-Z0-9_./:-]*", query)]
    if not lower_text or not tokens:
        return text[:window].strip()

    best_index = -1
    best_score = 0
    for token in tokens:
        idx = lower_text.find(token)
        if idx == -1:
            continue
        score = lower_text.count(token)
        if score > best_score:
            best_score = score
            best_index = idx
    if best_index == -1:
        return ""

    start = max(0, best_index - window // 3)
    end = min(len(text), start + window)
    return text[start:end].strip()
