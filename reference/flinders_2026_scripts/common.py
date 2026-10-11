import numpy as np, pandas as pd, re, io
VAR = 12.8  # deg E magnetic variation (checked against Expedition Brg°M: start->LB 029M = 041.8T)
T0 = pd.Timestamp('2026-09-26 10:00:00')          # start, local AEST
T0_EPOCH = 1790380800
R_NM = 3440.065
WORK = '/tmp/claude-0/-home-claude/43abbab8-3734-5835-90ec-9f7d0bdcbf04/scratchpad/work'

def ddm(s):
    m = re.match(r'\s*(\d+)\s+([\d.]+)([nsewNSEW])', s)
    d, mi, h = int(m.group(1)), float(m.group(2)), m.group(3).lower()
    v = d + mi / 60
    return -v if h in 'sw' else v

def hav(lat1, lon1, lat2, lon2):
    lat1, lon1, lat2, lon2 = map(np.radians, (lat1, lon1, lat2, lon2))
    a = np.sin((lat2-lat1)/2)**2 + np.cos(lat1)*np.cos(lat2)*np.sin((lon2-lon1)/2)**2
    return 2*R_NM*np.arcsin(np.sqrt(a))

def brg(lat1, lon1, lat2, lon2):
    lat1, lon1, lat2, lon2 = map(np.radians, (lat1, lon1, lat2, lon2))
    y = np.sin(lon2-lon1)*np.cos(lat2); x = np.cos(lat1)*np.sin(lat2)-np.sin(lat1)*np.cos(lat2)*np.cos(lon2-lon1)
    return (np.degrees(np.arctan2(y, x)) + 360) % 360

def circmean(a, w=None):
    a = np.radians(np.asarray(a, float)); m = ~np.isnan(a)
    if m.sum() == 0: return np.nan
    w = np.ones_like(a) if w is None else np.asarray(w, float)
    s = np.nansum(np.sin(a[m])*w[m]); c = np.nansum(np.cos(a[m])*w[m])
    return (np.degrees(np.arctan2(s, c)) + 360) % 360

def angdiff(a, b):
    return (np.asarray(a) - np.asarray(b) + 180) % 360 - 180

def load_route(path):
    txt = open(path, encoding='utf-8-sig').read()
    tab, meta = txt.split('\n,,,,', 1)
    df = pd.read_csv(io.StringIO(tab))
    df = df.rename(columns={'AUS Eastern Standard Time': 'time'})
    df['time'] = pd.to_datetime(df['time'], format='%d-%b-%Y %H:%M')
    df['lat'] = df['Latitude'].map(ddm); df['lon'] = df['Longitude'].map(ddm)
    df['twd'] = (df['Twd°M'] + VAR) % 360
    df['twa_num'] = pd.to_numeric(df['Twa'].astype(str).str.replace('(', '').str.replace(')', ''), errors='coerce')
    md = {}
    for line in meta.splitlines():
        p = line.split(',')
        if len(p) > 1 and p[0] and p[1]: md[p[0]] = p[1]
    return df, md

COURSE = [  # from Expedition routing tables (DDM -> decimal)
 ('Start', ddm('33 51.6390s'), ddm('151 14.8560e')),
 ('LB', ddm('33 50.0000s'), ddm('151 16.6200e')),
 ('South Head', ddm('33 49.8750s'), ddm('151 16.8450e')),
 ('Dunbar', ddm('33 50.8600s'), ddm('151 17.3880e')),
 ('Ben Buckler', ddm('33 53.4220s'), ddm('151 17.3940e')),
 ('Cape Banks', ddm('34 00.0320s'), ddm('151 15.4210e')),
 ('FI W', ddm('34 27.3524s'), ddm('150 55.6193e')),
 ('FI S', ddm('34 27.5129s'), ddm('150 55.7710e')),
 ('FI E', ddm('34 27.3833s'), ddm('150 55.9636e')),
 ('Cape Banks ', ddm('34 00.0320s'), ddm('151 15.4210e')),
 ('Ben Buckler ', ddm('33 53.4220s'), ddm('151 17.3940e')),
 ('Dunbar ', ddm('33 50.8600s'), ddm('151 17.3880e')),
 ('South Head ', ddm('33 49.8750s'), ddm('151 16.8450e')),
 ('Finish', ddm('33 50.4681s'), ddm('151 16.4630e')),
]
FI = (ddm('34 27.5s'), ddm('150 55.8e'))  # SI coordinate of Flinders Islet

def load_yb(paths):
    rows = []
    for p in paths:
        for line in open(p):
            line = line.strip()
            if not line: continue
            tid, fin, n, cs, data = line.split('|')
            nums = [int(x) for x in data.split(',')]
            t = la = lo = None
            for i in range(0, len(nums), 3):
                if t is None: t, la, lo = nums[i], nums[i+1], nums[i+2]
                else: t += nums[i]; la += nums[i+1]; lo += nums[i+2]
                rows.append((int(tid), int(fin), t, la/1e4, lo/1e4))
    df = pd.DataFrame(rows, columns=['id', 'fin_s', 't_s', 'lat', 'lon'])
    df = df.drop_duplicates(['id', 't_s'])
    df['time'] = T0 + pd.to_timedelta(df['t_s'], unit='s')
    return df

def load_coast(path):
    chains = []
    for line in open(path):
        line = line.strip()
        if not line: continue
        ci, closed, n, cs, data = line.split('|')
        nums = [int(x) for x in data.split(',')]
        la = lo = None; pts = []
        for i in range(0, len(nums), 2):
            if la is None: la, lo = nums[i], nums[i+1]
            else: la += nums[i]; lo += nums[i+1]
            pts.append((la/1e4, lo/1e4))
        chains.append((int(closed), np.array(pts)))
    return chains
