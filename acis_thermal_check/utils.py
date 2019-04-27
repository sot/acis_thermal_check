import numpy as np
import Ska.Sun
import logging
import os
import matplotlib.pyplot as plt
from Ska.Matplotlib import cxctime2plotdate
import Ska.Numpy
import six

TASK_DATA = os.path.abspath(os.path.join(os.path.dirname(__file__), '..'))

mylog = logging.getLogger('acis_thermal_check')


def calc_pitch_roll(ephem, states):
    """Calculate the normalized sun vector in body coordinates.
    Shamelessly copied from Ska.engarchive.derived.pcad but 
    modified to use commanded states quaternions

    Parameters
    ----------
    ephem : MSIDset with orbitephem and solarephem MSIDs
    states : commanded states NumPy recarray

    Returns
    -------
    3 NumPy arrays: time, pitch and roll
    """
    from Ska.engarchive.derived.pcad import arccos_clip, qrotate
    idxs = Ska.Numpy.interpolate(np.arange(len(states)), states['tstart'],
                                 ephem['solarephem0_x'].times, method='nearest')
    states = states[idxs]

    chandra_eci = np.array([ephem['orbitephem0_x'].vals,
                            ephem['orbitephem0_y'].vals,
                            ephem['orbitephem0_z'].vals])
    sun_eci = np.array([ephem['solarephem0_x'].vals,
                        ephem['solarephem0_y'].vals,
                        ephem['solarephem0_z'].vals])
    sun_vec = -chandra_eci + sun_eci
    est_quat = np.array([states['q1'],
                         states['q2'],
                         states['q3'],
                         states['q4']])

    sun_vec_b = qrotate(est_quat, sun_vec)  # Rotate into body frame
    magnitude = np.sqrt((sun_vec_b ** 2).sum(axis=0))
    magnitude[magnitude == 0.0] = 1.0
    sun_vec_b = sun_vec_b / magnitude  # Normalize

    pitch = np.degrees(arccos_clip(sun_vec_b[0, :]))
    roll = np.degrees(np.arctan2(-sun_vec_b[1, :], -sun_vec_b[2, :]))

    return ephem['orbitephem0_x'].times, pitch, roll


def config_logging(outdir, verbose):
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
    """
    # Disable auto-configuration of root logger by adding a null handler.
    # This prevents other modules (e.g. Chandra.cmd_states) from generating
    # a streamhandler by just calling logging.info(..).
    class NullHandler(logging.Handler):
        def emit(self, record):
            pass
    rootlogger = logging.getLogger()
    rootlogger.addHandler(NullHandler())

    logger = logging.getLogger('acis_thermal_check')
    logger.setLevel(logging.DEBUG)

    # Set numerical values for the different log levels
    loglevel = {0: logging.CRITICAL,
                1: logging.INFO,
                2: logging.DEBUG}.get(verbose, logging.INFO)

    formatter = logging.Formatter('%(message)s')

    console = logging.StreamHandler()
    console.setFormatter(formatter)
    console.setLevel(loglevel)
    logger.addHandler(console)

    logfile = os.path.join(outdir, 'run.dat')

    filehandler = logging.FileHandler(filename=logfile, mode='w')
    filehandler.setFormatter(formatter)
    # Set the file loglevel to be at least INFO,
    # but override to DEBUG if that is requested at the
    # command line
    filehandler.setLevel(logging.INFO)
    if loglevel == logging.DEBUG:
        filehandler.setLevel(logging.DEBUG)
    logger.addHandler(filehandler)


def plot_one(fig_id, x, y, linestyle='-', 
             color='blue', xmin=None,
             xmax=None, ylim=None, 
             xlabel='', ylabel='', title='',
             figsize=(7, 3.5), load_start=None,
             width=None):
    """
    Plot one quantities with a date x-axis and a left
    y-axis.

    Parameters
    ----------
    fig_id : integer
        The ID for this particular figure.
    x : NumPy array
        Times in seconds since the beginning of the mission for
        the left y-axis quantity.
    y : NumPy array
        Quantity to plot against the times on the left x-axis.
    linestyle : string, optional
        The style of the line for the left y-axis.
    color : string, optional
        The color of the line for the left y-axis.
    xmin : float, optional
        The left-most value of the x-axis.
    xmax : float, optional
        The right-most value of the x-axis.
    ylim : 2-tuple, optional
        The limits for the left y-axis.
    xlabel : string, optional
        The label of the x-axis.
    ylabel : string, optional
        The label for the left y-axis.
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
    if xmin is None:
        xmin = min(xt)
    if xmax is None:
        xmax = max(xt)
    ax.set_xlim(xmin, xmax)
    if ylim:
        ax.set_ylim(*ylim)
    ax.set_xlabel(xlabel)
    ax.set_ylabel(ylabel)
    ax.set_title(title)
    ax.grid()

    if load_start is not None:
        # Add a vertical line to mark the start time of the load
        ax.axvline(load_start, linestyle='-', color='g', linewidth=2.0)

    Ska.Matplotlib.set_time_ticks(ax)
    [label.set_rotation(30) for label in ax.xaxis.get_ticklabels()]

    fig.subplots_adjust(bottom=0.22, right=0.87)
    # The next several lines ensure that the width of the axes
    # of all the weekly prediction plots are the same
    if width is not None:
        w2, _ = fig.get_size_inches()
        lm = fig.subplotpars.left * width / w2
        rm = fig.subplotpars.right * width / w2
        fig.subplots_adjust(left=lm, right=rm)

    return {'fig': fig, 'ax': ax}


def plot_two(fig_id, x, y, x2, y2,
             linestyle='-', linestyle2='-',
             color='blue', color2='magenta',
             xmin=None, xmax=None, ylim=None, ylim2=None,
             xlabel='', ylabel='', ylabel2='', title='',
             figsize=(7, 3.5), load_start=None, width=None):
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
    xmin : float, optional
        The left-most value of the x-axis.
    xmax : float, optional
        The right-most value of the x-axis.
    ylim : 2-tuple, optional
        The limits for the left y-axis.
    ylim2 : 2-tuple, optional
        The limits for the right y-axis.
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
    if xmin is None:
        xmin = min(xt)
    if xmax is None:
        xmax = max(xt)
    ax.set_xlim(xmin, xmax)
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
    ax2.set_xlim(xmin, xmax)
    if ylim2:
        ax2.set_ylim(*ylim2)
    ax2.set_ylabel(ylabel2, color=color2)
    ax2.xaxis.set_visible(False)

    if load_start is not None:
        # Add a vertical line to mark the start time of the load
        ax.axvline(load_start, linestyle='-', color='g', linewidth=2.0)

    Ska.Matplotlib.set_time_ticks(ax)
    [label.set_rotation(30) for label in ax.xaxis.get_ticklabels()]
    [label.set_color(color2) for label in ax2.yaxis.get_ticklabels()]

    fig.subplots_adjust(bottom=0.22, right=0.87)
    # The next several lines ensure that the width of the axes
    # of all the weekly prediction plots are the same
    if width is not None:
        w2, _ = fig.get_size_inches()
        lm = fig.subplotpars.left * width / w2
        rm = fig.subplotpars.right * width / w2
        fig.subplots_adjust(left=lm, right=rm)

    return {'fig': fig, 'ax': ax, 'ax2': ax2}


def get_options(name, model_path, opts=None):
    """
    Construct the argument parser for command-line options for running
    predictions and validations for a load. Sets up the parser and 
    defines default options. This function should be used by the specific 
    thermal model checking tools.

    Parameters
    ----------
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
    parser.add_argument("--outdir", default="out", help="Output directory. Default: 'out'")
    parser.add_argument("--backstop_file", help="Path to the backstop file. If a directory, "
                                                "the backstop file will be searched for within "
                                                "this directory. Default: None")
    parser.add_argument("--oflsdir", help="Path to the directory containing the backstop "
                                          "file (legacy argument). If specified, it will "
                                          "override the value of the backstop_file "
                                          "argument. Default: None")
    parser.add_argument("--model-spec", 
                        default=os.path.join(model_path, '%s_model_spec.json' % name),
                        help="Model specification file. Defaults to the one included with "
                             "the model package.")
    parser.add_argument("--days", type=float, default=21.0,
                        help="Days of validation data. Default: 21")
    parser.add_argument("--run-start", help="Reference time to replace run start time "
                                            "for regression testing. The default is to "
                                            "use the current time.")
    parser.add_argument("--interrupt", help="Set this flag if this is an interrupt load.",
                        action='store_true')
    parser.add_argument("--traceback", default=True, help='Enable tracebacks. Default: True')
    parser.add_argument("--verbose", type=int, default=1,
                        help="Verbosity (0=quiet, 1=normal, 2=debug)")
    parser.add_argument("--T-init", type=float,
                        help="Starting temperature (degC or degF, depending on the model). "
                             "Default is to compute it from telemetry.")
    parser.add_argument("--cmd-states-db", default="sqlite",
                        help="Commanded states database server (sybase|sqlite). "
                             "Default: sqlite")
    parser.add_argument("--state-builder", default="acis",
                        help="StateBuilder to use (sql|acis). Default: acis")
    parser.add_argument("--version", action='store_true', help="Print version")
    # Argument pointing to the NLET file the model should use for this run
    parser.add_argument("--nlet_file",
                        default='/data/acis/LoadReviews/NonLoadTrackedEvents.txt',
                        help="Full path to the Non-Load Event Tracking file that should be "
                             "used for this model run.")
    parser.add_argument("--ephem_file",
                        help="Path to a file containing an ephemeris for the period "
                             "under consideration. Useful for testing purposes.")
    if opts is not None:
        for opt_name, opt in opts:
            parser.add_argument("--%s" % opt_name, **opt)

    args = parser.parse_args()

    if args.oflsdir is not None:
        args.backstop_file = args.oflsdir

    if args.cmd_states_db not in ('sybase', 'sqlite'):
        raise ValueError('--cmd-states-db must be one of "sybase" or "sqlite"')

    # Enforce sqlite cmd states db for Python 3
    if six.PY3 and args.cmd_states_db == 'sybase':
        args.cmd_states_db = 'sqlite'

    return args


def make_state_builder(name, args):
    """
    Take the command-line arguments and use them to construct
    a StateBuilder object which will be used for the thermal
    prediction and validation.

    Parameters
    ----------
    name : string 
        The identifier for the state builder to be used.
    args : ArgumentParser arguments
        The arguments to pass to the StateBuilder subclass.
    """
    # Import the dictionary of possible state builders. This
    # dictionary is located in state_builder.py
    from acis_thermal_check.state_builder import state_builders

    builder_class = state_builders[name]

    # Build the appropriate state_builder depending upon the
    # value of the passed in parameter "name" which was
    # originally the --state-builder="sql"|"acis" input argument
    #
    # Instantiate the SQL History Builder: SQLStateBuilder
    if name == "sql":
        state_builder = builder_class(interrupt=args.interrupt,
                                      backstop_file=args.backstop_file,
                                      cmd_states_db=args.cmd_states_db,
                                      logger=mylog)

    # Instantiate the ACIS OPS History Builder: ACISStateBuilder
    elif name == "acis":
        # Create a state builder using the ACIS Ops backstop history
        # modules
        state_builder = builder_class(interrupt=args.interrupt,
                                      backstop_file=args.backstop_file,
                                      nlet_file=args.nlet_file,
                                      cmd_states_db=args.cmd_states_db,
                                      logger=mylog)
    else:
        raise RuntimeError("No such state builder with name %s!" % name)

    return state_builder


def get_acis_limits(msid):
    """
    Get the current yellow hi limit and margin for a 
    given ACIS-related MSID, or the various limits 
    for the focal plane temperature.

    Parameters
    ----------
    msid : string
        The MSID to get the limits for, e.g. "1deamzt".
    """
    import requests

    if msid == "fptemp":
        fp_sens = -118.7
        acis_i = -112.0
        acis_s = -111.0
        return fp_sens, acis_i, acis_s

    yellow_lo = None
    yellow_hi = None

    margins = {"1dpamzt": 2.0, 
               "1deamzt": 2.0,
               "1pdeaat": 4.5,
               "tmp_fep1_mong": 2.0,
               "tmp_fep1_actel": 2.0,
               "tmp_bep_pcb": 2.0}

    margin = margins[msid]

    pmon_file = "PMON/pmon_limits.txt"
    eng_file = "Thermal/MSID_Limits.txt"
    file_root = "/proj/web-cxc-dmz/htdocs/acis/"

    if msid.startswith("tmp_"):
        limits_file = pmon_file
        cols = (4, 5)
        msid = "ADC_"+msid.upper()
    else:
        limits_file = eng_file
        cols = (2, 3)

    if os.path.exists(file_root):
        loc = "local"
        f = open(os.path.join(file_root, limits_file), "r")
        lines = f.readlines()
        f.close()
    else:
        loc = "remote"
        url = "http://cxc.cfa.harvard.edu/acis/"+limits_file
        u = requests.get(url)
        lines = u.text.split("\n")

    mylog.info("Obtaining limits for %s from %s file." % (msid, loc))

    for line in lines:
        words = line.strip().split()
        if len(words) > 1 and words[0] == msid.upper():
            yellow_lo = float(words[cols[0]])
            yellow_hi = float(words[cols[1]])
            break

    return yellow_lo, yellow_hi, margin
