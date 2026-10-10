"""Drive the Terrarium window offscreen through every mode and save a screenshot of each.

    python dev/smoke.py   ->  dev/smoke_grid.png, dev/smoke_single.png, dev/smoke_mini.png
"""
import os
import sys
from types import SimpleNamespace

os.environ["SDL_VIDEODRIVER"] = "dummy"
HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, os.path.dirname(HERE))
import terrarium as tr  # noqa: E402

app = tr.App(SimpleNamespace(seed=3, mini=False))
pg = app.pg
for env in app.envs:                       # let each world mature before looking at it
    for _ in range(1500):
        env.step()


def shot(name, frames):
    app.run(frames=frames, keep_open=True)
    path = os.path.join(HERE, f"smoke_{name}.png")
    pg.image.save(app.win.get_surface(), path)
    print("saved", path, app.win.size)


for k, env in enumerate(app.envs):         # pokes shouldn't crash anywhere
    env.poke(10, 10)
    env.poke(tr.W - 1, tr.H - 1)
shot("grid", 90)
app.handle(pg.event.Event(pg.KEYDOWN, key=pg.K_TAB, mod=0, unicode=""))
app.handle(pg.event.Event(pg.KEYDOWN, key=pg.K_RIGHT, mod=0, unicode=""))
shot("single", 60)
app.handle(pg.event.Event(pg.KEYDOWN, key=pg.K_m, mod=0, unicode=""))
app.handle(pg.event.Event(pg.KEYDOWN, key=pg.K_RIGHT, mod=0, unicode=""))
shot("mini", 60)
for key in (pg.K_o, pg.K_t, pg.K_l, pg.K_n, pg.K_a, pg.K_SPACE, pg.K_r, pg.K_ESCAPE):
    app.handle(pg.event.Event(pg.KEYDOWN, key=key, mod=0, unicode=""))
app.run(frames=10, keep_open=True)
print("mode after Esc:", app.mode)
pg.quit()
