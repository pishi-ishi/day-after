import sys; sys.path.insert(0, '/tmp/claude-0/-home-claude/43abbab8-3734-5835-90ec-9f7d0bdcbf04/scratchpad/work')
from common import *
def load_llama():
    df = pd.read_pickle(WORK + '/log.pkl').set_index('time_local').sort_index()
    df = df[~df.index.duplicated()]
    keep = ['BSP','SOG','COG','HDG','TWS','TWD','TWA','AWS','AWA','Lat','Lon','Depth','SeaTemp','RPM 1','TmToGun']
    d = df[keep].copy()
    d = d.loc['2026-09-26 08:50':'2026-09-26 21:46']
    # positions present on the GPS rows; forward-fill wind channels across short gaps (<=3 s)
    d = d.resample('1s').mean() if False else d
    return d

K_BSP = 1.257
def true_wind(aws, awa, spd, hdg=None, cog=None):
    """Return (tws, twa) relative to boat heading frame. awa deg (+stbd), spd along heading (water) or
    ground velocity given separately via cog (then returns tws/twd over ground)."""
    awa_r = np.radians(awa)
    # apparent wind velocity (air rel boat) in boat frame x fwd, y stbd: wind FROM awa => velocity = -aws*(cos, sin)
    ax, ay = -aws*np.cos(awa_r), -aws*np.sin(awa_r)
    if cog is None:
        tx, ty = ax + spd, ay
    else:
        rel = np.radians(cog - hdg)
        tx, ty = ax + spd*np.cos(rel), ay + spd*np.sin(rel)
    tws = np.hypot(tx, ty)
    twa = (np.degrees(np.arctan2(-ty, -tx)) + 180) % 360 - 180
    return tws, twa
