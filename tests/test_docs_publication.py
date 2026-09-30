"""The public docs site must describe the current RAG_new artefact."""

from pathlib import Path


ROOT = Path(__file__).resolve().parent.parent
SITE = ROOT / "docs-site"
CONTENT = SITE / "src" / "content" / "docs"


def _frontmatter(path: Path) -> str:
    return path.read_text(encoding="utf-8").split("---", 2)[1]


def test_public_docs_target_current_repository() -> None:
    config = (SITE / "astro.config.mjs").read_text(encoding="utf-8")
    assert "base: '/RAG_new'" in config
    assert "https://github.com/brownjuly2003-code/RAG_new" in config
    assert "RAG_Support_Assistant" not in config

    for path in (CONTENT / "index.mdx", CONTENT / "ru" / "index.mdx"):
        page = path.read_text(encoding="utf-8")
        assert "RAG assistant" in page
        assert "phase-e-demo.mp4" in page
        assert "RAG_Support_Assistant" not in page
        assert "E20" not in page

    fallback = (CONTENT / "404.md").read_text(encoding="utf-8")
    assert "RAG_Support_Assistant" not in fallback


def test_inherited_demo_pages_are_not_published_as_current_guides() -> None:
    inherited = (
        "examples.mdx",
        "reproduce-e20.mdx",
        "architecture/index.mdx",
        "evaluation/index.mdx",
        "ru/examples.mdx",
        "ru/reproduce-e20.mdx",
        "ru/architecture/index.mdx",
        "ru/evaluation/index.mdx",
        "ru/guides/quickstart.md",
    )
    for relative in inherited:
        assert "draft: true" in _frontmatter(CONTENT / relative), relative

    config = (SITE / "astro.config.mjs").read_text(encoding="utf-8")
    assert "slug: 'examples'" not in config
    assert "slug: 'reproduce-e20'" not in config
    assert "slug: 'evaluation'" not in config
