# Terrarium

A little shelf of seven living pixel environments: a digital desk garden for a side screen.

Each environment is a 96×64 world with its own physics and its own mood. Each one runs a loop where growth and decay
pull against each other, so it never fills up and never dies out. It just keeps moving.

![shelf](dev/smoke_grid.png)

## Run

```powershell
cd D:\playground\claude\terrarium
..\scribblefall\.venv\Scripts\python.exe terrarium.py          # the shelf (4×2)
..\scribblefall\.venv\Scripts\python.exe terrarium.py --mini   # frameless, always-on-top, bottom-right corner
..\scribblefall\.venv\Scripts\python.exe terrarium.py --headless 3000   # vital signs, no window
```

(Reuses the Scribblefall venv; anywhere else: `pip install pygame-ce`.)

## Portable build (USB stick)

```powershell
powershell -ExecutionPolicy Bypass -File dev\build_portable.ps1
```

This makes `dist\Terrarium\` (about 34 MB) and `dist\Terrarium-portable.zip` (about 14 MB). Copy the folder to a stick and run
`Terrarium.exe`, or `Terrarium mini.cmd` for the corner widget. The other PC needs no Python and no install.
It's a PyInstaller *folder* build on purpose: a one-file exe would unpack itself into the host's `%TEMP%` on every
launch, while the folder runs straight off the stick. Screenshots go to `shots\` next to the exe, so they're on the stick too.
Only the build machine needs [uv](https://docs.astral.sh/uv/).

## The environments

| | mood | the loop |
|---|---|---|
| **Tidepool** | calm | kelp grows toward the light, ages and rots → rot sinks as detritus → composts the sand → rich sand sprouts new kelp (only where it isn't crowded). Fish graze the rot; bubbles rise from rich sand and leaves; caustic light shimmers near the surface. |
| **Ember Forest** | restless | trees spread from neighbours and darken as they age → lightning and drifting embers start fires that race downwind (older trees burn more readily) → ash crumbles back to soil. Population swings between ~1k and ~4k trees: boom, burn, regrow. |
| **Crystal Garden** | focused | Packard snowflakes on a hex lattice: an empty cell freezes if its count of frozen neighbours is in this bloom's rule. Each bloom picks a rule, colour family and seed layout, grows, holds, then melts from the tips or from the heart, and a new one begins. |
| **Pulse** | hypnotic | a Greenberg–Hastings excitable medium: cells fire, then rest. Propagation slowly drifts between perfect (crisp geometric diamonds) and lossy (fronts break and curl into self-sustaining spirals). The colours drift through the hue wheel over minutes. |
| **Firefly Meadow** | dreamy | pulse-coupled oscillators: every flash nudges nearby fireflies closer to flashing. Coupling waxes and wanes, so the meadow drifts from scattered twinkling to waves of light rolling across the grass → fireflies that flash together lay glowing eggs in the grass → eggs hatch, old fireflies fade. Stars twinkle, grass sways under the moon. |
| **Millpond** | patient | a pond seen from the bank at the end of a jetty, with a day that turns to night. Fish (the three-pixel kind: roach, perch, and the odd carp) hatch from eggs laid on the weed, grow from 2-px fry to adults to 4-px old lunkers, and die of age, sinking into the mud to feed the weed. Adults spawn only while the pond has room and only if two of their kind are left. They rise for midges at dusk, leaving rings on the surface. **You can fish it:** see below. |
| **Slime Mold** | curious | Physarum: hundreds of agents sniff the scent ahead, turn toward the strongest and leave scent behind, knitting a vein network between oat flakes → feeding makes it grow → when the oats run out it starves and pulls back → new oats fall. The veins slowly breathe (shuttle streaming). |

## Controls

| | |
|---|---|
| click | poke the world: feed the pool, start a fire / plant trees, seed a crystal, drop a pulse, release fireflies, drop an oat flake, cast a line |
| double-click a tile · Tab | open it · back to the shelf |
| ← → / wheel | switch environment (single + mini) |
| M | mini mode (drag to move, right-click to poke) |
| T · O | always-on-top · opacity (100 / 80 / 55%) in mini mode |
| A | auto-cycle environments every 90 s |
| L · N | scanlines + vignette · labels |
| R · Space · S | reseed · pause · screenshot to `shots/` |

## Fishing the Millpond

1. **Cast:** click the water. Where you click is where the float lands, and how deep you click is how deep the bait
   hangs. Roach feed high, perch in the middle, carp near the bottom. The plop scares fish close by, so don't cast on
   top of them. Watch for rise rings to see where they are. Fish bite best at dusk and dawn.
2. **Wait:** the float twitches as a fish nibbles. Strike now and you'll spook it. When the float goes **right under**,
   you have under a second to click. Too slow and the bait's gone.
3. **Fight:** hold the mouse button to reel in. The gauge top-right is line tension. When the fish shakes and bolts
   (*"it's about to run!"*), let go, or the line snaps. Leave the line slack too long and it throws the hook. Big old
   fish give less warning and pull harder. You won't land them all.
4. Fry are slipped back. Click the jetty to reel in and rest.

Every fish you keep is one fewer to spawn. Landing one also puts the others off for a while. Fish non-stop and the pond
runs down to a handful, and bites dry up. Take a break between catches and it stays full. If a kind is fished down to
its last fish it can't spawn, and the pond waits for a stray to swim in from the stream. `dev/pond_bot.py` measures
all this with a simulated angler (one hour, same pond):

| | fish kept | fish in the pond, every 5 min |
|---|---|---|
| greedy, recasts straight away | 25 to 29 | 11 → 6 → 2 → 1 … 1 |
| patient, 3 min rest per fish | 12 to 17 | 11 → 10 → 13 → 15 … 10 |
| nobody fishing | | 11 → 13 → 18 → 16 … 14 |

## How it's put together

- Every environment subclasses `Env`: it owns a 96×64 `bytearray` of **palette indices** and a 256-colour palette.
  The renderer hands that buffer straight to an 8-bit surface, so there's no per-pixel Python in the draw path.
- Animation is mostly **palette work**: fire flicker, caustics, crystal colour flowing outward and hue drift all
  change a few palette entries per frame, not pixels. That's how 8-bit-era games did it too.
- Bloom: each env lists its glowing palette indices; a glow-only copy is shrunk to ¼ and stretched back with
  additive blending.
- Each env runs at its own `tempo` (steps/sec): Crystal breathes at 14, the forest at 24. Together they use well
  under 10% of one CPU core.
- Slime Mold blurs its scent map without a per-pixel loop: the bytes are packed into 16-bit lanes of one big
  Python integer, and shifted copies of it are added together.
- Adding an environment is one class: `step()`, `animate(t)`, optionally `poke()`, `release()` (the mouse button was
  let go), `frame()` (for sprites like fish and embers), `status()` (lines of text for the tile) and `vitals()` (for
  the headless check). Then add it to `ENVIRONMENTS`.
