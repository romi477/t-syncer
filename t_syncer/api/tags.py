from dataclasses import dataclass


@dataclass(frozen=True)
class Tag:
    code: str
    label: str


# Listed most used first. The code is the identity, in the database as well,
# so this order is free to change and a tag can be added by hand.
TAGS: tuple[Tag, ...] = (
    Tag("DEV", "Development"),
    Tag("INT", "Internal communications"),
    Tag("SUP", "Support and escalations"),
    Tag("QA", "Testing (separate activity)"),
    Tag("DOC", "Documentation"),
    Tag("REL", "Releases"),
    Tag("DEM", "Demos and customer meetings"),
)

_BY_CODE = {tag.code: tag for tag in TAGS}


def resolve_tag(code: str | None) -> Tag | None:
    if not code or not str(code).strip():

        return None

    return _BY_CODE.get(str(code).strip().upper())
