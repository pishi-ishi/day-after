import sys; sys.path.insert(0, '/tmp/claude-0/-home-claude/43abbab8-3734-5835-90ec-9f7d0bdcbf04/scratchpad/work')
from common import *; from style import *; from fleet import NAMES, S_FI, TOTAL, CUM
import matplotlib.dates as mdates
setup()
# ---------- Fig 3: time vs plan ----------
S = pd.read_csv('splits.csv')
dist_at = {'LB': CUM[1], 'South Head': CUM[2], 'Dunbar': CUM[3], 'Ben Buckler': CUM[4], 'Cape Banks': CUM[5], 'FI S': CUM[7],
           'Cape Banks (ret)': CUM[9], 'Ben Buckler (ret)': CUM[10], 'Dunbar (ret)': CUM[11], 'South Head (ret)': CUM[12], 'Finish': CUM[13]}
S['x'] = S['mark'].map(dist_at)
fig, ax = plt.subplots(figsize=(6.6, 3.1))
for m in ['GFS','ECMWF','ACCESS']:
    ax.plot(S.x, S[m+'_d'], color=MODEL[m], marker=MARK[m], ms=5, lw=1.8, label=f'vs {m} route')
    ax.text(S.x.iloc[-1]+1, S[m+'_d'].iloc[-1], f'{m} {S[m+"_d"].iloc[-1]:+d} min', color=INK, fontsize=8, va='center')
ax.axhline(0, color=INK2, lw=0.8)
ax.axvline(S_FI, color=MUTED, lw=0.8); ax.text(S_FI+0.6, 74, 'Flinders Islet', fontsize=7.5, color=INK2, va='top')
ax.set_xlim(0, 99); ax.set_ylim(-75, 78)
ax.set_xticks([0, 10, 20, 30, 40, 50, 60, 70, 80, 88.06]); ax.set_xticklabels(['Start','10','20','30','40','50','60','70','80','Finish'])
ax.set_xlabel('distance along the 88 nm course (nm)'); ax.set_ylabel('minutes behind (+) / ahead (−) of route')
ax.annotate('Heads hole\n+20 min', (3.5, 23), xytext=(8, 52), fontsize=7.5, color=INK, arrowprops=dict(arrowstyle='-', color=INK2, lw=0.6))
ax.annotate('NNE stronger than forecast:\ncaught up on GFS/ACCESS', (40, -2), xytext=(13, -55), fontsize=7.5, color=INK, arrowprops=dict(arrowstyle='-', color=INK2, lw=0.6))
ax.annotate('rounded ~1 h before the change:\n65-min beat + lull', (50, 50), xytext=(52, 20), fontsize=7.5, color=INK)
ax.legend(loc='upper left', ncol=3, fontsize=7.5, bbox_to_anchor=(0, 1.13))
ax.set_title('Time against the 25 Sep evening optimal routes', pad=22)
fig.tight_layout(); fig.savefig('fig/fig3_vs_plan.png', dpi=200)

# ---------- Fig 4: forecast vs observed wind ----------
d = pd.read_pickle('llama_wind.pkl')
o = d.resample('10min').agg({'TWSg': 'mean'})
o['TWDg'] = d['TWDg'].resample('10min').apply(lambda s: circmean(s) if len(s) else np.nan)
o = o.loc['2026-09-26 10:00':'2026-09-26 21:40']
routes = {m: load_route('routes/'+f)[0] for m, f in [('GFS','GFS_25_1800_25sep2026.csv'),('ECMWF','ECMWF_25_1800_25sep2026.csv'),('ACCESS','ACCESS_1_25_1800_25sep2026.csv')]}
fig, (a1, a2) = plt.subplots(2, 1, figsize=(6.6, 5.2), sharex=True, gridspec_kw={'height_ratios': [1.15, 1]})
for ax in (a1, a2):
    ax.axvspan(pd.Timestamp('2026-09-26 16:40'), pd.Timestamp('2026-09-26 17:30'), color='#f0efec', zorder=0, lw=0)
    ax.axvline(pd.Timestamp('2026-09-26 16:00'), color=MUTED, lw=0.8); ax.axvline(pd.Timestamp('2026-09-26 17:05'), color=INK2, lw=0.9)
a1.plot(o.index, o.TWSg, color=BLUE, lw=2.4, label='Observed on Llama II (masthead, 10-min mean)', zorder=4)
for m, r in routes.items():
    a1.plot(r.time, r.Tws, color=MODEL[m], marker=MARK[m], ms=4, lw=1.4, label=f'{m} forecast along its route (10 m)', zorder=3)
a1.set_ylabel('true wind speed (kt)'); a1.set_ylim(0, 40)

a1.text(pd.Timestamp('2026-09-26 16:02'), 38.5, 'rounded FI 16:00', fontsize=7, color=INK2, ha='right', va='top')
a1.text(pd.Timestamp('2026-09-26 17:08'), 38.5, 'southerly 17:05', fontsize=7, color=INK2, ha='left', va='top')

# TWD: unwrap around 0 so N/NNE plots continuously: show as -180..180 centered at 0
def wrap(x): return ((np.asarray(x) + 110) % 360) - 110
a2.plot(o.index, wrap(o.TWDg), color=BLUE, lw=2.4, zorder=4)
for m, r in routes.items():
    a2.plot(r.time, wrap(r.twd), color=MODEL[m], marker=MARK[m], ms=4, lw=1.4, zorder=3)
a2.set_yticks([-90, -45, 0, 45, 90, 135, 180, 225]); a2.set_yticklabels(['W 270', 'NW 315', 'N 0', 'NE 45', 'E 90', 'SE 135', 'S 180', 'SW 225'])
a2.set_ylim(-110, 240); a2.set_ylabel('true wind direction (from)')
a2.text(pd.Timestamp('2026-09-26 17:33'), -100, 'shaded: race-morning forecast\nwindow for the change (16:40–17:30)', fontsize=6.8, color=INK2, va='bottom')
a2.xaxis.set_major_formatter(mdates.DateFormatter('%H:%M'))
a2.set_xlim(pd.Timestamp('2026-09-26 10:00'), pd.Timestamp('2026-09-26 21:50'))
fig.tight_layout(rect=(0, 0, 1, 0.86))
h, l = a1.get_legend_handles_labels()
fig.legend(h, l, loc='upper left', ncol=2, fontsize=7.4, bbox_to_anchor=(0.01, 0.935))
fig.suptitle('Forecast (25 Sep evening routes) vs observed wind', x=0.01, y=0.985, ha='left', fontsize=10, fontweight='bold', color=INK)
fig.savefig('fig/fig4_wind.png', dpi=200)

# ---------- Fig 5: rounding time vs corrected leg-2 ----------
R = pd.read_pickle('fleet_R2.pkl')
R['round_t'] = T0 + pd.to_timedelta(R.round_h*3600, unit='s')
fig, ax = plt.subplots(figsize=(6.6, 3.5))
ax.axvline(pd.Timestamp('2026-09-26 17:05'), color=INK2, lw=0.9); ax.text(pd.Timestamp('2026-09-26 17:08'), 8.1, 'southerly reached\nthe FI area ~17:05', fontsize=7.5, color=INK2, va='top')
others = R[~R.index.isin([50])]
ax.scatter(others.round_t, others.leg2_corr, s=28, color='#b9b7b0', edgecolor=SURF, linewidth=1, zorder=3, label='other IRC finishers')
cmp_ids = {26: 'Calibre 12', 33: 'Kanreki', 40: 'Ragtime', 2: "Wot's Next", 48: 'Disko Trooper (1st)', 45: 'Borderline (2nd)', 49: 'Blue Planet (3rd)', 11: 'Back 2 Black', 35: 'Ambition'}
offs = {26: (-8, -12), 33: (6, 6), 40: (6, 3), 2: (6, 4), 48: (-6, -12), 45: (6, -9), 49: (6, -4), 11: (6, 2), 35: (6, 0)}
for bid, lab in cmp_ids.items():
    r = R.loc[bid]; ax.scatter([r.round_t], [r.leg2_corr], s=30, color=INK2, zorder=4, edgecolor=SURF, linewidth=1)
    dx, dy = offs[bid]
    ax.annotate(lab, (r.round_t, r.leg2_corr), xytext=(dx, dy), textcoords='offset points', fontsize=7.2, color=INK, ha='left' if dx>0 else 'right')
r = R.loc[50]
ax.scatter([r.round_t], [r.leg2_corr], s=70, color=BLUE, zorder=5, edgecolor=SURF, linewidth=1.5, label='Llama II')
ax.annotate('Llama II', (r.round_t, r.leg2_corr), xytext=(-10, 8), textcoords='offset points', fontsize=8, fontweight='bold', color=INK, ha='right')
ax.set_ylabel('leg 2 corrected time (h)\n(FI → finish × TCC)'); ax.set_xlabel('time of rounding Flinders Islet')
ax.xaxis.set_major_formatter(mdates.DateFormatter('%H:%M'))
ax.set_ylim(4.4, 8.3)
ax.set_title('The later you rounded, the cheaper the trip home', pad=8)
ax.legend(loc='lower left', fontsize=7.5)
fig.tight_layout(); fig.savefig('fig/fig5_rounding.png', dpi=200)

# ---------- Fig 6: corrected-time gap along course ----------
C = pd.read_pickle('gate_corr.pkl')   # corrected hours per gate
C = C[[c for c in C.columns if abs(c-80.0) > 0.01 and abs(c-45.0) > 0.01]]  # drop gate 80 (projection artefact near Ben Buckler) and duplicate 45
gates = np.array(C.columns, float)
ends = []
sel = [(26, 'Calibre 12', ORANGE), (33, 'Kanreki', AQUA), (40, 'Ragtime', YELLOW), (2, "Wot's Next", MAGENTA), (48, 'Disko Trooper', GREEN), (49, 'Blue Planet', VIOLET)]
fig, ax = plt.subplots(figsize=(6.6, 3.4))
ax.axhline(0, color=BLUE, lw=2.2); ax.text(1, 3, 'Llama II', color=INK, fontsize=8, fontweight='bold')
ax.axvline(S_FI, color=MUTED, lw=0.8); ax.text(S_FI+0.6, 76, 'Flinders Islet', fontsize=7.5, color=INK2, va='top')
for bid, lab, col in sel:
    gap = (C.loc[bid] - C.loc[50]).values*60
    ax.plot(gates, gap, color=col, lw=1.6, marker='o', ms=3, label=lab)
    ends.append((gap[-1], lab))
ax.set_xlim(0, 106); ax.set_ylim(-125, 80)
ax.set_xticks([0, 10, 20, 30, 40, 50, 60, 70, 80, 88.02]); ax.set_xticklabels(['Start','10','20','30','40','50','60','70','80','Finish'])
ax.set_xlabel('distance along the course (nm)'); ax.set_ylabel('corrected-time gap (min)\n+ they are behind us · − ahead')
ends.sort()
ys = [e[0] for e in ends]
for i in range(1, len(ys)):
    if ys[i] - ys[i-1] < 9: ys[i] = ys[i-1] + 9
for (v, lab), y in zip(ends, ys):
    ax.text(gates[-1]+1.2, y, f'{lab} {v:+.0f}', fontsize=7.5, color=INK, va='center')
ax.set_title('Corrected-time gap to comparison boats as the race unfolded', pad=8)
ax.legend(loc='lower left', ncol=3, fontsize=7.2)
fig.tight_layout(); fig.savefig('fig/fig6_gaps.png', dpi=200)
print(pd.DataFrame({lab: ((C.loc[bid]-C.loc[50])*60).round(1).values for bid, lab, col in sel}, index=np.round(gates,1)).to_string())
