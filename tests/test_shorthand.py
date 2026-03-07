"""Tests for shorthand syntax parser."""

from brain.shorthand import parse_shorthand


def test_basic_title_only():
    result = parse_shorthand("Fix the login bug")
    assert result["title"] == "Fix the login bug"
    assert result["priority"] is None
    assert result["project"] is None
    assert result["tags"] == []
    assert result["due"] is None
    assert result["assignee"] is None


def test_priority():
    result = parse_shorthand("Fix login bug !high")
    assert result["title"] == "Fix login bug"
    assert result["priority"] == "high"


def test_priority_alias():
    result = parse_shorthand("Fix login bug !crit")
    assert result["priority"] == "urgent"


def test_project():
    result = parse_shorthand("Fix login bug @webapp")
    assert result["title"] == "Fix login bug"
    assert result["project"] == "webapp"


def test_tags():
    result = parse_shorthand("Fix login bug #auth #security")
    assert result["title"] == "Fix login bug"
    assert result["tags"] == ["auth", "security"]


def test_due():
    result = parse_shorthand("Fix login bug ~friday")
    assert result["title"] == "Fix login bug"
    assert result["due"] == "friday"


def test_due_date_format():
    result = parse_shorthand("Fix login bug ~2024-03-15")
    assert result["due"] == "2024-03-15"


def test_assignee():
    result = parse_shorthand("Fix login bug >alice")
    assert result["title"] == "Fix login bug"
    assert result["assignee"] == "alice"


def test_all_tokens():
    result = parse_shorthand("Fix login bug !high @webapp #auth ~friday >alice")
    assert result["title"] == "Fix login bug"
    assert result["priority"] == "high"
    assert result["project"] == "webapp"
    assert result["tags"] == ["auth"]
    assert result["due"] == "friday"
    assert result["assignee"] == "alice"


def test_tokens_in_middle():
    result = parse_shorthand("Fix !high login bug @webapp")
    assert result["priority"] == "high"
    assert result["project"] == "webapp"
    assert "login bug" in result["title"]


def test_empty_string():
    result = parse_shorthand("")
    assert result["title"] == ""


def test_unknown_priority_ignored():
    result = parse_shorthand("Fix bug !unknown")
    assert result["priority"] is None
    assert "Fix bug" in result["title"]


def test_caret_priority():
    result = parse_shorthand("Fix login bug ^high")
    assert result["title"] == "Fix login bug"
    assert result["priority"] == "high"


def test_caret_priority_urgent():
    result = parse_shorthand("Deploy now ^urgent @prod")
    assert result["priority"] == "urgent"
    assert result["project"] == "prod"


def test_quoted_due_date():
    result = parse_shorthand('Fix bug ~"next week" @webapp')
    assert result["due"] == "next week"
    assert result["project"] == "webapp"
    assert result["title"] == "Fix bug"


def test_due_alias_tmrw():
    result = parse_shorthand("Fix bug ~tmrw")
    assert result["due"] == "tomorrow"


def test_due_alias_1w():
    result = parse_shorthand("Fix bug ~1w")
    assert result["due"] == "1 week"


def test_due_alias_nw():
    result = parse_shorthand("Fix bug ~nw")
    assert result["due"] == "next week"


def test_due_alias_fri():
    result = parse_shorthand("Fix bug ~fri")
    assert result["due"] == "friday"


def test_due_alias_eow():
    result = parse_shorthand("Fix bug ~eow")
    assert result["due"] == "friday"


def test_due_unknown_passthrough():
    result = parse_shorthand("Fix bug ~2025-12-31")
    assert result["due"] == "2025-12-31"
