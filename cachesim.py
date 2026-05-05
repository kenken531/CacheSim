"""
CacheSim — Two-level CPU cache simulator
BUILDCORED ORCAS Day 23

Simulates L1 + L2 cache with LRU eviction.
Access results: L1 hit (green), L2 hit (yellow), miss (red).
"""

import time
import argparse
from collections import OrderedDict
from dataclasses import dataclass
from typing import Optional

from rich.console import Console
from rich.table import Table
from rich.panel import Panel
from rich.text import Text
from rich.live import Live
from rich.layout import Layout
from rich.rule import Rule
from rich import box
import numpy as np

# ── Config ────────────────────────────────────────────────────────────────────
L1_SIZE         = 8   # cache lines
L2_SIZE         = 16  # cache lines
CACHE_LINE_SIZE = 4   # words per line (spatial locality grouping)
DELAY           = 0.25

# ── Colours & symbols ─────────────────────────────────────────────────────────
COL_L1_HIT = "bold green"
COL_L2_HIT = "bold yellow"
COL_MISS   = "bold red"
COL_EVICT  = "dim cyan"
COL_EMPTY  = "dim white"

SYM_L1_HIT = "█"
SYM_L2_HIT = "▓"
SYM_MISS   = "░"
SYM_EMPTY  = "·"

console = Console()


# ── LRU Cache ─────────────────────────────────────────────────────────────────
class LRUCache:
    """
    LRU cache backed by OrderedDict.
    Order = recency: LRU at front (last=False), MRU at back (last=True).
    Dict value is None — positional order carries all LRU state.
    """

    def __init__(self, capacity: int, name: str):
        self.capacity = capacity
        self.name = name
        self.store: OrderedDict[int, None] = OrderedDict()

    def lookup(self, tag: int) -> bool:
        """Return True on hit; move tag to MRU position."""
        if tag in self.store:
            self.store.move_to_end(tag)
            return True
        return False

    def insert(self, tag: int) -> Optional[int]:
        """
        Insert a new tag (callers guarantee it is not already present via
        lookup() first). Evicts and returns the LRU tag if at capacity.
        """
        evicted: Optional[int] = None
        if len(self.store) >= self.capacity:
            evicted, _ = self.store.popitem(last=False)  # remove LRU
        self.store[tag] = None
        return evicted

    def contents(self) -> list:
        """Return tags MRU-first."""
        return list(reversed(self.store.keys()))


# ── Access result ──────────────────────────────────────────────────────────────
@dataclass
class AccessResult:
    address:    int
    tag:        int
    result:     str           # "L1_HIT" | "L2_HIT" | "MISS"
    evicted_l1: Optional[int]
    evicted_l2: Optional[int]


# ── Simulator ─────────────────────────────────────────────────────────────────
class CacheSim:
    def __init__(self, l1_size: int = L1_SIZE, l2_size: int = L2_SIZE,
                 line_size: int = CACHE_LINE_SIZE):
        self.l1        = LRUCache(l1_size, "L1")
        self.l2        = LRUCache(l2_size, "L2")
        self.line_size = line_size
        self.history:  list = []
        self.l1_hits   = 0
        self.l2_hits   = 0
        self.misses    = 0

    def _tag(self, address: int) -> int:
        return address // self.line_size

    def access(self, address: int) -> AccessResult:
        tag        = self._tag(address)
        evicted_l1 = None
        evicted_l2 = None

        if self.l1.lookup(tag):
            result = "L1_HIT"
            self.l1_hits += 1

        elif self.l2.lookup(tag):
            result = "L2_HIT"
            self.l2_hits += 1
            # Promote from L2 → L1 (L2 already marked MRU by lookup)
            evicted_l1 = self.l1.insert(tag)

        else:
            result = "MISS"
            self.misses += 1
            # RAM fetch → fill L2, then fill L1
            evicted_l2 = self.l2.insert(tag)
            evicted_l1 = self.l1.insert(tag)

        ar = AccessResult(address, tag, result, evicted_l1, evicted_l2)
        self.history.append(ar)
        return ar

    @property
    def total(self) -> int:
        return len(self.history)

    @property
    def l1_rate(self) -> float:
        return self.l1_hits / self.total * 100 if self.total else 0.0

    @property
    def l2_rate(self) -> float:
        return self.l2_hits / self.total * 100 if self.total else 0.0

    @property
    def miss_rate(self) -> float:
        return self.misses / self.total * 100 if self.total else 0.0


# ── Rich rendering ─────────────────────────────────────────────────────────────
GRID_COLS = 20

# Pre-built cell objects — reused every frame (no repeated allocation)
_CELL_L1  = Text(SYM_L1_HIT, style=COL_L1_HIT, end="")
_CELL_L2  = Text(SYM_L2_HIT, style=COL_L2_HIT, end="")
_CELL_RAM = Text(SYM_MISS,   style=COL_MISS,    end="")
_CELL_EMP = Text(SYM_EMPTY,  style=COL_EMPTY,   end="")
_CELL_MAP = {"L1_HIT": _CELL_L1, "L2_HIT": _CELL_L2, "MISS": _CELL_RAM}


def build_history_grid(history: list, max_cols: int = GRID_COLS) -> Table:
    """Color-coded access history grid."""
    t = Table(box=None, padding=(0, 0), show_header=False, show_edge=False)
    for _ in range(max_cols):
        t.add_column(width=2)

    if not history:
        t.add_row(*[_CELL_EMP] * max_cols)
        return t

    row = []
    for ar in history:
        row.append(_CELL_MAP[ar.result])
        if len(row) == max_cols:
            t.add_row(*row)
            row = []

    if row:
        row.extend([_CELL_EMP] * (max_cols - len(row)))
        t.add_row(*row)

    return t


def build_cache_state(cache: LRUCache, line_size: int,
                      highlight_tag: Optional[int] = None) -> Table:
    """Display current cache contents MRU-first; highlight the active tag."""
    t = Table(box=box.SIMPLE_HEAD, show_header=True,
              header_style="bold blue", min_width=26)
    t.add_column("MRU", style="dim", width=4)
    t.add_column("Tag (line)", width=12)
    t.add_column("Addresses",  width=14)

    contents = cache.contents()
    slots = contents + [None] * (cache.capacity - len(contents))

    for i, tag in enumerate(slots):
        if tag is None:
            t.add_row(str(i), "[dim]—[/dim]", "[dim]empty[/dim]")
        else:
            lo = tag * line_size
            hi = lo + line_size - 1
            if tag == highlight_tag:
                t.add_row(str(i),
                          f"[bold green]{tag}[/bold green]",
                          f"[bold green]{lo}–{hi}[/bold green]")
            else:
                t.add_row(str(i), str(tag), f"{lo}–{hi}")

    return t


def build_stats_panel(sim: CacheSim, last: Optional[AccessResult]) -> Panel:
    t = Table(box=None, show_header=False, padding=(0, 2))
    t.add_column(width=18)
    t.add_column(width=14)
    t.add_column(width=14)
    t.add_column(width=14)

    t.add_row(
        Text("Total accesses", style="bold"),
        Text("L1 hits",        style=COL_L1_HIT),
        Text("L2 hits",        style=COL_L2_HIT),
        Text("RAM misses",     style=COL_MISS),
    )
    t.add_row(
        Text(str(sim.total),   style="bold white"),
        Text(f"{sim.l1_hits}  ({sim.l1_rate:.1f}%)", style=COL_L1_HIT),
        Text(f"{sim.l2_hits}  ({sim.l2_rate:.1f}%)", style=COL_L2_HIT),
        Text(f"{sim.misses}  ({sim.miss_rate:.1f}%)", style=COL_MISS),
    )

    subtitle: Optional[Text] = None
    if last:
        sym_str = {
            "L1_HIT": f"[{COL_L1_HIT}]{SYM_L1_HIT} L1 HIT[/]",
            "L2_HIT": f"[{COL_L2_HIT}]{SYM_L2_HIT} L2 HIT[/]",
            "MISS":   f"[{COL_MISS}]{SYM_MISS} RAM MISS[/]",
        }[last.result]
        ev = ""
        if last.evicted_l1 is not None:
            ev += f"  [{COL_EVICT}]evicted L1:{last.evicted_l1}[/]"
        if last.evicted_l2 is not None:
            ev += f"  [{COL_EVICT}]evicted L2:{last.evicted_l2}[/]"
        subtitle = Text.from_markup(
            f"  addr [bold]{last.address}[/bold] → tag {last.tag} → {sym_str}{ev}"
        )

    return Panel(
        t,
        title=(
            f"[bold white]◉ CacheSim  "
            f"[dim]L1={sim.l1.capacity} lines | L2={sim.l2.capacity} lines"
            f" | line={sim.line_size} words[/dim]"
        ),
        subtitle=subtitle,
        border_style="blue",
    )


def make_layout() -> Layout:
    """Create the reusable layout skeleton once."""
    layout = Layout()
    layout.split_column(
        Layout(name="stats",  size=7),
        Layout(name="middle"),
        Layout(name="grid",   size=10),
    )
    layout["middle"].split_row(
        Layout(name="l1_state"),
        Layout(name="l2_state"),
    )
    return layout


def update_layout(layout: Layout, sim: CacheSim,
                  last: Optional[AccessResult]) -> Layout:
    """Fill the layout with fresh data in-place — avoids per-frame allocation."""
    ht = last.tag if last else None

    layout["stats"].update(build_stats_panel(sim, last))
    layout["l1_state"].update(
        Panel(build_cache_state(sim.l1, sim.line_size, ht),
              title="[bold green]L1 Cache[/bold green]",
              border_style="green")
    )
    layout["l2_state"].update(
        Panel(build_cache_state(sim.l2, sim.line_size, ht),
              title="[bold yellow]L2 Cache[/bold yellow]",
              border_style="yellow")
    )
    layout["grid"].update(
        Panel(
            build_history_grid(sim.history),
            title=(
                f"[bold white]Access History  "
                f"[dim]{SYM_L1_HIT}=L1  {SYM_L2_HIT}=L2  {SYM_MISS}=miss[/dim]"
            ),
            border_style="dim blue",
        )
    )
    return layout


# ── Pattern generators ─────────────────────────────────────────────────────────
def parse_pattern(raw: str) -> list:
    tokens = raw.replace(",", " ").split()
    return [int(t) for t in tokens]


def generate_pattern(name: str, n: int = 40, l1_size: int = L1_SIZE,
                     line_size: int = CACHE_LINE_SIZE) -> list:
    """
    All patterns use line-aligned addresses (multiples of line_size) so that
    each address maps to a *distinct* cache tag.  Using raw integers like 0,1,2
    would collapse many addresses to the same tag (e.g. 0–3 all → tag 0).
    """
    rng = np.random.default_rng(42)
    ls  = line_size  # shorthand

    if name == "sequential":
        # One access per cache line, sequential tags 0..n-1
        return [i * ls for i in range(n)]

    elif name == "random":
        # 64 distinct cache lines, random order
        tags = rng.integers(0, 64, size=n)
        return [int(t) * ls for t in tags]

    elif name == "stride":
        # Access every 4th cache line (stride-4 in tag space)
        return [(i * 4 * ls) % (64 * ls) for i in range(n)]

    elif name == "temporal":
        # Tight 4-line working set — near-100% L1 hit rate after warmup
        hot = [i * ls for i in range(4)]
        return [hot[i % len(hot)] for i in range(n)]

    elif name == "thrash":
        # Working set = L1+2 distinct cache lines.
        # Larger than L1 → L1 evicts on every cycle.
        # Fits in L2 → L2 absorbs after warmup, showing L2 hits.
        ws = [i * ls for i in range(l1_size + 2)]
        return [ws[i % len(ws)] for i in range(n)]

    elif name == "mixed":
        # Hot 4-line set interleaved with a cold 8-line scan
        hot  = [i * ls for i in range(4)]
        cold = [i * ls for i in range(20, 28)]
        seq  = hot + [hot[0], hot[1], hot[2], hot[0], hot[1]] + cold
        return (seq * 3)[:n]

    else:
        raise ValueError(f"Unknown pattern: {name!r}")


# ── Main ───────────────────────────────────────────────────────────────────────
PRESETS = ["sequential", "random", "stride", "temporal", "thrash", "mixed"]


def interactive_menu(l1_size: int = L1_SIZE) -> tuple:
    console.print(Rule("[bold blue]CacheSim — Two-Level CPU Cache Simulator[/bold blue]"))
    console.print()
    console.print("[bold]Choose access pattern:[/bold]")
    for i, name in enumerate(PRESETS, 1):
        console.print(f"  [{i}] {name}")
    console.print("  [c] custom  (enter addresses manually)")
    console.print()

    choice = console.input("[bold cyan]> [/bold cyan]").strip().lower()

    if choice == "c":
        raw       = console.input("[bold cyan]Addresses (space/comma separated): [/bold cyan]")
        addresses = parse_pattern(raw)
    elif choice.isdigit() and 1 <= int(choice) <= len(PRESETS):
        addresses = generate_pattern(PRESETS[int(choice) - 1], l1_size=l1_size)
    else:
        console.print("[red]Invalid choice — using 'mixed'[/red]")
        addresses = generate_pattern("mixed", l1_size=l1_size)

    raw_delay = console.input(
        "\n[bold cyan]Delay between accesses in seconds (0=instant, default 0.2): [/bold cyan]"
    ).strip()
    try:
        delay = float(raw_delay) if raw_delay else 0.2
    except ValueError:
        console.print("[red]Invalid delay — using 0.2 s[/red]")
        delay = 0.2

    return addresses, delay


def run(addresses: list, delay: float = DELAY,
        l1_size: int = L1_SIZE, l2_size: int = L2_SIZE) -> None:
    sim = CacheSim(l1_size, l2_size)

    console.print()
    console.print(
        Panel(
            f"[bold]Simulating [cyan]{len(addresses)}[/cyan] memory accesses[/bold]\n"
            f"L1: [green]{l1_size}[/green] lines  |  "
            f"L2: [yellow]{l2_size}[/yellow] lines  |  "
            f"Line: [blue]{sim.line_size}[/blue] words",
            title="[bold blue]Starting CacheSim[/bold blue]",
            border_style="blue",
        )
    )
    time.sleep(0.6)

    layout = make_layout()
    last: Optional[AccessResult] = None

    with Live(update_layout(layout, sim, last), refresh_per_second=12,
              screen=True, console=console) as live:
        for addr in addresses:
            last = sim.access(addr)
            live.update(update_layout(layout, sim, last))
            if delay > 0:
                time.sleep(delay)

    # ── Final summary ──────────────────────────────────────────────────────────
    console.print()
    console.print(Rule("[bold green]Simulation Complete[/bold green]"))
    console.print()

    summary = Table(title="Final Hit Rates", box=box.ROUNDED,
                    border_style="green", header_style="bold white")
    summary.add_column("Level",  style="bold")
    summary.add_column("Hits",   justify="right")
    summary.add_column("Rate",   justify="right")

    summary.add_row("L1 (fastest)",
                    f"[green]{sim.l1_hits}[/green]",
                    f"[green]{sim.l1_rate:.1f}%[/green]")
    summary.add_row("L2 (slower)",
                    f"[yellow]{sim.l2_hits}[/yellow]",
                    f"[yellow]{sim.l2_rate:.1f}%[/yellow]")
    summary.add_row("RAM (miss)",
                    f"[red]{sim.misses}[/red]",
                    f"[red]{sim.miss_rate:.1f}%[/red]")
    summary.add_row("[dim]Total[/dim]",
                    f"[bold]{sim.total}[/bold]", "100%")
    console.print(summary)
    console.print()

    if sim.l1_rate > 70:
        console.print("[bold green]✔  Excellent locality — cache-friendly access pattern.[/bold green]")
    elif sim.l1_rate + sim.l2_rate > 70:
        console.print("[bold yellow]⚠  Moderate locality — L2 absorbing load; tighten working set.[/bold yellow]")
    else:
        console.print("[bold red]✘  Poor locality — high RAM miss rate; cache thrashing detected.[/bold red]")
    console.print()


def main() -> None:
    parser = argparse.ArgumentParser(description="CacheSim — Two-level CPU cache simulator")
    parser.add_argument("--pattern",   choices=PRESETS)
    parser.add_argument("--addresses", type=str,
                        help="Comma/space-separated address sequence")
    parser.add_argument("--delay",     type=float, default=DELAY,
                        help=f"Seconds between accesses (default {DELAY})")
    parser.add_argument("--l1-size",   type=int,   default=L1_SIZE,
                        help=f"L1 cache lines (default {L1_SIZE})")
    parser.add_argument("--l2-size",   type=int,   default=L2_SIZE,
                        help=f"L2 cache lines (default {L2_SIZE})")
    parser.add_argument("--count",     type=int,   default=40,
                        help="Access count for preset patterns (default 40)")
    args = parser.parse_args()

    if args.addresses:
        addresses = parse_pattern(args.addresses)
    elif args.pattern:
        addresses = generate_pattern(args.pattern, args.count, l1_size=args.l1_size)
    else:
        addresses, args.delay = interactive_menu(l1_size=args.l1_size)

    run(addresses, args.delay, args.l1_size, args.l2_size)


if __name__ == "__main__":
    main()