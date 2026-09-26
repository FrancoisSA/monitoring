import pytest

from capucine.prompts import load_prompt


def test_load_prompt_reads_existing_markdown_file():
    content = load_prompt("digest")

    assert "{articles}" in content


def test_load_prompt_raises_clear_error_for_missing_file():
    with pytest.raises(FileNotFoundError, match="inconnu.md"):
        load_prompt("inconnu")
