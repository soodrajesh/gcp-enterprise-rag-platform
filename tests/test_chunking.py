from rag_common.chunking import chunk_markdown

DOC = """# Title

Intro paragraph.

## Section A

Alpha one.

Alpha two.

### Sub A1

Deep content.

## Section B

Bravo.
"""


def test_heading_path_is_preserved():
    chunks = chunk_markdown(DOC)
    headings = [c.heading for c in chunks]
    assert "Title" in headings
    assert "Title > Section A > Sub A1" in headings
    assert "Title > Section B" in headings


def test_indexes_are_sequential():
    chunks = chunk_markdown(DOC)
    assert [c.index for c in chunks] == list(range(len(chunks)))


def test_budget_is_respected_with_overlap_slack():
    big = "# T\n\n" + "\n\n".join(f"Paragraph {i} " + "word " * 60 for i in range(20))
    chunks = chunk_markdown(big, budget=500, overlap=50)
    assert len(chunks) > 3
    assert all(len(c.text) <= 500 + 50 + 2 for c in chunks)


def test_oversized_paragraph_is_hard_split():
    chunks = chunk_markdown("# T\n\n" + "x" * 3000, budget=900, overlap=0)
    assert len(chunks) >= 3


def test_empty_document():
    assert chunk_markdown("") == []
