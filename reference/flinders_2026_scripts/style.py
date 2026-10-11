import matplotlib
matplotlib.use('Agg')
import matplotlib.pyplot as plt
SURF = '#fcfcfb'; INK = '#0b0b0b'; INK2 = '#52514e'; MUTED = '#8a8984'; GRID = '#e7e6e1'
LAND = '#ebe9e3'; COAST = '#b4b1a8'
BLUE = '#2a78d6'; ORANGE = '#eb6834'; AQUA = '#1baf7a'; YELLOW = '#eda100'; MAGENTA = '#e87ba4'; GREEN = '#008300'; VIOLET = '#6250d6'; RED = '#e34948'
MODEL = {'GFS': ORANGE, 'ECMWF': AQUA, 'ACCESS': YELLOW}
MARK = {'GFS': 'o', 'ECMWF': 's', 'ACCESS': '^'}
def setup():
    plt.rcParams.update({'figure.facecolor': SURF, 'axes.facecolor': SURF, 'savefig.facecolor': SURF,
        'font.family': 'DejaVu Sans', 'font.size': 9, 'axes.edgecolor': GRID, 'axes.labelcolor': INK2,
        'xtick.color': INK2, 'ytick.color': INK2, 'axes.grid': True, 'grid.color': GRID, 'grid.linewidth': 0.6,
        'axes.spines.top': False, 'axes.spines.right': False, 'axes.titlesize': 10, 'axes.titleweight': 'bold',
        'axes.titlecolor': INK, 'axes.titlelocation': 'left', 'legend.frameon': False, 'legend.fontsize': 8,
        'lines.linewidth': 2})
