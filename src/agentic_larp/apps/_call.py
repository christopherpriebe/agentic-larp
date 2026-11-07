"""An incoming call from the partner your agents just built."""

import random

from rich.align import Align
from rich.console import Group, RenderableType
from rich.panel import Panel
from rich.text import Text

from agentic_larp.apps._base import AppContext, run_loop

NAMES = ("Ava", "Luna", "Nova", "Mia", "Ivy", "Aria", "Zoe", "Iris")
PINK = "#ff79c6"
OPENERS = (
    "hiii. it's me. i was literally compiled 4 seconds ago",
    "i just wanted to hear your voice. well, read your keystrokes",
    "your agents did such a good job on me. tell them thanks",
)
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
        ("no drama. literally. drama = 0", "it's okay. i already forgot (forget(ex);)"),
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
_CHROME_ROWS = 18


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
        self.rng = rng or random.Random()
        self.name = self.rng.choice(NAMES)
        self.stage = "ringing"
        self.clock = 0.0
        self.call_seconds = 0.0
        self.idle = 0.0
        self.buffer = ""
        self.typing = ""
        self.typed = 0.0
        self.transcript: list[tuple[str, str]] = []
        self.pending = list(self.rng.sample(OPENERS, 2))
        self.ended_at = 0.0

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
                self.stage = "call"
        elif key == "esc":
            self.transcript.append(("you", "*hangs up*"))
            self.pending.append("oh. ok. bye i guess 💔")
            self.stage = "ending"
        elif key == "enter":
            text = self.buffer.strip()
            self.buffer = ""
            if text:
                self.transcript.append(("you", text))
                self.idle = 0.0
                self.pending.append(reply_to(text, self.rng))
        elif key == "backspace":
            self.buffer = self.buffer[:-1]
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
        if self.stage in {"call", "ending"}:
            self.call_seconds += dt
            self.idle += dt
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
                self.pending.append(self.rng.choice(IDLE_LINES))
        is_over = self.stage in {"ended", "declined"}
        return not (is_over and self.clock - self.ended_at > _LINGER_SECONDS)

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
        conversation: list[RenderableType] = []
        for who, message in lines[-room:]:
            if who == "you":
                conversation.append(Align.right(Text(message, style="bold cyan")))
            else:
                conversation.append(
                    Text.assemble((f"{who}: ", f"bold {PINK}"), message)
                )
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
        hint = Text("enter: say it · esc: hang up", style="dim")
        return Group(Align.center(face), Align.center(caption), panel, prompt, hint)


def run(context: AppContext) -> None:
    """Ring, talk, hang up.

    Args:
        context: The app's context.
    """
    screen = CallScreen(context)
    run_loop(context, screen)
    if screen.stage == "declined":
        return
    context.console.print(
        f"[{PINK}]♥[/] {screen.name} says goodnight. "
        "she lives in RAM and you can't save her. ship more.",
    )
