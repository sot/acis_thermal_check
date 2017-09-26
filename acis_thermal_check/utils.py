import numpy as np
import Ska.Sun
import glob
import logging
import os
import matplotlib.pyplot as plt
from Ska.Matplotlib import cxctime2plotdate

TASK_DATA = os.path.abspath(os.path.join(os.path.dirname(__file__), '..'))

def calc_off_nom_rolls(states):
    """
    Calculate the off-nominal rolls from commanded states, which
    include for a given state its start and stop times and the
    attitude quaternion.

    states : NumPy record array
        The commanded states to compute the off-nominal rolls
        from.
    """
    off_nom_rolls = []
    for i, state in enumerate(states):
        att = [state[x] for x in ['q1', 'q2', 'q3', 'q4']]
        time = (state['tstart'] + state['tstop']) / 2
        off_nom_rolls.append(Ska.Sun.off_nominal_roll(att, time))
    return np.array(off_nom_rolls)

def globfile(pathglob):
    """
    Return the one file name matching ``pathglob``. Zero or multiple
    matches raises an IOError exception.
    """
    files = glob.glob(pathglob)
    if len(files) == 0:
        raise IOError('No files matching %s' % pathglob)
    elif len(files) > 1:
        raise IOError('Multiple files matching %s' % pathglob)
    else:
        return files[0]

def config_logging(outdir, verbose, name):
    """
    Set up file and console logger.
    See http://docs.python.org/library/logging.html#logging-to-multiple-destinations
    Logs to the console and to run.dat.

    Parameters
    ----------
    outdir : string
        The location of the directory which the model outputs
        are being written to.
    verbose : integer
        Indicate how verbose we want the logger to be.
        (0=quiet, 1=normal, 2=debug)
    name : string
        The name of the ACIS component whose temperature is being modeled.
    """
    # Disable auto-configuration of root logger by adding a null handler.
    # This prevents other modules (e.g. Chandra.cmd_states) from generating
    # a streamhandler by just calling logging.info(..).
    class NullHandler(logging.Handler):
        def emit(self, record):
            pass
    rootlogger = logging.getLogger()
    rootlogger.addHandler(NullHandler())

    # Set numerical values for the different log levels
    loglevel = {0: logging.CRITICAL,
                1: logging.INFO,
                2: logging.DEBUG}.get(verbose, logging.INFO)

    logger = logging.getLogger('%s_check' % name)
    logger.setLevel(loglevel)

    formatter = logging.Formatter('%(message)s')

    console = logging.StreamHandler()
    console.setFormatter(formatter)
    logger.addHandler(console)

    logfile = os.path.join(outdir, 'run.dat')

    filehandler = logging.FileHandler(filename=logfile, mode='w')
    filehandler.setFormatter(formatter)
    logger.addHandler(filehandler)

def plot_two(fig_id, x, y, x2, y2,
             linestyle='-', linestyle2='-',
             color='blue', color2='magenta',
             ylim=None, ylim2=None,
             xlabel='', ylabel='', ylabel2='', title='',
             figsize=(7, 3.5)):
    """
    Plot two quantities with a date x-axis, one on the left
    y-axis and the other on the right y-axis.

    Parameters
    ----------
    fig_id : integer
        The ID for this particular figure.
    x : NumPy array
        Times in seconds since the beginning of the mission for
        the left y-axis quantity.
    y : NumPy array
        Quantity to plot against the times on the left x-axis.
    x2 : NumPy array
        Times in seconds since the beginning of the mission for
        the right y-axis quantity.
    y2 : NumPy array
        Quantity to plot against the times on the right y-axis.
    linestyle : string, optional
        The style of the line for the left y-axis.
    linestyle2 : string, optional
        The style of the line for the right y-axis.
    color : string, optional
        The color of the line for the left y-axis.
    color2 : string, optional
        The color of the line for the right y-axis.
    xlabel : string, optional
        The label of the x-axis.
    ylabel : string, optional
        The label for the left y-axis.
    ylabel2 : string, optional
        The label for the right y-axis.
    title : string, optional
        The title for the plot.
    figsize : 2-tuple of floats
        Size of plot in width and height in inches.
    """
    # Convert times to dates
    xt = cxctime2plotdate(x)
    fig = plt.figure(fig_id, figsize=figsize)
    fig.clf()
    ax = fig.add_subplot(1, 1, 1)
    # Plot left y-axis
    ax.plot_date(xt, y, fmt='-', linestyle=linestyle, color=color)
    ax.set_xlim(min(xt), max(xt))
    if ylim:
        ax.set_ylim(*ylim)
    ax.set_xlabel(xlabel)
    ax.set_ylabel(ylabel)
    ax.set_title(title)
    ax.grid()

    # Plot right y-axis

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

def get_options(msid, name, model_path, opts=None):
    """
    Construct the argument parser for command-line options. Sets up the
    parser and defines default options. This function should be used by
    the specific thermal model checking tools.

    Parameters
    ----------
    msid : string
        The MSID mnemomic for the temperature to be modeled.
    name : string
        The name of the ACIS component whose temperature is being modeled.
    model_path : string
        The default directory path where the model JSON files are located.
        This is internal to the ``acis_thermal_check`` package.
    opts: dictionary
        A (key, value) dictionary of additional options for the parser. These
        may be defined by the thermal model checking tool if necessary.
    """
    from argparse import ArgumentParser
    parser = ArgumentParser()
    parser.set_defaults()
    parser.add_argument("--outdir", default="out", help="Output directory")
    parser.add_argument("--oflsdir", help="Load products OFLS directory")
    parser.add_argument("--model-spec", 
                        default=os.path.join(model_path, '%s_model_spec.json' % name),
                        help="Model specification file")
    parser.add_argument("--days", type=float, default=21.0,
                        help="Days of validation data (days)")
    parser.add_argument("--run-start", help="Reference time to replace run "
                                            "start time for regression testing")
    parser.add_argument("--traceback", default=True, help='Enable tracebacks')
    parser.add_argument("--verbose", type=int, default=1,
                        help="Verbosity (0=quiet, 1=normal, 2=debug)")
    parser.add_argument("--ccd-count", type=int, default=6,
                        help="Initial number of CCDs (default=6)")
    parser.add_argument("--fep-count", type=int, default=6,
                        help="Initial number of FEPs (default=6)")
    parser.add_argument("--vid-board", type=int, default=1,
                        help="Initial state of ACIS vid_board (default=1)")
    parser.add_argument("--clocking", type=int, default=1,
                        help="Initial state of ACIS clocking (default=1)")
    parser.add_argument("--simpos", default=75616.0, type=float,
                        help="Starting SIM-Z position (steps)")
    parser.add_argument("--pitch", default=150.0, type=float,
                        help="Starting pitch (deg)")
    parser.add_argument("--T-%s" % name, type=float,
                        help="Starting %s temperature (degC)" % msid)
    parser.add_argument("--cmd-states-db", default="sybase",
                        help="Commanded states database server (sybase|sqlite)")
    parser.add_argument("--version", action='store_true', help="Print version")
    if opts is not None:
        for opt_name, opt in opts:
            parser.add_argument("--%s" % opt_name, **opt)

    args = parser.parse_args()

    if args.cmd_states_db not in ('sybase', 'sqlite'):
        raise ValueError('--cmd-states-db must be one of "sybase" or "sqlite"')

    return args
