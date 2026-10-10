"""Fish the Millpond with a simulated angler and check the balance, headless.

    python dev/pond_bot.py            # catch rates, bite waits, and what greedy vs patient fishing does

The bot reacts like a person: it strikes 4-10 steps (~0.2-0.4 s) after the float goes under, lets go
a few steps after the fish starts thrashing, and takes up the line again once the run is over.
"""
import os
import sys
from collections import Counter

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
import terrarium as tr  # noqa: E402

RATE = tr.Millpond.tempo


class Bot:
    def __init__(self, env, rng, rest=0):
        self.e, self.r, self.rest = env, rng, rest   # rest: steps to sit on the jetty after each catch
        self.react = self.wait_from = self.idle_until = 0
        self.waits, self.outcomes, self.fought = [], Counter(), None

    def tick(self):
        e, r = self.e, self.r
        if e.line == "idle":
            if self.fought:                           # a fight just ended: how?
                caught = len(e.kept) > self.fought[1]
                self.outcomes[(self.fought[0], "landed" if caught else "lost")] += 1
                if caught:
                    self.idle_until = e.steps + self.rest
                self.fought = None
            if e.steps >= self.idle_until:
                x = r.randrange(26, 80)
                e.poke(x, r.randrange(e.SURF + 3, e.ground[x] - 2))
                e.release()
                self.wait_from = e.steps
            return
        if e.line == "wait":
            f = e.suitor
            if not e.bait:
                e.poke(40, 40)
                e.release()
            elif f is not None and f.mode == "take":
                if not self.react:
                    self.react = r.randint(4, 10)
                self.react -= 1
                if self.react <= 0:
                    self.waits.append(e.steps - self.wait_from)
                    st = e.stage(f)
                    e.poke(int(e.bx), int(e.by))
                    self.react = 0
                    if e.line == "fight":
                        self.fought = (f"{('fry', 'adult', 'old')[st]} {e.KINDS[f.kind][0]}", len(e.kept))
            return
        if e.line == "fight":
            danger = e.warn or e.surge or e.tension > .8
            if danger and e.holding:
                if r.random() < .2:                   # ~5 steps (0.2 s) to notice
                    e.release()
            elif not danger and not e.holding and r.random() < .25:
                e.poke(0, 0)


def balance(seed=1, steps=RATE * 60 * 40):
    e = tr.Millpond(seed)
    bot = Bot(e, e.rng.__class__(seed))
    for _ in range(steps):
        bot.tick()
        e.step()
    w = sorted(bot.waits)
    print(f"40 min of steady fishing (seed {seed}): kept {len(e.kept)}, lost {e.lost}, pond now {len(e.fish)} fish")
    if w:
        print(f"  wait for a bite: median {w[len(w) // 2] / RATE:.0f}s, 90th pct {w[len(w) * 9 // 10] / RATE:.0f}s")
    kinds = sorted({k for k, _ in bot.outcomes})
    for k in kinds:
        n, lo = bot.outcomes[(k, "landed")], bot.outcomes[(k, "lost")]
        print(f"  {k:12s} landed {n:3d}  lost {lo:3d}  ({n / max(1, n + lo):.0%})")


def pressure(rest, label, seed=2, minutes=60):
    e = tr.Millpond(seed)
    bot = Bot(e, e.rng.__class__(seed), rest)
    trace = []
    for s in range(RATE * 60 * minutes):
        bot.tick()
        e.step()
        if s % (RATE * 60 * 5) == 0:
            trace.append(len(e.fish))
    print(f"{label:28s} kept {len(e.kept):3d}   fish every 5 min: {trace}")


if __name__ == "__main__":
    for seed in (1, 7, 11):
        balance(seed)
    print()
    pressure(0, "greedy (recast at once)")
    pressure(RATE * 60 * 3, "patient (3 min rest per fish)")
    pressure(10 ** 9, "nobody fishing")
