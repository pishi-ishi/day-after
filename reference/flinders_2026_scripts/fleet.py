import sys; sys.path.insert(0, '/tmp/claude-0/-home-claude/43abbab8-3734-5835-90ec-9f7d0bdcbf04/scratchpad/work')
from common import *
NAMES = pd.read_csv(WORK + '/fleet_merged.csv').set_index('id')['name'].to_dict()
RES = pd.read_csv(WORK + '/fleet_merged.csv').set_index('id')

# course polyline in local xy (nm)
LAT0, LON0 = -34.1, 151.1
KX = 60*np.cos(np.radians(LAT0))
def xy(lat, lon): return (np.asarray(lon)-LON0)*KX, (np.asarray(lat)-LAT0)*60
CX, CY = xy([c[1] for c in COURSE], [c[2] for c in COURSE])
SEG = np.hypot(np.diff(CX), np.diff(CY)); CUM = np.concatenate([[0], np.cumsum(SEG)])
TOTAL = CUM[-1]
I_FIE = 8  # index of 'FI E' in COURSE
S_FI = CUM[7]  # course distance at FI S (mid-rounding)

def project(px, py, seg_lo, seg_hi):
    best = (1e9, None)
    for i in range(seg_lo, seg_hi):
        ax, ay, bx, by = CX[i], CY[i], CX[i+1], CY[i+1]
        dx, dy = bx-ax, by-ay; L2 = dx*dx+dy*dy
        t = np.clip(((px-ax)*dx+(py-ay)*dy)/L2, 0, 1)
        qx, qy = ax+t*dx, ay+t*dy; dist = np.hypot(px-qx, py-qy)
        if dist < best[0]: best = (dist, CUM[i] + t*np.sqrt(L2))
    return best[1]

def progress(lat, lon, rounded):
    px, py = xy(lat, lon)
    if not rounded: return project(px, py, 0, 8)   # Start..FI E
    return project(px, py, 7, len(CX)-1)            # FI S..Finish

def rounding_time(tr):
    """tr: DataFrame time,lat,lon sorted. closest approach to FI with parabolic refinement on 3 points"""
    dd = hav(tr.lat.values, tr.lon.values, FI[0], FI[1]); i = int(np.argmin(dd))
    return tr.time.iloc[i], dd[i], i

def boat_progress(tr):
    tr = tr.sort_values('time').reset_index(drop=True)
    tround, dmin, iround = rounding_time(tr)
    s = [progress(la, lo, k > iround) for k, (la, lo) in enumerate(zip(tr.lat, tr.lon))]
    tr['s'] = s
    tr['s'] = np.maximum.accumulate(tr['s'].values)   # first-passage progress
    return tr, tround

def gate_times(tr, gates, fin_time):
    """time when progress first reaches each gate distance (linear interp); finish gate uses fin_time"""
    out = []
    t = (tr.time - T0).dt.total_seconds().values; s = tr.s.values
    for g in gates:
        if g >= TOTAL - 0.01: out.append((fin_time - T0).total_seconds()); continue
        j = np.where(s >= g)[0]
        if len(j) == 0: out.append(np.nan); continue
        j = j[0]
        if j == 0: out.append(t[0]); continue
        f = (g - s[j-1]) / (s[j] - s[j-1]) if s[j] > s[j-1] else 1.0
        out.append(t[j-1] + f*(t[j]-t[j-1]))
    return np.array(out)
