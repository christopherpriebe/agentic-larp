"""Scenario packs: what the fake agents pretend to be building."""

import random
import re
from dataclasses import dataclass, field, replace

_MAX_AREAS = 8
_MIN_WORD_LENGTH = 3


@dataclass(frozen=True, slots=True)
class Scenario:
    """A themed set of fake work for the agents.

    Attributes:
        key: Short name used on the command line (``-s key``).
        task: What the user asked for, shown in the header.
        keywords: Words in a task that select this scenario.
        areas: Agent area label mapped to the files that agent touches.
        vocab: Identifiers sprinkled into fake code.
        quips: Things agents say while working.
        finals: Things agents say when they finish.
        commands: Shell commands agents pretend to run.
        app: Name of the app launched after shipping.
    """

    key: str
    task: str
    keywords: tuple[str, ...]
    areas: dict[str, tuple[str, ...]]
    vocab: tuple[str, ...]
    quips: tuple[str, ...]
    finals: tuple[str, ...]
    commands: tuple[str, ...] = field(default_factory=tuple)
    app: str = "deploy"


SCENARIOS: dict[str, Scenario] = {
    scenario.key: scenario
    for scenario in (
        Scenario(
            key="girlfriend",
            task="build me a girlfriend",
            keywords=(
                "girlfriend",
                "boyfriend",
                "partner",
                "date",
                "wife",
                "husband",
                "love",
                "single",
            ),
            areas={
                "render": ("face.cpp", "shaders/eyes.glsl", "hair.cpp"),
                "voice": ("tts.cpp", "voice.hpp", "laugh.wav.cpp"),
                "heart": ("heart.hpp", "heart.cpp", "feelings.hpp"),
                "ring": ("ring.cpp", "carat.hpp"),
                "dialog": ("script.cpp", "smalltalk.cpp", "pet_names.hpp"),
                "build": ("CMakeLists.txt", "toolchain.cmake"),
                "memory": ("memory.cpp", "birthdays.db", "inside_jokes.hpp"),
                "signals": ("signals.cpp", "texts.cpp"),
            },
            vocab=(
                "love",
                "drama",
                "rate",
                "carat",
                "her",
                "you",
                "smile",
                "texts",
                "anniversary",
                "compliments",
                "red_flags",
                "jealousy",
                "cuddles",
                "patience",
                "playlist",
                "dinner",
            ),
            quips=(
                "She is gorgeous now.",
                "Ring sized.",
                "She remembers you.",
                "Removed all red flags.",
                "Taught her to laugh at your jokes.",
                "She texts back now.",
                "drama: 0 (was 3)",
                "Tuned voice to 165 wpm.",
                "Added 'good morning' texts.",
                "She likes your playlist.",
                "She thinks your code is clean.",
                "Anniversary reminder scheduled.",
                "More gorgeous.",
            ),
            finals=(
                "She is ready.",
                "No drama detected.",
                "She remembers your birthday.",
                "Voice is perfect.",
                "Ring fits.",
                "She says hi.",
            ),
            commands=(
                "ninja -j16",
                "ctest heart",
                "valgrind -q ./her",
                "ninja face",
                "clang-tidy *.cpp",
            ),
            app="call",
        ),
        Scenario(
            key="startup",
            task="build a billion dollar startup",
            keywords=(
                "startup",
                "billion",
                "unicorn",
                "company",
                "saas",
                "money",
                "rich",
                "vc",
                "ipo",
            ),
            areas={
                "pitch": ("pitch.ts", "elevator.md"),
                "deck": ("Deck.tsx", "slides/Hockey.tsx"),
                "valuation": ("valuation.ts", "cap_table.csv"),
                "hype": ("hype.ts", "Waitlist.tsx", "tweets.ts"),
                "growth": ("growth/funnel.ts", "referrals.ts"),
                "legal": ("terms.md", "privacy.md"),
                "infra": ("infra.tf", "k8s/web.yaml"),
                "moat": ("moat.ts", "network_effects.ts"),
            },
            vocab=(
                "synergy",
                "runway",
                "arr",
                "burn",
                "valuation",
                "users",
                "hockeyStick",
                "moat",
                "vcs",
                "tam",
                "growth",
                "pivot",
                "unicorn",
                "waitlist",
            ),
            quips=(
                "TAM is now $4T.",
                "Pivoted to AI.",
                "Added blockchain. Removed blockchain.",
                "ARR up 900%.",
                "Hired a Chief Vibes Officer.",
                "Burn rate: acceptable.",
                "Moat widened.",
                "Waitlist at 40k.",
                "Deck has 3 hockey sticks now.",
                "Series A term sheet drafted.",
            ),
            finals=(
                "Valuation: $1.2B.",
                "Deck is fire.",
                "Moat secured.",
                "Investors are calling.",
                "Product-market fit achieved.",
            ),
            commands=(
                "npm test",
                "npm run build",
                "vercel --prod",
                "npx prisma migrate deploy",
            ),
            app="stonks",
        ),
        Scenario(
            key="hacker",
            task="hack the mainframe",
            keywords=(
                "hack",
                "mainframe",
                "breach",
                "cyber",
                "pentest",
                "exploit",
                "firewall",
            ),
            areas={
                "recon": ("recon.py", "nmap_scan.xml"),
                "exploit": ("exploit.c", "overflow.c"),
                "payload": ("payload.asm", "shellcode.bin.c"),
                "crypto": ("rsa.py", "cracker.py"),
                "proxy": ("proxy.go", "tor_chain.go"),
                "firewall": ("firewall.rules", "bypass.py"),
                "backdoor": ("backdoor.c", "persist.sh"),
                "exfil": ("exfil.py", "loot.json"),
            },
            vocab=(
                "mainframe",
                "firewall",
                "packets",
                "root",
                "kernel",
                "cipher",
                "port",
                "shell",
                "payload",
                "proxy",
                "socket",
                "buffer",
                "token",
                "daemon",
            ),
            quips=(
                "Bypassed firewall.",
                "I'm in.",
                "Enhance.",
                "Rerouted through 7 proxies.",
                "Root acquired.",
                "Downloaded more RAM.",
                "Decrypted 2048 bits by hand.",
                "Typing faster helps.",
                "They're tracing us. Added another proxy.",
                "Mainframe is responding.",
            ),
            finals=(
                "Access granted.",
                "We're in.",
                "No logs left behind.",
                "Root shell open.",
            ),
            commands=(
                "nmap -sV 10.0.0.0/8",
                "python3 exploit.py --yolo",
                "make payload",
                "hydra -l admin",
            ),
            app="hacker",
        ),
        Scenario(
            key="prod",
            task="ship to prod on a friday",
            keywords=(
                "prod",
                "deploy",
                "ship",
                "release",
                "friday",
                "production",
                "server",
                "api",
            ),
            areas={
                "api": ("api/server.rs", "api/routes.rs"),
                "db": ("migrations/0042.sql", "schema.rs"),
                "cache": ("cache.rs", "redis.conf"),
                "auth": ("auth.rs", "jwt.rs"),
                "cdn": ("cdn.yaml", "edge.rs"),
                "ci": (".github/workflows/ci.yml", "flaky_test.rs"),
                "infra": ("main.tf", "helm/values.yaml"),
                "oncall": ("runbook.md", "pager.rs"),
            },
            vocab=(
                "latency",
                "replicas",
                "retries",
                "timeout",
                "rollback",
                "canary",
                "shard",
                "pool",
                "uptime",
                "cache",
                "queue",
                "pager",
                "friday",
            ),
            quips=(
                "Migrations look fine (probably).",
                "Disabled the flaky test.",
                "Paged nobody.",
                "CI is green. Do not ask how.",
                "Added retries. Lots of retries.",
                "Rollback plan: vibes.",
                "p99 down to 4ms.",
                "Bumped replicas to 64.",
                "Cache hit rate 100%.",
            ),
            finals=(
                "Ready for prod.",
                "Zero downtime.",
                "Pager is silent.",
                "Green across the board.",
            ),
            commands=(
                "cargo test",
                "cargo build --release",
                "terraform apply -auto-approve",
                "kubectl rollout status deploy/api",
                "gh pr merge 207 --admin",
            ),
            app="deploy",
        ),
    )
}

_GENERIC_QUIPS = (
    "Looks good to me.",
    "Refactored everything.",
    "Tests pass (I wrote them).",
    "Zero bugs remaining.",
    "Added AI.",
    "Works on my machine.",
    "Made it 10x faster.",
    "Deleted 4,000 lines. Still works.",
    "Added dark mode.",
    "This is fine.",
    "Rewrote it in Rust. Then back.",
    "Fixed the bug I introduced.",
)
_GENERIC_FINALS = (
    "Done.",
    "Ship-ready.",
    "All green.",
    "Perfect, actually.",
    "No notes.",
)
_GENERIC_AREAS = ("api", "ui", "tests", "infra", "docs", "auth", "perf", "vibes")
_STOPWORDS = frozenset(
    {
        "the",
        "and",
        "for",
        "with",
        "that",
        "this",
        "build",
        "make",
        "app",
        "some",
        "create",
        "write",
        "please",
        "like",
    }
)


def task_words(task: str) -> list[str]:
    """Pull the meaningful words out of a task, lowercased and deduplicated.

    Args:
        task: Free text such as ``"build uber for cats"``.

    Returns:
        Words of at least three letters that are not filler, in order.
    """
    words = [word.lower() for word in re.findall(r"[A-Za-z]+", task)]
    return [
        word
        for word in dict.fromkeys(words)
        if len(word) >= _MIN_WORD_LENGTH and word not in _STOPWORDS
    ]


def generic_scenario(task: str, rng: random.Random | None = None) -> Scenario:
    """Build a scenario from arbitrary task text.

    Words from the task become agent areas and file names (``cats.ts``,
    ``Cats.tsx``), padded with generic areas up to eight.

    Args:
        task: Free text describing what is being "built".
        rng: Random source used to pick the payoff app.

    Returns:
        A scenario themed on the task.
    """
    rng = rng or random.Random()
    words = task_words(task)
    names = (words + [area for area in _GENERIC_AREAS if area not in words])[
        :_MAX_AREAS
    ]
    areas: dict[str, tuple[str, ...]] = {
        name: (f"{name}.ts", f"{name.capitalize()}.tsx", f"{name}.test.ts")
        for name in names
    }
    return Scenario(
        key="generic",
        task=task,
        keywords=(),
        areas=areas,
        vocab=(
            *words,
            "state",
            "props",
            "data",
            "config",
            "user",
            "result",
            "cache",
            "vibes",
        ),
        quips=(
            *_GENERIC_QUIPS,
            *(f"{word.capitalize()} is done." for word in words[:4]),
        ),
        finals=_GENERIC_FINALS,
        commands=(
            "npm test",
            "npm run build",
            "npx tsc --noEmit",
            "npm run lint -- --fix",
        ),
        app=rng.choice(("deploy", "stonks")),
    )


def pick_scenario(
    task: str | None,
    key: str | None = None,
    rng: random.Random | None = None,
) -> Scenario:
    """Choose a scenario by key, by keywords in the task, or at random.

    Args:
        task: What the user asked for, or ``None`` for a random scenario.
        key: A key from :data:`SCENARIOS`, or ``"generic"``, to force a pack.
        rng: Random source for any choices made.

    Returns:
        The chosen scenario, with its task replaced by ``task`` when given.
    """
    rng = rng or random.Random()
    if key == "generic":
        return generic_scenario(task or "build the thing", rng)
    if key is not None:
        return _with_task(SCENARIOS[key], task)
    if task is not None:
        lowered = task.lower()
        for scenario in SCENARIOS.values():
            if any(keyword in lowered for keyword in scenario.keywords):
                return _with_task(scenario, task)
        return generic_scenario(task, rng)
    return rng.choice(list(SCENARIOS.values()))


def _with_task(scenario: Scenario, task: str | None) -> Scenario:
    return replace(scenario, task=task) if task is not None else scenario
