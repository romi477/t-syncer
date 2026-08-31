from api.tags import TAGS, resolve_tag


def test_tags_are_listed_most_used_first():
    assert [t.code for t in TAGS] == ["DEV", "INT", "SUP", "QA", "DOC", "REL", "DEM"]


def test_a_tag_is_a_code_and_a_label_only():
    """The code is the identity, in the database too, so a tag can be added by
    hand."""
    for tag in TAGS:
        assert not hasattr(tag, "id")
    assert len({tag.code for tag in TAGS}) == len(TAGS)


def test_every_tag_has_a_help_text():
    for tag in TAGS:
        assert tag.label and tag.label != tag.code, tag.code


def test_resolve_tag_is_case_insensitive():
    tag = resolve_tag("  dev ")

    assert tag is not None
    assert tag.code == "DEV"
    assert tag.label == "Development"


def test_resolve_unknown_tag_is_none():
    assert resolve_tag("NOPE") is None
    assert resolve_tag("") is None
    assert resolve_tag(None) is None


def test_support_is_sup_not_sub():
    assert resolve_tag("SUB") is None
    assert resolve_tag("SUP") is not None
