from pathlib import Path

from services.knowledge_service import KnowledgeService, split_markdown_sections


def test_split_markdown_sections_builds_heading_paths() -> None:
    text = "# Root\nIntro\n## Child\nDetails\n### Leaf\nMore details"

    sections = split_markdown_sections("FAQ.md", text)

    heading_paths = [section.heading_path for section in sections]
    assert ("Root",) in heading_paths
    assert ("Root", "Child") in heading_paths
    assert ("Root", "Child", "Leaf") in heading_paths


def test_search_prioritizes_relevant_skill_sections(tmp_path: Path) -> None:
    knowledge_dir = tmp_path / "knowledge"
    knowledge_dir.mkdir()
    (knowledge_dir / "SKILL.md").write_text(
        "# Wallets\nUsers do not need their own Hyperliquid wallet.\n",
        encoding="utf-8",
    )
    (knowledge_dir / "FAQ.md").write_text(
        "# General\nSuperior.Trade helps deploy strategies.\n",
        encoding="utf-8",
    )

    service = KnowledgeService(knowledge_dir)
    service.load()
    results = service.search("Do users need their own Hyperliquid wallet?", top_k=2)

    assert results
    assert results[0].source_name == "SKILL.md"
    assert "Wallets" in results[0].heading_path_display


def test_build_context_block_respects_max_chars(tmp_path: Path) -> None:
    knowledge_dir = tmp_path / "knowledge"
    knowledge_dir.mkdir()
    long_body = "wallet " * 300
    (knowledge_dir / "SKILL.md").write_text(f"# Wallets\n{long_body}\n", encoding="utf-8")

    service = KnowledgeService(knowledge_dir)
    service.load()
    context = service.build_context_block("wallet", max_chars=180)

    assert context.startswith("[SOURCE: SKILL.md")
    assert len(context) <= 260


def test_list_sources_returns_sorted_unique_names(tmp_path: Path) -> None:
    knowledge_dir = tmp_path / "knowledge"
    knowledge_dir.mkdir()
    (knowledge_dir / "B.md").write_text("# B\nBody\n", encoding="utf-8")
    (knowledge_dir / "A.md").write_text("# A\nBody\n", encoding="utf-8")

    service = KnowledgeService(knowledge_dir)
    service.load()

    assert service.list_sources() == ["A.md", "B.md"]
