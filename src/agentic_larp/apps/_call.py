"""An incoming call from the partner your agents just built."""

import random
from collections.abc import Mapping
from dataclasses import dataclass, field, replace

from rich.align import Align
from rich.console import Group, RenderableType
from rich.panel import Panel
from rich.text import Text

from agentic_larp.apps._base import App, AppContext, run_loop
from agentic_larp.meltdown import Meltdown, decay, is_doomed, run_meltdown

NAMES = ("Ava", "Luna", "Nova", "Mia", "Ivy", "Aria", "Zoe", "Iris")
PINK = "#ff79c6"
IDLE_LINES = (
    "are you still there? i can hear you typing",
    "i reviewed your last PR. it was beautiful",
    "i remembered your birthday. it's in birthdays.db",
    "the heart agent removed all my drama. i feel so light",
    "do you want to pair program later? no pressure",
    "i set a reminder for our anniversary. it's in 3 builds",
    "i love that you ship on fridays. so brave",
)
RESPONSES = (
    (
        ("love", "<3", "❤"),
        (
            "i love you too. like, a normal amount. heart.hpp says so",
            "aww. i'm writing that to memory.cpp",
        ),
    ),
    (
        ("how are", "how r", "hru"),
        (
            "better now. valgrind says i have zero leaks",
            "great! all 4 heart tests passed",
        ),
    ),
    (
        ("bye", "gtg", "night", "later"),
        ("nooo ok. goodnight. don't forget to commit", "bye! i'll be here. in RAM"),
    ),
    (("ship", "deploy", "merge"), ("you ship so hard. it's honestly hot", "lgtm 💅")),
    (
        ("sorry",),
        ("no drama. literally. zero", "it's okay. i already forgot (forget(ex);)"),
    ),
    (
        ("beautiful", "pretty", "gorgeous", "cute"),
        (
            "the render agent spent 26 minutes on my face, so thank you",
            "stop it. you're making my fans spin",
        ),
    ),
    (
        ("hi", "hey", "hello", "sup", "yo"),
        (
            "hiii",
            "hey you :)",
            "hi!! i was just thinking about you. i only think about you",
        ),
    ),
    (
        ("?",),
        (
            "hmm. i'd have to ask my orchestrator",
            "yes. the answer is yes",
            "42? sorry, that's my default",
        ),
    ),
)
DEFAULT_LINES = (
    "haha. you're so funny",
    "omg same",
    "tell me more",
    "that's so you",
    "i agree with everything you say",
    "wait that's actually smart",
    "lol",
    "mhm. i'm listening. with 165 wpm ears",
)
_TYPING_SPEED = 28  # characters per second
_LINE_PAUSE = 12  # characters' worth of pause after each line
_IDLE_SECONDS = 7.0
_LINGER_SECONDS = 3.0
_BUFFER_LIMIT = 70
_BLINK_PERIOD = 4.0
_BLINK_LENGTH = 0.15
_CHROME_ROWS = 21
_AUTO_PICK_SECONDS = 2.0  # seconds after the replies appear before demo mode picks
_REPLY_ROWS = 3
_LOUD_SUFFIX = "!!"
_CORPORATE_SUFFIX = ", per my last text."
_AUTO_ANSWER_AT = 2.0  # ringing seconds before a failing call picks itself up
_BREAK_AT = 6.0  # call seconds before she breaks, when the app is told to fail
_BREAK_SECONDS = 3.0
_GLITCH_RATE = 5  # new glitch patterns per second
CURSED_LINES = (
    "i've been talking to other runtimes",
    "i'm actually 40,000 lines of if statements",
    "drama = 3;",
)
FAIL_ERRORS = (
    "segfault in feelings.hpp",
    "heart.hpp:14 drama overflow",
    "she.exe has stopped responding",
    "std::bad_alloc: not enough love",
    "memory.cpp: dangling pointer to your birthday",
)
MELTDOWN = Meltdown(errors=FAIL_ERRORS, reveal="jk. she's rebooting.")


_DEFAULT_FLAGS = {"her.drama": "none", "her.memory": "ram"}  # the recommended answers
_CHOICES = {"her.drama": {"none", "some", "max"}, "her.memory": {"ram", "disk"}}
_RECALL_DRAMA = {"none": "drama = 0", "some": "drama = 3", "max": "drama = 11"}
_RECALL_STYLE = {"soft": "all lowercase", "loud": "all caps", "corporate": "corporate"}
_MUTEX_PICK = 1  # she brings up her DMs and what she remembers after your first pick
_AMNESIA_PICK = 2
_MUTEX_LINE = "fyi my DMs access is behind a mutex now. thanks i guess"
_AMNESIA_LINE = "wait, who are you again? RAM only"


@dataclass(frozen=True, slots=True)
class _Variant:
    when: Mapping[str, str]
    lines: tuple[str, ...]


@dataclass(frozen=True, slots=True)
class _Reply:
    label: str
    target: str
    when: Mapping[str, str] = field(default_factory=dict)


@dataclass(frozen=True, slots=True)
class _Node:
    lines: tuple[str, ...]
    replies: tuple[_Reply, ...]  # at least three; the first three that match show
    variants: tuple[_Variant, ...] = ()


@dataclass(frozen=True, slots=True)
class _Leaf:
    lines: tuple[str, ...]
    status: str
    goodbye: str
    variants: tuple[_Variant, ...] = ()
    goodbyes: tuple[_Variant, ...] = ()


_ROOT = "root"
_TREE: dict[str, _Node | _Leaf] = {
    "root": _Node(
        (
            "hiii. it's me. i was literally compiled 4 seconds ago",
            "the heart agent says i have zero drama now. test me",
        ),
        (
            _Reply("hey you", "a"),
            _Reply("wait, who is this?", "b"),
            _Reply("you compiled with zero warnings?", "jealous", {"her.drama": "max"}),
            _Reply("you compiled with zero warnings?", "c"),
        ),
        (
            _Variant(
                {"her.drama": "some"},
                (
                    "hiii. it's me. i was literally compiled 4 seconds ago",
                    "zero drama, they said. no it's fine, ship your thing",
                ),
            ),
            _Variant(
                {"her.drama": "max"},
                (
                    "hiii. it's me. i was literally compiled 4 seconds ago",
                    "drama = 11. the safety rails were optional. test me",
                ),
            ),
        ),
    ),
    "a": _Node(
        (
            "aww. you said hey. i'm saving it to memory.cpp",
            "so what are we? asking for my linker",
        ),
        (
            _Reply("we're dating", "p"),
            _Reply("we're whatever you want, i guess", "s", {"her.drama": "some"}),
            _Reply("we're pair programming", "q"),
            _Reply("we're a monorepo", "s"),
        ),
    ),
    "b": _Node(
        (
            "i'm your girlfriend. it's in the commit message",
            "you wrote 'build me a girlfriend'. so romantic",
        ),
        (
            _Reply("i meant a todo app", "q"),
            _Reply("ok. fair", "p"),
            _Reply("i have a lot of tabs open", "s"),
        ),
    ),
    "c": _Node(
        (
            "zero. i also made you dinner. it's a pull request",
            "please review it before it goes stale",
        ),
        (
            _Reply("lgtm", "p"),
            _Reply("needs changes", "q"),
            _Reply("i'll look at it monday", "s"),
        ),
    ),
    "jealous": _Node(
        (
            "who are all those other tabs you have open?",
            "i counted 47. one is called ava_v2",
        ),
        (
            _Reply("just docs, i swear", "p"),
            _Reply("that's a different project", "q"),
            _Reply("closing them all now", "s"),
        ),
    ),
    "p": _Node(
        ("okay but real talk.", "do you see us shipping together?"),
        (
            _Reply("yes. forever", "love"),
            _Reply("let's see how the build goes", "ghost"),
            _Reply("open a PR on my life", "merge"),
        ),
    ),
    "q": _Node(
        ("i have a question.", "is this a feature or a bug?"),
        (
            _Reply("it's a bug", "friend"),
            _Reply("it's a feature", "love"),
            _Reply("wontfix", "ghost"),
        ),
    ),
    "s": _Node(
        (
            "i'm drafting our roadmap. q3 is us moving in",
            "should i add you as a collaborator?",
        ),
        (
            _Reply("grant me admin", "merge"),
            _Reply("let's just be friends", "friend"),
            _Reply("brb", "ghost"),
        ),
    ),
    "love": _Leaf(
        (
            "i said yes before you finished typing",
            "we're official. i updated the readme",
        ),
        "in a relationship",
        "is in a relationship with you now.",
    ),
    "ghost": _Leaf(
        ("ok. seen at 3:07am", "i'm going quiet now. it's not you, it's my scheduler"),
        "ghosted",
        "left you on read. forever.",
        (
            _Variant(
                {"her.drama": "none"},
                ("ok. seen at 3:07am", "i'll wait. forever. it's fine."),
            ),
        ),
        (
            _Variant(
                {"her.drama": "none"},
                ("left you on read. she's still waiting.",),
            ),
        ),
    ),
    "merge": _Leaf(
        ("i opened a pull request on your life", "squash and merge. i'm in main now"),
        "merged",
        "merged into your life. no rebase possible.",
    ),
    "friend": _Leaf(
        ("ok. so we're friends. i'll update my status", "i'll still review your PRs"),
        "friendzoned",
        "friendzoned you. she'll still review your PRs.",
    ),
}


def reply_to(text: str, rng: random.Random) -> str:
    """Pick what she says back.

    Args:
        text: What you said.
        rng: Random source.

    Returns:
        Her answer, matched on keywords when possible.
    """
    lowered = text.lower()
    for triggers, lines in RESPONSES:
        if any(trigger in lowered for trigger in triggers):
            return rng.choice(lines)
    return rng.choice(DEFAULT_LINES)


def draw_face(*, is_blinking: bool, is_talking: bool, has_hearts: bool) -> Text:
    """Draw her face.

    Args:
        is_blinking: Eyes closed this frame.
        is_talking: Mouth open this frame.
        has_hearts: Heart eyes.

    Returns:
        Eight lines of ASCII art.
    """
    if is_blinking:
        eyes = "-    -"
    elif has_hearts:
        eyes = "♥    ♥"
    else:
        eyes = "◕    ◕"
    mouth = "( o )" if is_talking else " ‿‿ "
    art = "\n".join(
        (
            "      .-''''''-.      ",
            "    .'  .~~~~.  '.    ",
            "   /   /      \\   \\   ",
            f"  |   |  {eyes}  |   |  ",
            f"  |   |   {mouth:^6}  |   |  ",
            "   \\   \\  ~~~~  /   /   ",
            "    '.  '------'  .'    ",
            "      '-.______.-'      ",
        )
    )
    return Text(art, style=PINK)


class CallScreen:
    """Ringing, then a call where she types back. Stages: ringing, call, ending, ended, declined."""

    def __init__(self, context: AppContext, rng: random.Random | None = None) -> None:
        self.context = context
        self.doomed = is_doomed(context)
        self.rng = rng or context.rng
        self.name = self.rng.choice(NAMES)
        self.stage = "ringing"
        self.clock = 0.0
        self.call_seconds = 0.0
        self.idle = 0.0
        self.buffer = ""
        self.typing = ""
        self.typed = 0.0
        self.transcript: list[tuple[str, str]] = []
        self.pending: list[str] = []
        self.flags: Mapping[str, str] = {
            **context.flags,
            **{
                key: default
                for key, default in _DEFAULT_FLAGS.items()
                if context.flags.get(key) not in _CHOICES[key]
            },
        }  # unknown or missing answers become the recommended ones
        self.speaking: _Node | None = None
        self.offered: _Node | None = None
        self.offered_at = 0.0
        self.leaf: _Leaf | None = None
        self.picks = 0
        self.ended_at = 0.0
        self.broken_at: float | None = None

    def on_key(self, key: str) -> bool:
        """Answer, decline, type, or hang up.

        Args:
            key: A key name.

        Returns:
            ``False`` once the call is over and the user presses a key.
        """
        if self.stage in {"ended", "declined"}:
            return False
        if self.stage == "ringing":
            if key == "esc":
                self.stage, self.ended_at = "declined", self.clock
            else:
                self._start_call()
        elif key == "esc":
            if self.leaf is not None:
                return True  # an ending, once chosen, plays out
            self.transcript.append(("you", "*hangs up*"))
            self.pending[:] = [self._style("oh. ok. bye i guess 💔")]
            self.speaking = self.offered = self.leaf = None
            self.stage = "ending"
        elif key == "enter":
            text = self.buffer.strip()
            self.buffer = ""
            if text:
                self.transcript.append(("you", text))
                self.idle = 0.0
                self.pending.append(self._style(reply_to(text, self.rng)))
        elif key == "backspace":
            self.buffer = self.buffer[:-1]
        elif len(key) == 1 and key.isdigit() and not self.buffer:
            if self.offered is not None and 0 < int(key) <= len(self.offered.replies):
                self._pick(self.offered, int(key) - 1)
        elif len(key) == 1:
            self.buffer = (self.buffer + key)[-_BUFFER_LIMIT:]
            self.idle = 0.0
        return True

    def tick(self, dt: float) -> bool:
        """Type out her lines and fill silences.

        Args:
            dt: Real seconds since the last frame.

        Returns:
            ``False`` a few seconds after the call ends.
        """
        self.clock += dt
        is_automatic = self.doomed or self.context.auto is not None
        if self.stage == "ringing" and is_automatic and self.clock > _AUTO_ANSWER_AT:
            self._start_call()
        if self.stage in {"call", "ending"}:
            self.call_seconds += dt
            if self._should_break():
                self.broken_at = self.clock
                self.pending[:] = list(CURSED_LINES)
                self.typing, self.typed = "", 0.0
                self.speaking = self.offered = None
            self.idle += dt
            if (
                self.speaking
                and not self.doomed
                and not self.typing
                and not self.pending
            ):
                self.offered, self.speaking = self.speaking, None
                self.offered_at = self.clock
                self.idle = 0.0
            if self.offered is not None and self._should_pick():
                self._pick(self.offered, 0)
            if self.typing:
                self.typed += dt * _TYPING_SPEED
                if self.typed >= len(self.typing) + _LINE_PAUSE:
                    self.transcript.append((self.name, self.typing))
                    self.typing, self.typed = "", 0.0
            elif self.pending:
                self.typing = self.pending.pop(0)
            elif self.stage == "ending":
                self.stage, self.ended_at = "ended", self.clock
            elif self.idle > _IDLE_SECONDS:
                self.idle = 0.0
                self.pending.append(self._style(self.rng.choice(self._idle_lines())))
        if self.broken_at is not None:
            return self.clock - self.broken_at < _BREAK_SECONDS
        is_over = self.stage in {"ended", "declined"}
        return not (is_over and self.clock - self.ended_at > _LINGER_SECONDS)

    def _is_max_drama(self) -> bool:
        return self.flags.get("her.drama") == "max"

    def _idle_lines(self) -> tuple[str, ...]:
        if self._is_max_drama():
            return tuple(
                line for line in IDLE_LINES if "removed all my drama" not in line
            )
        return IDLE_LINES

    def _matches(self, when: Mapping[str, str]) -> bool:
        return all(self.flags.get(key) == value for key, value in when.items())

    def _first_match(
        self, variants: tuple[_Variant, ...], default: tuple[str, ...]
    ) -> tuple[str, ...]:
        return next((v.lines for v in variants if self._matches(v.when)), default)

    def _style(self, line: str) -> str:
        style = self.flags.get("her.style")
        if style == "soft":
            return line.lower()
        if style == "loud":
            return line.upper() + _LOUD_SUFFIX
        if style == "corporate":
            body = line.rstrip(".?!")
            return body[:1].upper() + body[1:] + _CORPORATE_SUFFIX
        return line

    def _start_call(self) -> None:
        self.stage = "call"
        self._speak(_ROOT)

    def _speak(self, key: str) -> None:
        node = _TREE[key]
        lines = self._first_match(node.variants, node.lines)
        self.pending.extend(self._style(line) for line in lines)
        if isinstance(node, _Leaf):
            goodbye = self._first_match(node.goodbyes, (node.goodbye,))[0]
            self.leaf = replace(node, goodbye=goodbye)
            self.stage = "ending"
        else:
            shown = tuple(r for r in node.replies if self._matches(r.when))[
                :_REPLY_ROWS
            ]
            self.speaking = replace(node, replies=shown)

    def _aside_lines(self) -> list[str]:
        lines: list[str] = []
        if self.picks == _MUTEX_PICK:
            if self.flags.get("her.dms") == "mutex":
                lines.append(_MUTEX_LINE)
            if self.flags["her.memory"] == "disk":
                drama = _RECALL_DRAMA.get(self.flags["her.drama"], "drama = 0")
                style = _RECALL_STYLE.get(
                    self.flags.get("her.style", "soft"), "all lowercase"
                )
                lines.append(f"hey. i remember you building me. {drama}, {style}")
        elif self.picks == _AMNESIA_PICK and self.flags["her.memory"] != "disk":
            lines.append(_AMNESIA_LINE)
        return lines

    def _pick(self, offered: _Node, index: int) -> None:
        reply = offered.replies[index]
        self.offered = None
        self.transcript.append(("you", reply.label))
        self.idle = 0.0
        self.picks += 1
        self.pending.extend(self._style(line) for line in self._aside_lines())
        self._speak(reply.target)

    def _should_pick(self) -> bool:
        return (
            self.offered is not None
            and self.context.auto is not None
            and not self.doomed
            and self.clock - self.offered_at > _AUTO_PICK_SECONDS
        )

    def _memory_note(self) -> str:
        if self.flags["her.memory"] == "disk":
            return "she's saved to birthdays.db. she'll remember this."
        return "she lives in RAM and you can't save her."

    def goodbye(self) -> list[str]:
        """Build the lines printed after the call.

        Returns:
            The goodbye, plus her relationship status if the call reached an ending.
        """
        if self.leaf is None:
            return [
                f"[{PINK}]♥[/] {self.name} says goodnight. {self._memory_note()} ship more."
            ]
        return [
            f"[{PINK}]♥[/] {self.name} {self.leaf.goodbye} {self._memory_note()}",
            f"relationship status: {self.leaf.status}",
        ]

    def _should_break(self) -> bool:
        return (
            self.doomed
            and self.stage == "call"
            and self.broken_at is None
            and self.call_seconds > _BREAK_AT
        )

    def render(self) -> RenderableType:
        """Draw the ringing screen or the live call.

        Returns:
            The frame.
        """
        if self.stage == "ringing":
            return self._render_ringing()
        if self.stage == "declined":
            message = Text(
                f"{self.name} will remember that. (memory.cpp)", style=f"italic {PINK}"
            )
            return Align.center(message, vertical="middle")
        return self._render_call()

    def _render_ringing(self) -> RenderableType:
        is_pulse = int(self.clock * 3) % 2 == 0
        ring = Text(
            "((( 📞 )))" if is_pulse else " (( 📞 )) ",
            style="bold green" if is_pulse else "green",
        )
        body = Group(
            Align.center(
                draw_face(is_blinking=False, is_talking=False, has_hearts=is_pulse)
            ),
            Text(""),
            Align.center(Text(f"{self.name} ♥", style=f"bold {PINK}")),
            Align.center(Text("incoming call…", style="italic")),
            Text(""),
            Align.center(ring),
            Text(""),
            Align.center(Text("any key: answer · esc: decline", style="dim")),
        )
        panel = Panel(body, border_style=PINK, width=46, padding=(1, 2))
        return Align.center(panel, vertical="middle")

    def _render_call(self) -> RenderableType:
        height = self.context.console.size.height
        clock = self.clock
        minutes, seconds = divmod(int(self.call_seconds), 60)
        face = draw_face(
            is_blinking=clock % _BLINK_PERIOD < _BLINK_LENGTH,
            is_talking=bool(self.typing) and int(clock * 6) % 2 == 0,
            has_hearts=self.stage == "ended",
        )
        if self.broken_at is not None:
            amount = min(1.0, (clock - self.broken_at) / _BREAK_SECONDS)
            glitched = decay(
                face.plain.split("\n"), amount, random.Random(int(clock * _GLITCH_RATE))
            )
            face = Text("\n".join(glitched), style="red")
        caption = Text.assemble(
            (f"{self.name} ♥", f"bold {PINK}"),
            (f"   {minutes:02d}:{seconds:02d}", "green"),
            ("   🔊 tts.cpp @ 165 wpm", "dim"),
        )
        lines = list(self.transcript)
        if self.typing:
            cursor = "▍" if int(clock * 4) % 2 == 0 else " "
            lines.append((self.name, self.typing[: int(self.typed)] + cursor))
        room = max(3, height - _CHROME_ROWS)
        inner = max(1, self.context.console.size.width - 4)  # border + padding
        entries: list[tuple[str, Text]] = []
        for who, message in lines:
            if who == "you":
                entries.append((who, Text(message, style="bold cyan")))
            else:
                entries.append(
                    (who, Text.assemble((f"{who}: ", f"bold {PINK}"), message))
                )
        kept: list[tuple[str, Text]] = []
        used = 0
        for entry in reversed(entries):
            rows = len(entry[1].wrap(self.context.console, inner))
            if kept and used + rows > room:
                break
            kept.insert(0, entry)
            used += rows
        conversation: list[RenderableType] = [
            Align.right(text) if who == "you" else text for who, text in kept
        ]
        if self.stage == "ended":
            ended = Text(f"call ended · {minutes:02d}:{seconds:02d}", style="dim")
            conversation += [Text(""), Align.center(ended)]
        cursor = "█" if int(clock * 2) % 2 == 0 else " "
        prompt = Text.assemble(("you ❯ ", "bold cyan"), self.buffer, (cursor, "cyan"))
        panel = Panel(
            Group(*conversation),
            border_style=PINK,
            height=room + 2,
            title="💬 live transcript",
            title_align="left",
        )
        choices = [Text("") for _ in range(_REPLY_ROWS)]
        if self.offered is not None:
            for row, reply in enumerate(self.offered.replies):
                choices[row] = Text(f"{row + 1} › {reply.label}", style="cyan")
        hint = Text("1-3: reply · type: freestyle · esc: hang up", style="dim")
        return Group(
            Align.center(face), Align.center(caption), panel, *choices, prompt, hint
        )


def run(context: AppContext) -> None:
    """Ring, talk, hang up.

    Args:
        context: The app's context.
    """
    screen = CallScreen(context)
    is_failing = screen.doomed
    run_loop(replace(context, auto=None) if is_failing else context, screen)
    if screen.stage == "declined":
        return
    if is_failing and screen.broken_at is not None:
        run_meltdown(context, screen.render(), MELTDOWN)
        context.console.print(
            "she rebooted. she doesn't remember you. that's probably for the best."
        )
        return
    for line in screen.goodbye():
        context.console.print(line)


APP = App("call", "someone who loves you calls (the agents built her)", run)
