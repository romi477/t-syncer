def format_jira_comment(issue_key: str, tag: str | None, message: str) -> str:
    parts = [f"[{issue_key}]"]
    if tag:
        parts.append(f"[{tag}]")
    parts.append(message.strip())

    return " ".join(parts)


def to_adf(text: str) -> dict:

    return {
        "type": "doc",
        "version": 1,
        "content": [
            {
                "type": "paragraph",
                "content": [{"type": "text", "text": text}],
            }
        ],
    }
