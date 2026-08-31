from api.comments import format_jira_comment, to_adf


def test_comment_with_tag():
    text = format_jira_comment("QBO-120", "DEV", "Text message")

    assert text == "[QBO-120] [DEV] Text message"


def test_comment_without_tag():
    text = format_jira_comment("QBO-120", None, "Text message")

    assert text == "[QBO-120] Text message"


def test_comment_empty_tag_omits_brackets():
    text = format_jira_comment("QBO-120", "", "Text message")

    assert text == "[QBO-120] Text message"


def test_to_adf_wraps_plain_text():
    body = to_adf("[QBO-120] [DEV] Text message")

    assert body == {
        "type": "doc",
        "version": 1,
        "content": [
            {
                "type": "paragraph",
                "content": [{"type": "text", "text": "[QBO-120] [DEV] Text message"}],
            }
        ],
    }
