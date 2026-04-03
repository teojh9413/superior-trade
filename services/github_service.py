from __future__ import annotations

import base64
import re

import aiohttp

from core.config import AppConfig
from services.website_service import LookupSnippet, score_and_extract_excerpt


class GitHubService:
    def __init__(self, config: AppConfig) -> None:
        self.config = config
        self.api_base = "https://api.github.com"

    async def fetch_repo_snippets(self, query: str, limit: int = 2) -> list[LookupSnippet]:
        repos = await self._fetch_org_repositories(limit=4)
        if not repos:
            return []

        snippets: list[LookupSnippet] = []
        async with aiohttp.ClientSession(
            headers={"Accept": "application/vnd.github+json", "User-Agent": "superior-discord-bot"},
            timeout=aiohttp.ClientTimeout(total=self.config.llm_timeout_seconds),
        ) as session:
            for repo in repos:
                snippet = await self._fetch_readme_snippet(session=session, repo_full_name=repo, query=query)
                if snippet:
                    snippets.append(snippet)
                if len(snippets) >= limit:
                    break
        return snippets

    async def _fetch_org_repositories(self, limit: int) -> list[str]:
        url = f"{self.api_base}/search/repositories"
        params = {"q": f"org:{self.config.superior_github_org}", "per_page": str(limit), "sort": "updated"}
        async with aiohttp.ClientSession(
            headers={"Accept": "application/vnd.github+json", "User-Agent": "superior-discord-bot"},
            timeout=aiohttp.ClientTimeout(total=self.config.llm_timeout_seconds),
        ) as session:
            try:
                async with session.get(url, params=params) as response:
                    if response.status != 200:
                        return []
                    payload = await response.json()
            except aiohttp.ClientError:
                return []

        items = payload.get("items", [])
        return [item["full_name"] for item in items if item.get("full_name")]

    async def _fetch_readme_snippet(
        self, session: aiohttp.ClientSession, repo_full_name: str, query: str
    ) -> LookupSnippet | None:
        url = f"{self.api_base}/repos/{repo_full_name}/readme"
        try:
            async with session.get(url) as response:
                if response.status != 200:
                    return None
                payload = await response.json()
        except aiohttp.ClientError:
            return None

        content = payload.get("content")
        html_url = payload.get("html_url")
        if not content or not html_url:
            return None

        try:
            decoded = base64.b64decode(content).decode("utf-8", errors="ignore")
        except (ValueError, UnicodeDecodeError):
            return None

        excerpt = score_and_extract_excerpt(text=markdown_to_text(decoded), query=query)
        if not excerpt:
            return None

        return LookupSnippet(
            source_type="github",
            title=f"{repo_full_name} README",
            url=html_url,
            excerpt=excerpt,
        )


def markdown_to_text(markdown: str) -> str:
    text = re.sub(r"`{1,3}.*?`{1,3}", " ", markdown, flags=re.DOTALL)
    text = re.sub(r"\[([^\]]+)\]\([^)]+\)", r"\1", text)
    text = re.sub(r"[#>*_\-\|]", " ", text)
    text = re.sub(r"\s+", " ", text)
    return text.strip()
