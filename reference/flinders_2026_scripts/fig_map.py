import sys; sys.path.insert(0, '/tmp/claude-0/-home-claude/43abbab8-3734-5835-90ec-9f7d0bdcbf04/scratchpad/work')
from common import *; from style import *; from llama import load_llama
import glob
from fleet import NAMES
setup()
coast = load_coast('coast.txt')
g = load_llama().dropna(subset=['Lat','Lon']).loc['2026-09-26 09:55':'2026-09-26 21:46']
gs = g.resample('20s').first().dropna(subset=['Lat'])
routes = {}
for m, f in [('GFS','GFS_25_1800_25sep2026.csv'),('ECMWF','ECMWF_25_1800_25sep2026.csv'),('ACCESS','ACCESS_1_25_1800_25sep2026.csv')]:
    routes[m] = load_route('routes/'+f)[0]
yb = load_yb(sorted(glob.glob('yb_tracks_[abcd].txt')))
K = np.cos(np.radians(34.1))
def draw_base(ax, ext):
    lon0, lon1, lat0, lat1 = ext
    main = coast[0][1]
    poly = np.vstack([main, [[-33.70, 151.30], [-33.70, 150.6], [-34.70, 150.6], [-34.70, main[0,1]]]])
    ax.fill(poly[:,1], poly[:,0], color=LAND, zorder=0, lw=0)
    ax.plot(main[:,1], main[:,0], color=COAST, lw=0.7, zorder=1)
    for closed, pts in coast[1:]:
        ax.fill(pts[:,1], pts[:,0], color=LAND, zorder=1, lw=0); ax.plot(pts[:,1], pts[:,0], color=COAST, lw=0.6, zorder=1)
    ax.set_xlim(lon0, lon1); ax.set_ylim(lat0, lat1); ax.set_aspect(1/K)
    ax.grid(False); ax.set_xticks([]); ax.set_yticks([])
    for s in ax.spines.values(): s.set_visible(True); s.set_color(GRID)

fig = plt.figure(figsize=(6.6, 7.4))
axA = fig.add_axes([0.01, 0.01, 0.98, 0.93])
ext = (150.74, 151.42, -34.50, -33.80)
draw_base(axA, ext)
for m, r in routes.items():
    axA.plot(r.lon, r.lat, color=MODEL[m], lw=1.3, ls=(0,(4,2)), zorder=3, label=f'{m} optimal route (25 Sep 17:34)')
axA.plot(gs.Lon, gs.Lat, color=BLUE, lw=2.2, zorder=4, label='Llama II sailed track')
# marks
for nm, la, lo, dx, dy, ha in [('Sydney Heads', -33.832, 151.283, 0.012, 0.004, 'left'), ('Cape Banks', -34.0005, 151.257, 0.012, 0, 'left'),
                               ('Flinders Islet (FI)', -34.4583, 150.93, -0.012, -0.012, 'right'), ('Port Hacking', -34.07, 151.155, -0.012, 0, 'right'),
                               ('Wollongong', -34.425, 150.893, -0.006, 0.0, 'right')]:
    axA.plot(lo, la, 'o', ms=3, color=INK2, zorder=5)
    axA.text(lo+dx, la+dy, nm, fontsize=7.5, color=INK2, ha=ha, va='center', zorder=6)
# annotations on track
def ann(t, text, dx, dy, ax=axA):
    p = g.loc[t:].iloc[0]
    ax.annotate(text, (p.Lon, p.Lat), xytext=(p.Lon+dx, p.Lat+dy), fontsize=7.5, color=INK, zorder=7,
                arrowprops=dict(arrowstyle='-', color=INK2, lw=0.6), ha='left', va='center',
                bbox=dict(boxstyle='round,pad=0.25', fc=SURF, ec=GRID, lw=0.6))
ann('2026-09-26 13:05', '13:00–14:10 NNE 21–25 kt\n(routes expected 8–17 kt)', 0.07, 0.035)
ann('2026-09-26 17:06', '17:05 southerly hits\nS 30–36 kt by 17:30', 0.13, -0.02)
axA.set_title('Course, sailed track and pre-race optimal routes', pad=6)
axA.legend(loc='upper left', fontsize=7.2, handlelength=2.4, borderaxespad=0.6, facecolor=SURF, frameon=True, edgecolor=GRID)
# scale bar 5 nm
x0, y0 = 151.25, -34.47
axA.plot([x0, x0 + 5/60/K], [y0, y0], color=INK2, lw=1.5); axA.text(x0 + 2.5/60/K, y0+0.008, '5 nm', ha='center', fontsize=7, color=INK2)

fig.savefig('fig/fig1_map.png', dpi=200)
# panel B: Heads zoom 10:00-11:15
fig = plt.figure(figsize=(6.6, 3.6))
axB = fig.add_axes([0.005, 0.02, 0.44, 0.88])
extB = (151.235, 151.32, -33.885, -33.818)
draw_base(axB, extB)
h = g.loc['2026-09-26 10:00':'2026-09-26 11:15']
hole = g.loc['2026-09-26 10:30':'2026-09-26 10:57']
fleet_ids = {26: 'Calibre 12', 33: 'Kanreki', 40: 'Ragtime'}
axB.plot(h.Lon, h.Lat, color=BLUE, lw=2, zorder=4)
axB.plot(hole.Lon, hole.Lat, color=RED, lw=3.2, zorder=5, solid_capstyle='round')
p = hole.iloc[len(hole)//2]
axB.annotate('10:30–10:57 parked:\nTWS 2–4 kt, SOG ~1 kt\n≈ 20–25 min lost', (p.Lon, p.Lat), xytext=(151.239, -33.875), fontsize=7.5, color=INK,
             arrowprops=dict(arrowstyle='-', color=INK2, lw=0.6), bbox=dict(boxstyle='round,pad=0.25', fc=SURF, ec=GRID, lw=0.6))
for t, lab in [('2026-09-26 10:00:49', 'start 10:00:49'), ('2026-09-26 11:00', '11:00')]:
    q = g.loc[t:].iloc[0]; axB.plot(q.Lon, q.Lat, 'o', ms=4, color=BLUE, zorder=6, mec=SURF, mew=1)
    axB.text(q.Lon+0.003, q.Lat, lab, fontsize=7, color=INK2, va='center')
axB.set_title('A · Exiting the Heads (10:00–11:15)', fontsize=9, pad=4)
axB.plot([151.30, 151.30 + 1/60/K], [-33.882, -33.882], color=INK2, lw=1.5); axB.text(151.30 + 0.5/60/K, -33.879, '1 nm', ha='center', fontsize=7, color=INK2)

# panel C: FI zoom 15:30-17:40 with similar-rated boats
axC = fig.add_axes([0.46, 0.02, 0.535, 0.88])
extC = (150.885, 151.075, -34.48, -34.355)
draw_base(axC, extC)
w = g.loc['2026-09-26 15:30':'2026-09-26 17:40']
cols = {26: ORANGE, 33: AQUA, 40: YELLOW}
for bid, col in cols.items():
    tr = yb[(yb.id==bid)].set_index('time').sort_index().loc['2026-09-26 15:20':'2026-09-26 17:50']
    axC.plot(tr.lon, tr.lat, color=col, lw=1.4, marker='o', ms=2.5, zorder=3, label=fleet_ids[bid])
    q = tr.loc['2026-09-26 17:00':].iloc[0]
    axC.plot(q.lon, q.lat, 'o', ms=5, color=col, mec=INK, mew=0.7, zorder=6)
axC.plot(w.Lon, w.Lat, color=BLUE, lw=2, zorder=4, label='Llama II')
lull = g.loc['2026-09-26 16:33':'2026-09-26 16:46']
axC.plot(lull.Lon, lull.Lat, color=RED, lw=3.2, zorder=5, solid_capstyle='round')
q = g.loc['2026-09-26 17:00':].iloc[0]; axC.plot(q.Lon, q.Lat, 'o', ms=5, color=BLUE, mec=INK, mew=0.7, zorder=6)
r0 = g.loc['2026-09-26 16:00:12':].iloc[0]
axC.annotate('rounded 16:00\n(NNE 12 kt)', (r0.Lon, r0.Lat), xytext=(150.895, -34.475), fontsize=7.2, color=INK, arrowprops=dict(arrowstyle='-', color=INK2, lw=0.6), bbox=dict(boxstyle='round,pad=0.25', fc=SURF, ec=GRID, lw=0.6))
p = lull.iloc[len(lull)//2]
axC.annotate('16:33–16:46 lull,\nnear-stopped', (p.Lon, p.Lat), xytext=(151.005, -34.47), fontsize=7.2, color=INK, arrowprops=dict(arrowstyle='-', color=INK2, lw=0.6), bbox=dict(boxstyle='round,pad=0.25', fc=SURF, ec=GRID, lw=0.6))
axC.text(151.068, -34.362, '● = position at 17:00', fontsize=7, color=INK2, ha='right', va='top')
axC.set_title('B · Rounding Flinders Islet (15:30–17:40)', fontsize=9, pad=4)
axC.legend(loc='upper left', fontsize=7, frameon=True, facecolor=SURF, edgecolor=GRID)
fig.savefig('fig/fig2_zooms.png', dpi=200)
print('ok')
