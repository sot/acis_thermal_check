import numpy as np
import Ska.Sun
import glob
import logging
import os
import matplotlib.pyplot as plt
from Ska.Matplotlib import cxctime2plotdate

TASK_DATA = os.path.abspath(os.path.join(os.path.dirname(__file__), '..'))

def calc_off_nom_rolls(states):
    off_nom_rolls = []
    for i, state in enumerate(states):
        att = [state[x] for x in ['q1', 'q2', 'q3', 'q4']]
        time = (state['tstart'] + state['tstop']) / 2
        off_nom_rolls.append(Ska.Sun.off_nominal_roll(att, time))
    return np.array(off_nom_rolls)

def globfile(pathglob):
    """Return the one file name matching ``pathglob``.  Zero or multiple
    matches raises an IOError exception."""

    files = glob.glob(pathglob)
    if len(files) == 0:
        raise IOError('No files matching %s' % pathglob)
    elif len(files) > 1:
        raise IOError('Multiple files matching %s' % pathglob)
    else:
        return files[0]

def config_logging(outdir, verbose, short_msid):
    """Set up file and console logger.
    See http://docs.python.org/library/logging.html
              #logging-to-multiple-destinations
    """
    # Disable auto-configuration of root logger by adding a null handler.
    # This prevents other modules (e.g. Chandra.cmd_states) from generating
    # a streamhandler by just calling logging.info(..).
    class NullHandler(logging.Handler):
        def emit(self, record):
            pass
    rootlogger = logging.getLogger()
    rootlogger.addHandler(NullHandler())

    loglevel = {0: logging.CRITICAL,
                1: logging.INFO,
                2: logging.DEBUG}.get(verbose, logging.INFO)

    logger = logging.getLogger('%s_check' % short_msid)
    logger.setLevel(loglevel)

    formatter = logging.Formatter('%(message)s')

    console = logging.StreamHandler()
    console.setFormatter(formatter)
    logger.addHandler(console)

    filehandler = logging.FileHandler(
            filename=os.path.join(outdir, 'run.dat'), mode='w')
    filehandler.setFormatter(formatter)
    logger.addHandler(filehandler)

def plot_two(fig_id, x, y, x2, y2,
             linestyle='-', linestyle2='-',
             color='blue', color2='magenta',
             ylim=None, ylim2=None,
             xlabel='', ylabel='', ylabel2='', title='',
             figsize=(7, 3.5),
             ):
    """Plot two quantities with a date x-axis"""
    xt = cxctime2plotdate(x)
    fig = plt.figure(fig_id, figsize=figsize)
    fig.clf()
    ax = fig.add_subplot(1, 1, 1)
    ax.plot_date(xt, y, fmt='-', linestyle=linestyle, color=color)
    ax.set_xlim(min(xt), max(xt))
    if ylim:
        ax.set_ylim(*ylim)
    ax.set_xlabel(xlabel)
    ax.set_ylabel(ylabel)
    ax.set_title(title)
    ax.grid()

    ax2 = ax.twinx()

    xt2 = cxctime2plotdate(x2)
    ax2.plot_date(xt2, y2, fmt='-', linestyle=linestyle2, color=color2)
    ax2.set_xlim(min(xt), max(xt))
    if ylim2:
        ax2.set_ylim(*ylim2)
    ax2.set_ylabel(ylabel2, color=color2)
    ax2.xaxis.set_visible(False)

    Ska.Matplotlib.set_time_ticks(ax)
    [label.set_rotation(30) for label in ax.xaxis.get_ticklabels()]
    [label.set_color(color2) for label in ax2.yaxis.get_ticklabels()]

    fig.subplots_adjust(bottom=0.22)

    return {'fig': fig, 'ax': ax, 'ax2': ax2}

def get_options(msid, short_msid, script_path, opts=None):
    from optparse import OptionParser
    parser = OptionParser()
    parser.set_defaults()
    parser.add_option("--outdir",
                      default="out",
                      help="Output directory")
    parser.add_option("--oflsdir",
                      help="Load products OFLS directory")
    parser.add_option("--model-spec",
                      default=os.path.join(script_path, '%s_model_spec.json' % short_msid),
                      help="Model specification file")
    parser.add_option("--days",
                      type='float',
                      default=21.0,
                      help="Days of validation data (days)")
    parser.add_option("--run-start",
                      help="Reference time to replace run start time "
                           "for regression testing")
    parser.add_option("--traceback",
                      default=True,
                      help='Enable tracebacks')
    parser.add_option("--verbose",
                      type='int',
                      default=1,
                      help="Verbosity (0=quiet, 1=normal, 2=debug)")
    parser.add_option("--ccd-count",
                      type='int',
                      default=6,
                      help="Initial number of CCDs (default=6)")
    parser.add_option("--fep-count",
                      type='int',
                      default=6,
                      help="Initial number of FEPs (default=6)")
    parser.add_option("--vid-board",
                      type='int',
                      default=1,
                      help="Initial state of ACIS vid_board (default=1)")
    parser.add_option("--clocking",
                      type='int',
                      default=1,
                      help="Initial state of ACIS clocking (default=1)")
    parser.add_option("--simpos",
                      default=75616,
                      type='float',
                      help="Starting SIM-Z position (steps)")
    parser.add_option("--pitch",
                      default=150.0,
                      type='float',
                      help="Starting pitch (deg)")
    parser.add_option("--T-%s" % short_msid,
                      type='float',
                      help="Starting %s temperature (degC)" % msid)
    parser.add_option("--cmd-states-db",
                      default="sqlite",
                      help="Commanded states database server (sybase|sqlite)")
    parser.add_option("--version",
                      action='store_true',
                      help="Print version")
    if opts is not None:
        for opt_name, opt in opts:
            parser.add_option("--%s" % opt_name, **opt)

    opt, args = parser.parse_args()

    if opt.cmd_states_db not in ('sybase', 'sqlite'):
        raise ValueError('--cmd-states-db must be one of "sybase" or "sqlite"')

    return opt, args
