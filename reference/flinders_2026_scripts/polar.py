import numpy as np
def load_polar(path):
    rows = []
    for line in open(path):
        if line.startswith('!') or not line.strip(): continue
        v = [float(x) for x in line.split()]
        tws = v[0]; pairs = [(v[i], v[i+1]) for i in range(1, len(v), 2)]
        rows.append((tws, pairs))
    return rows
def target(polar, tws, twa):
    if not np.isfinite(tws) or not np.isfinite(twa): return np.nan
    twa = abs(twa)
    def row_bsp(pairs, a):
        A = np.array([p[0] for p in pairs]); B = np.array([p[1] for p in pairs])
        o = np.argsort(A); A, B = A[o], B[o]
        return np.interp(a, A, B)
    T = np.array([r[0] for r in polar])
    if tws <= T[0]:
        return row_bsp(polar[0][1], twa) * tws / T[0]
    if tws >= T[-1]:
        return row_bsp(polar[-1][1], twa)
    j = np.searchsorted(T, tws) - 1
    f = (tws - T[j]) / (T[j+1] - T[j])
    return (1-f)*row_bsp(polar[j][1], twa) + f*row_bsp(polar[j+1][1], twa)
def upwind_opt(polar, tws):
    T = np.array([r[0] for r in polar]); A = np.array([r[1][1][0] for r in polar]); B = np.array([r[1][1][1] for r in polar])
    return np.interp(tws, T, A), np.interp(tws, T, B)
