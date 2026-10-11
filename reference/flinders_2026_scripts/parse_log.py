import sys, csv, collections, pandas as pd, numpy as np
path = sys.argv[1]
out = sys.argv[2]
with open(path, newline='') as f:
    names = f.readline().strip().split(',')
    ids = f.readline().strip().split(',')
    ver = f.readline().strip()
    # map id -> name
    idmap = {}
    for n, i in zip(names[1:], ids[1:]):
        idmap[int(i)] = n
    print('version', ver, 'nchan', len(idmap))
    rows = []
    counts = collections.Counter()
    for line in f:
        p = line.strip().split(',')
        if len(p) < 2 or p[0].startswith('!'):
            continue
        rec = {'boat': int(p[0]), 'Utc': float(p[1])}
        for k in range(2, len(p) - 1, 2):
            try:
                cid = int(p[k]); v = float(p[k + 1])
            except ValueError:
                continue
            nm = idmap.get(cid, f'ch{cid}')
            rec[nm] = v
            counts[nm] += 1
        rows.append(rec)
df = pd.DataFrame(rows)
df['time_utc'] = pd.to_datetime('1899-12-30') + pd.to_timedelta(df['Utc'], unit='D')
df['time_local'] = df['time_utc'] + pd.Timedelta(hours=10)
df.to_pickle(out)
print('rows', len(df), 'boats', df['boat'].unique())
print('time range local', df['time_local'].min(), df['time_local'].max())
print('channel counts:')
for k, v in counts.most_common():
    print(f'  {k}: {v}')
