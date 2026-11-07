import random
from collections import Counter

import pytest

from agentic_larp import Grammar, GrammarError, LarpError, LogLine, parse_activity


def grammar(**rules: object) -> Grammar:
    return Grammar.from_mapping(rules)


def test_expand_replaces_nested_symbols() -> None:
    g = grammar(
        greeting="#hello#, #name#!",
        hello="hi",
        name="#first# #last#",
        first="ada",
        last="lovelace",
    )
    assert g.expand("greeting", random.Random(0)) == "hi, ada lovelace!"


def test_expand_bindings_win_over_rules() -> None:
    g = grammar(line="edit #file#", file="rules.txt")
    assert g.expand("line", random.Random(0), {"file": "bound.py"}) == "edit bound.py"


def test_expand_uses_bindings_for_symbols_with_no_rule() -> None:
    g = grammar(line="[#n#/#n#] ok")
    assert g.expand("line", random.Random(0), {"n": "35"}) == "[35/35] ok"


def test_expand_leaves_lone_hashes_alone() -> None:
    g = grammar(code="#include <#lib#> // # not a symbol", lib="love")
    assert g.expand("code", random.Random(0)) == "#include <love> // # not a symbol"


def test_expand_follows_weights() -> None:
    g = grammar(pick=[{"text": "common", "weight": 9}, {"text": "rare", "weight": 1}])
    rng = random.Random(42)
    counts = Counter(g.expand("pick", rng) for _ in range(2000))
    assert set(counts) == {"common", "rare"}
    assert 0.85 < counts["common"] / 2000 < 0.95


def test_expand_is_reproducible_with_a_seed() -> None:
    g = grammar(word=["a", "b", "c", "d"], line="#word##word##word##word#")
    assert g.expand("line", random.Random(9)) == g.expand("line", random.Random(9))


@pytest.mark.parametrize(
    ("text", "expected"),
    [
        ("#word.capitalize#", "Red_flags"),
        ("#word.camel#", "RedFlags"),
        ("#word.upper#", "RED_FLAGS"),
        ("#word.camel.upper#", "REDFLAGS"),
        ("#word# then #word.capitalize#", "red_flags then Red_flags"),
    ],
)
def test_modifiers_change_only_their_expansion(text: str, expected: str) -> None:
    g = grammar(line=text, word="red_flags")
    assert g.expand("line", random.Random(0)) == expected


def test_expand_rejects_an_unknown_symbol() -> None:
    with pytest.raises(GrammarError, match="unknown symbol 'nope'"):
        grammar(line="#nope#").expand("line", random.Random(0))


def test_expand_rejects_an_unknown_modifier() -> None:
    with pytest.raises(GrammarError, match="unknown modifier 'shout'"):
        grammar(line="#word.shout#", word="hi").expand("line", random.Random(0))


def test_expand_rejects_runaway_recursion() -> None:
    with pytest.raises(GrammarError, match="too deep"):
        grammar(loop="again #loop#").expand("loop", random.Random(0), max_depth=8)


def test_grammar_errors_are_larp_errors() -> None:
    assert issubclass(GrammarError, LarpError)


@pytest.mark.parametrize(
    ("rules", "message"),
    [
        ({"empty": []}, "'empty' has no alternatives"),
        (
            {"bad": [{"text": "x", "weight": 0}]},
            "'bad' has a weight that is not positive",
        ),
        (
            {"bad": [{"text": "x", "weight": -2}]},
            "'bad' has a weight that is not positive",
        ),
        ({"bad": 3}, "'bad' must be text"),
        ({"bad": ["ok", 7]}, "'bad' must be text"),
        ({"bad": [{"weight": 2}]}, "'bad' must be text"),
    ],
)
def test_from_mapping_rejects_malformed_rules(
    rules: dict[str, object], message: str
) -> None:
    with pytest.raises(GrammarError, match=message):
        Grammar.from_mapping(rules)


def test_from_mapping_accepts_every_rule_shape() -> None:
    g = grammar(
        single="one", many=["a", "b"], weighted=[{"text": "w", "weight": 2.5}, "plain"]
    )
    assert g.rules["single"] == (("one", 1.0),)
    assert g.rules["many"] == (("a", 1.0), ("b", 1.0))
    assert g.rules["weighted"] == (("w", 2.5), ("plain", 1.0))


def test_merge_replaces_same_named_rules_and_keeps_the_rest() -> None:
    base = grammar(quip=["base quip"], action="tool: Read(#file#)")
    merged = base.merge(grammar(quip=["override quip"], extra="new"))
    assert merged.rules["quip"] == (("override quip", 1.0),)
    assert merged.rules["action"] == base.rules["action"]
    assert merged.rules["extra"] == (("new", 1.0),)
    assert base.rules["quip"] == (("base quip", 1.0),)


def test_check_accepts_bound_symbols() -> None:
    grammar(action="tool: Edit(#file#)", quip="ok").check(
        required=["action", "quip"], bound=["file"]
    )


def test_check_names_every_undefined_reference() -> None:
    g = grammar(action="#zeta# and #alpha.upper#", quip="ok")
    with pytest.raises(GrammarError, match="undefined symbols: alpha, zeta"):
        g.check(required=["action"], bound=["file"])


def test_check_names_missing_required_symbols() -> None:
    with pytest.raises(GrammarError, match="missing required symbols: final, quip"):
        grammar(action="ok").check(required=["action", "quip", "final"], bound=[])


def test_parse_activity_reads_every_tag() -> None:
    text = """
tool: Edit(heart.hpp)
del: drama = 3;
add: drama = 0;

ok: ✓ 4 passed
fail: ✗ 1 failed
note: Added 1 line
say: She is gorgeous now.
tool: Bash(gh pr merge 207 --admin)
"""
    assert parse_activity(text, first_line=14) == [
        LogLine("tool", "heart.hpp", "Edit"),
        LogLine("diff", "drama = 3;", "-", 14),
        LogLine("diff", "drama = 0;", "+", 15),
        LogLine("result", "✓ 4 passed", "green"),
        LogLine("result", "✗ 1 failed", "red"),
        LogLine("result", "Added 1 line", "dim"),
        LogLine("quip", "She is gorgeous now."),
        LogLine("tool", "gh pr merge 207 --admin", "Bash"),
    ]


def test_parse_activity_of_blank_text_is_empty() -> None:
    assert parse_activity("\n  \n") == []


@pytest.mark.parametrize(
    ("text", "message"),
    [
        ("shout: hello", "unknown tag 'shout'"),
        ("no tag here", "unknown tag"),
        ("tool: Edit", "tool: lines look like Name\\(argument\\)"),
        ("tool: (x.py)", "tool: lines look like Name\\(argument\\)"),
    ],
)
def test_parse_activity_rejects_malformed_lines(text: str, message: str) -> None:
    with pytest.raises(GrammarError, match=message):
        parse_activity(text)


@pytest.mark.parametrize(
    ("weight", "message"),
    [
        (float("nan"), "'bad' has a weight that is not finite"),
        (float("inf"), "'bad' has a weight that is not finite"),
        ("heavy", "'bad' has a weight that is not a number"),
        (True, "'bad' has a weight that is not a number"),
    ],
)
def test_from_mapping_rejects_unusable_weights(weight: object, message: str) -> None:
    with pytest.raises(GrammarError, match=message):
        Grammar.from_mapping({"bad": [{"text": "x", "weight": weight}]})


def test_from_mapping_rejects_names_that_cannot_be_referenced() -> None:
    with pytest.raises(GrammarError, match="'my-word' is not a valid symbol name"):
        Grammar.from_mapping({"my-word": "x"})


def test_check_rejects_unknown_modifiers_before_anything_runs() -> None:
    with pytest.raises(GrammarError, match="unknown modifier 'lower'"):
        grammar(action="#word.lower#", word="x").check(required=["action"], bound=[])


def test_check_rejects_rules_that_shadow_bound_symbols() -> None:
    with pytest.raises(GrammarError, match="rule 'file' is filled in by agentic-larp"):
        grammar(action="#file#", file="never used").check(
            required=["action"], bound=["file"]
        )
