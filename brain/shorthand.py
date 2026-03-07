"""Shorthand syntax parser for inline task metadata.

Syntax:
    !priority or ^priority  — priority (low, medium, high, urgent)
    @project                — project name
    #tag                    — tag (multiple allowed)
    ~due or ~"next week"    — due date (quote multi-word values)
    >assignee               — assignee

Note: Use ^ instead of ! in zsh/bash to avoid history expansion issues.
"""

import re


DUE_ALIASES = {
    "today": "today",
    "tod": "today",
    "tmrw": "tomorrow",
    "tomorrow": "tomorrow",
    "mon": "monday",
    "tue": "tuesday",
    "wed": "wednesday",
    "thu": "thursday",
    "fri": "friday",
    "sat": "saturday",
    "sun": "sunday",
    "1d": "1 day",
    "2d": "2 days",
    "3d": "3 days",
    "1w": "1 week",
    "2w": "2 weeks",
    "1m": "1 month",
    "eow": "friday",
    "eom": "next month",
    "nw": "next week",
    "nm": "next month",
}

PRIORITY_ALIASES = {
    "low": "low",
    "med": "medium",
    "medium": "medium",
    "high": "high",
    "urgent": "urgent",
    "crit": "urgent",
    "critical": "urgent",
}

_TOKEN_RE = re.compile(
    r"""
    (?:^|\s)          # start of string or whitespace
    (
      [!^][a-zA-Z]+   # !priority or ^priority
    | @[\w-]+          # @project
    | \#[\w-]+         # #tag
    | ~"[^"]+?"        # ~"next week" (quoted due date)
    | ~[\w/-]+         # ~due (allows slashes for dates)
    | >[\w-]+          # >assignee
    )
    """,
    re.VERBOSE,
)


def parse_shorthand(text: str) -> dict:
    """Parse shorthand tokens from a title string.

    Returns dict with keys: title, priority, project, tags, due, assignee.
    The title has shorthand tokens stripped out.
    """
    priority = None
    project = None
    tags = []
    due = None
    assignee = None

    tokens_to_remove = []

    for match in _TOKEN_RE.finditer(text):
        token = match.group(1)
        tokens_to_remove.append(token)

        if token[0] in ("!", "^"):
            val = token[1:].lower()
            if val in PRIORITY_ALIASES:
                priority = PRIORITY_ALIASES[val]
        elif token.startswith("@"):
            project = token[1:]
        elif token.startswith("#"):
            tags.append(token[1:])
        elif token.startswith("~"):
            raw = token[1:].strip('"').lower()
            due = DUE_ALIASES.get(raw, raw)
        elif token.startswith(">"):
            assignee = token[1:]

    # Strip tokens from the title
    title = text
    for token in tokens_to_remove:
        title = title.replace(token, "", 1)
    title = re.sub(r"\s{2,}", " ", title).strip()

    return {
        "title": title,
        "priority": priority,
        "project": project,
        "tags": tags,
        "due": due,
        "assignee": assignee,
    }
