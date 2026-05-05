# CacheSim 🧠

> **BUILDCORED ORCAS — Day 23 (Advanced)**  
> Simulate a two-level CPU cache (L1 + L2) with real-time rich TUI visualization.

---

## Description

CacheSim models the L1 → L2 → RAM memory hierarchy found in every modern CPU (and ARM Cortex-M MCUs). You feed it a sequence of memory addresses. For each access it classifies the result as an **L1 hit**, **L2 hit**, or **RAM miss**, enforces **LRU eviction**, and shows a live color-coded grid of every access alongside the current state of both caches.

Cache misses on a Cortex-M MCU cost 10–100× more cycles than a hit. Understanding *why* your access pattern thrashes or warms the cache is the difference between firmware that runs at full speed and firmware that stalls.

---

## How It Works

- **Cache lines**: addresses are grouped into lines of `CACHE_LINE_SIZE` words (default 4), modelling spatial locality — nearby addresses share a cache line.
- **L1 lookup**: if the tag is in L1 → **L1 hit** (fastest path, 1–4 cycle cost).
- **L2 promotion**: L1 miss → check L2. If found → **L2 hit**; promote line to L1 (may evict LRU L1 line).
- **RAM fetch**: L2 miss → **RAM miss**; line loaded into both L2 and L1 (may evict LRU lines from each).
- **LRU eviction**: each cache uses an `OrderedDict`-based LRU policy. The least-recently-used line is evicted when capacity is full.
- **Hit rates**: computed live after every access — `hits / total`.

### Grid colours

| Symbol | Meaning |
|--------|---------|
| `█` green | L1 hit — served from L1 |
| `▓` yellow | L2 hit — served from L2, promoted to L1 |
| `░` red | RAM miss — fetched from main memory |
| `·` dim | not yet accessed |

---

## Requirements

- Python 3.11+
- Windows (tested on Windows 10/11)
- Terminal with 24-bit colour (Windows Terminal recommended)

## Python Packages

```
pip install -r requirements.txt
```

```
rich>=13.7.0
numpy>=1.26.0
```

---

## Setup

```bash
git clone <repo>
cd CacheSim
pip install -r requirements.txt
```

---

## Usage

### Interactive menu (recommended for demo)
```bash
python cache_sim.py
```
Choose a preset pattern or enter your own addresses. Set replay delay (0.2 s default).

### Command-line presets
```bash
python cache_sim.py --pattern temporal --count 50 --delay 0.15
python cache_sim.py --pattern thrash   --delay 0.2
python cache_sim.py --pattern random   --count 60 --delay 0.1
```

### Custom address sequence
```bash
python cache_sim.py --addresses "0 1 2 0 1 3 0 4 5 6 0 1"
python cache_sim.py --addresses "0,4,8,12,16,0,4,8"
```

### Tune cache sizes
```bash
python cache_sim.py --pattern thrash --l1-size 4 --l2-size 8
python cache_sim.py --pattern random --l1-size 16 --l2-size 32
```

### Available presets

| Pattern | What it demonstrates |
|---------|----------------------|
| `temporal` | Tiny hot set → near-100% L1 hit rate |
| `mixed` | Blend of hot and cold accesses |
| `thrash` | Working set > L1 → L1 thrashes, L2 absorbs |
| `stride` | Stride-4 access → some spatial locality |
| `sequential` | Linear scan → cold start misses then L2 hits |
| `random` | No locality → mostly misses |

---

## Common Fixes

| Symptom | Fix |
|---------|-----|
| All misses every run | `--l1-size` / `--l2-size` too small for your address range; increase them or reduce the address range |
| Eviction logic wrong | Check `LRUCache.insert` — `popitem(last=False)` removes the LRU (front); `last=True` would remove MRU — don't flip it |
| `rich` grid flickers | Reduce `--count` or increase `--delay`; `rich.Live` is stable above ~0.1 s |
| All green after warmup | Expected! `temporal` pattern is *designed* to show perfect locality |
| Screen too small | Resize terminal to ≥ 90 columns × 35 rows; `rich` layout requires space |

---

## Hardware Concept

### Cache hierarchy on ARM Cortex-M

```
Register file  — 1 cycle
L1 I/D cache   — 1–4 cycles    ← CacheSim L1
L2 cache       — 4–12 cycles   ← CacheSim L2
Flash / SRAM   — 10–100 cycles ← CacheSim "RAM miss"
```

**Temporal locality**: re-using the same addresses frequently → L1 stays warm.  
**Spatial locality**: accessing nearby addresses → same cache line → one miss loads multiple useful addresses.  
**LRU eviction**: the cache line that has not been used for the longest time gets replaced — keeps the working set hot.

Thrashing occurs when your working set is *slightly* larger than your cache — every access evicts a line you'll need again immediately. The `thrash` preset demonstrates this perfectly.

---

## v2.0 Bridge

In v2.0 you'll instrument a real ARM Cortex-M0+ (RP2040 or STM32) with ITM trace or cycle-counter sampling to capture actual memory access addresses. Feed that trace into this simulator and compare predicted vs. measured hit rates — validating the model against silicon.

---

## Credits

Built by **Javohir** · BUILDCORED ORCAS Day 23  
Challenge spec: two-level cache sim with LRU, rich TUI, real-time hit rate display.
