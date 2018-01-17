from __future__ import print_function

# Matplotlib setup
# Use Agg backend for command-line (non-interactive) operation
import matplotlib
matplotlib.use('Agg')

import os
from pprint import pformat
from collections import OrderedDict, defaultdict
import re
import time
import pickle
import numpy as np
import Ska.DBI
import Ska.Numpy
from Chandra.Time import DateTime
import matplotlib.pyplot as plt
from Ska.Matplotlib import cxctime2plotdate, \
    pointpair, plot_cxctime
import Ska.engarchive.fetch_sci as fetch
import shutil
import acis_thermal_check
version = acis_thermal_check.__version__
from acis_thermal_check.utils import \
    config_logging, TASK_DATA, plot_two, \
    mylog, plot_one, calc_off_nom_rolls
from kadi import events

class ACISThermalCheck(object):
    r"""
    ACISThermalCheck class for making thermal model predictions
    and validating past model data against telemetry

    ACISThermalCheck takes inputs to model a specific ACIS
    component temperature and evolves a Xija thermal model
    forward in time to predict temperatures for a given period,
    typically a load which is under review. This information is
    outputted onto a web page in the form of plots and statistical
    information about the model run. ACISThermalCheck also
    runs the thermal model for a period previous to the current
    time for validation of the model against telemetry, and outputs
    plots to the same web page.

    Parameters
    ----------
    msid : string
        The MSID mnemomic for the temperature to be modeled.
    name : string
        The name of the ACIS component whose temperature is
        being modeled.
    MSIDs : dictionary of string values
        A dictionary mapping between names (e.g., "dea") and
        MSIDs (e.g., "1DEAMZT") for components that will be
        modeled or used in the model.
    yellow : dictionary of float values
        A dictionary mapping between names (e.g., "dea") and
        the yellow limits for the corresponding components.
    margin : dictionary of float values
        A dictionary mapping between names (e.g., "dea") and
        the margin between the yellow limit and the planning
        limit for the corresponding components.
    validation_limits : dictionary of lists of tuples
        A dictionary mapping between names (e.g., "dea") and
        the validation limits for each component in the form
        of a list of tuples, where each tuple corresponds to
        (percentile, model-data), e.g.: [(1, 2.0), (50, 1.0),
        (99, 2.0)]
    hist_limit : list of floats
        A list of floating-point values corresponding to the
        temperatures which will be included in the validation
        histogram. The number of colored histograms on the plot
        will correspond to the number of values in this list.
    calc_model : function
        A function which is used to drive Xija and run the
        thermal model. It must have the following signature:
        def calc_model(model_spec, states, start, stop,
                       T_comp=None, T_comp_times=None)
        "model_spec": The model specifiation which is used to
        run the model.
        "states": commanded states structured NumPy array.
        "start": The start time of the model run
        "stop": The stop time of the model run
        "T_comp": The initial temperature values of the components
        "T_comp_times": The times at which the components of the
        temperature are defined
    other_telem : list of strings, optional
        A list of other MSIDs that may need to be obtained from
        the engineering archive for validation purposes. The
        calling program determines this.
    other_map : dictionary, optional
        A dictionary which maps names to MSIDs, e.g.:
        {'sim_z': 'tscpos', 'dp_pitch': 'pitch'}. Used to map
        names understood by Xija to MSIDs.
    """
    def __init__(self, msid, name, MSIDs, yellow, margin, 
                 validation_limits, hist_limit, calc_model,
                 other_telem=None, other_map=None):
        self.msid = msid
        self.name = name
        self.MSIDs = MSIDs
        self.yellow = yellow
        self.margin = margin
        self.validation_limits = validation_limits
        self.hist_limit = hist_limit
        self.calc_model = calc_model
        self.other_telem = other_telem
        self.other_map = other_map

    def driver(self, args, state_builder):
        """
        The main interface to all of ACISThermalCheck's functions.
        This method must be called by the particular thermal model
        implementation to actually run the code and make the webpage.

        Parameters
        ----------
        args : ArgumentParser arguments
            The command-line options object, which has the options
            attached to it as attributes
        state_builder : StateBuilder object
            The StateBuilder object used to construct commanded states
        """
        self.state_builder = state_builder

        proc = self._setup_proc_and_logger(args)

        is_weekly_load = args.backstop_file is not None
        tstart, tstop, tnow = self._determine_times(args.run_start,
                                                    is_weekly_load)

        proc["datestart"] = DateTime(tstart).date
        if tstop is not None:
            proc["datestop"] = DateTime(tstop).date

        # Get the telemetry values which will be used
        # for prediction and validation
        tlm = self.get_telem_values(min(tstart, tnow), days=args.days)

        # make predictions on a backstop file if defined
        if args.backstop_file is not None:
            pred = self.make_week_predict(tstart, tstop, tlm, args.T_init, 
                                          args.model_spec, args.outdir)
        else:
            pred = defaultdict(lambda: None)

        # Validation
        # Make the validation plots
        plots_validation = self.make_validation_plots(tlm, args.model_spec,
                                                      args.outdir, args.run_start)

        # Determine violations of temperature validation
        valid_viols = self.make_validation_viols(plots_validation)
        if len(valid_viols) > 0:
            mylog.info('validation warning(s) in output at %s' % args.outdir)

        # Write everything to the web page.
        # First, write the reStructuredText file.

        # Set up the context for the reST file
        context = {'bsdir': self.bsdir,
                   'plots': pred["plots"],
                   'viols': pred["viols"],
                   'valid_viols': valid_viols,
                   'proc': proc,
                   'plots_validation': plots_validation}
        self.write_index_rst(self.bsdir, args.outdir, context)

        # Second, convert reST to HTML
        self.rst_to_html(args.outdir, proc)

        return

    def get_states(self, tlm, T_init):
        """
        Call the state builder to get the commanded states and
        determine the initial temperature.

        Parameters
        ----------
        tlm : NumPy structured array
            Telemetry which will be used to construct the initial temperature
        T_init : float
            The initial temperature of the model prediction. If None, an
            initial value will be constructed from telemetry.
        """

        # The -5 here has us back off from the last telemetry reading just a bit
        tbegin = DateTime(tlm['date'][-5]).date
        states, state0 = self.state_builder.get_prediction_states(tbegin)

        # We now determine the initial temperature.

        # If we have an initial temperature input from the
        # command line, use it, otherwise construct T_init 
        # from an average of telemetry values around state0
        if T_init is None:
            ok = ((tlm['date'] >= state0['tstart'] - 700) &
                  (tlm['date'] <= state0['tstart'] + 700))
            T_init = np.mean(tlm[self.msid][ok])

        state0.update({self.msid: T_init})

        return states, state0

    def make_week_predict(self, tstart, tstop, tlm, T_init, model_spec,
                          outdir):
        """
        Parameters
        ----------
        tstart : float
            The start time of the model run in seconds from the beginning
            of the mission.
        tstop : float
            The stop time of the model run in seconds from the beginning
            of the mission.
        tlm : NumPy structured array
            Telemetry which will be used to construct the initial temperature
        T_init : float
            The initial temperature of the model prediction. If None, an
            initial value will be constructed from telemetry.
        model_spec : string
            The path to the thermal model specification.
        outdir : string
            The directory to write outputs to.
        """
        mylog.info('Calculating %s thermal model' % self.name.upper())

        # Get commanded states and set initial temperature
        states, state0 = self.get_states(tlm, T_init)

        # calc_model_wrapper actually does the model calculation by running
        # model-specific code.
        model = self.calc_model_wrapper(model_spec, states, state0['tstart'], 
                                        tstop, state0=state0)

        # Make the limit check plots and data files
        plt.rc("axes", labelsize=10, titlesize=12)
        plt.rc("xtick", labelsize=10)
        plt.rc("ytick", labelsize=10)
        temps = {self.name: model.comp[self.msid].mvals}
        # make_prediction_plots runs the validation of the model against previous telemetry
        plots = self.make_prediction_plots(outdir, states, model.times, temps, tstart)
        # make_prediction_viols determines the violations and prints them out
        viols = self.make_prediction_viols(model.times, temps, tstart)
        # write_states writes the commanded states to states.dat
        self.write_states(outdir, states)
        # write_temps writes the temperatures to temperatures.dat
        self.write_temps(outdir, model.times, temps)

        return dict(states=states, times=model.times, temps=temps,
                    plots=plots, viols=viols)

    def calc_model_wrapper(self, model_spec, states, tstart, tstop, state0=None):
        """
        This method sets up the model and runs it. "calc_model" is
        provided by the specific model instances.

        Parameters
        ----------
        model_spec : string
            Path to the JSON file containing the model specification.
        states : NumPy record array
            Commanded states
        tstart : float
            The start time of the model run.
        tstop : float
            The end time of the model run. 
        state0 : initial state dictionary, optional
            This state is used to set the initial temperature.
        """
        if state0 is None:
            start_msid = None
        else:
            start_msid = state0[self.msid]
        return self.calc_model(model_spec, states, tstart, tstop, start_msid)

    def make_validation_viols(self, plots_validation):
        """
        Find limit violations where MSID quantile values are outside the
        allowed range.

        Parameters
        ----------
        plots_validation : list of dictionaries
            List of dictionaries with information about the contents of the
            plots which will be used to compute violations
        """
        mylog.info('Checking for validation violations')

        viols = []

        for plot in plots_validation:
            # 'plot' is actually a structure with plot info and stats about the
            # plotted data for a particular MSID. 'msid' can be a real MSID
            # (1DEAMZT) or pseudo like 'POWER'
            msid = plot['msid']

            # Make sure validation limits exist for this MSID
            if msid not in self.validation_limits:
                continue

            # Cycle through defined quantiles (e.g. 99 for 99%) and corresponding
            # limit values for this MSID.
            for quantile, limit in self.validation_limits[msid]:
                # Get the quantile statistic as calculated when making plots
                msid_quantile_value = float(plot['quant%02d' % quantile])

                # Check for a violation and take appropriate action
                if abs(msid_quantile_value) > limit:
                    viol = {'msid': msid,
                            'value': msid_quantile_value,
                            'limit': limit,
                            'quant': quantile,
                            }
                    viols.append(viol)
                    mylog.info('WARNING: %s %d%% quantile value of %s exceeds '
                               'limit of %.2f' % (msid, quantile,
                                                  msid_quantile_value, limit))

        return viols

    def make_prediction_viols(self, times, temps, load_start):
        """
        Find limit violations where predicted temperature is above the
        yellow limit minus margin.

        Parameters
        ----------
        times : NumPy array
            Times from the start of the mission in seconds.
        temps : dict of NumPy arrays
            NumPy arrays corresponding to the modeled temperatures
        load_start : float
            The start time of the load, used so that we only report
            violations for times later than this time for the model
            run.
        """
        mylog.info('Checking for limit violations')

        viols = dict((x, []) for x in self.MSIDs)
        for msid in self.MSIDs:
            temp = temps[msid]
            plan_limit = self.yellow[msid] - self.margin[msid]
            # The NumPy black magic of the next two lines is to figure 
            # out which time periods have planning limit violations and 
            # to find the bounding indexes of these times. This will also
            # find violations which happen for one discrete time value also.
            bad = np.concatenate(([False], temp >= plan_limit, [False]))
            changes = np.flatnonzero(bad[1:] != bad[:-1]).reshape(-1, 2)
            # Now go through the periods where the temperature violates
            # the planning limit and flag the duration and maximum of
            # the violation
            for change in changes:
                # Only report violations which occur after the load being
                # reviewed starts.
                in_load = times[change[0]] > load_start or \
                          (times[change[0]] < load_start < times[change[1]])
                if in_load:
                    viol = {'datestart': DateTime(times[change[0]]).date,
                            'datestop': DateTime(times[change[1] - 1]).date,
                            'maxtemp': temp[change[0]:change[1]].max()}
                    mylog.info('WARNING: %s exceeds planning limit of %.2f '
                               'degC from %s to %s' % (self.MSIDs[msid],
                                                       plan_limit,
                                                       viol['datestart'],
                                                       viol['datestop']))
                    viols[msid].append(viol)

        viols["default"] = viols[self.name]

        return viols

    def write_states(self, outdir, states):
        """
        Write the states record array to the file "states.dat".

        Parameters
        ----------
        outdir : string
            The directory the file will be written to.
        states : NumPy record array
            The commanded states to be written to the file.
        """
        outfile = os.path.join(outdir, 'states.dat')
        mylog.info('Writing states to %s' % outfile)
        out = open(outfile, 'w')
        fmt = {'power': '%.1f',
               'pitch': '%.2f',
               'tstart': '%.2f',
               'tstop': '%.2f'}
        Ska.Numpy.pprint(states, fmt, out)
        out.close()

    def write_temps(self, outdir, times, temps):
        """
        Write the states record array to the file "states.dat".

        Parameters
        ----------
        outdir : string
            The directory the file will be written to.
        times : NumPy array
            Times in seconds from the start of the mission
        temps : NumPy array
            Temperatures in Celsius
        """
        outfile = os.path.join(outdir, 'temperatures.dat')
        mylog.info('Writing temperatures to %s' % outfile)
        T = temps[self.name]
        temp_recs = [(times[i], DateTime(times[i]).date, T[i])
                     for i in range(len(times))]
        temp_array = np.rec.fromrecords(
            temp_recs, names=('time', 'date', self.msid))

        fmt = {self.msid: '%.2f',
               'time': '%.2f'}
        out = open(outfile, 'w')
        Ska.Numpy.pprint(temp_array, fmt, out)
        out.close()

    def make_prediction_plots(self, outdir, states, times, temps, load_start):
        """
        Make plots of the thermal prediction as well as associated 
        commanded states.

        Parameters
        ----------
        outdir : string
            The path to the output directory.
        states : NumPy record array
            Commanded states
        times : NumPy array
            Times in seconds from the beginning of the mission for the
            temperature arrays
        temps : dict of NumPy arrays
            Dictionary of temperature arrays
        load_start : float
            The start time of the load in seconds from the beginning of the
            mission.
        """
        plots = {}

        # Start time of loads being reviewed expressed in units for plotdate()
        load_start = cxctime2plotdate([load_start])[0]
        # Value for left side of plots
        plot_start = max(load_start-2.0, cxctime2plotdate([times[0]])[0])
        # Make the plots for the temperature prediction. This loop allows us
        # to make a plot for more than one temperature, but we currently only 
        # do one. Plots are of temperature on the left axis and pitch on the
        # right axis. 
        mylog.info('Making temperature prediction plots')
        for fig_id, msid in enumerate((self.name,)):
            plots[msid] = plot_two(fig_id=fig_id + 1,
                                   x=times,
                                   y=temps[msid],
                                   x2=pointpair(states['tstart'], states['tstop']),
                                   y2=pointpair(states['pitch']),
                                   title=self.MSIDs[msid],
                                   xlabel='Date',
                                   ylabel='Temperature (C)',
                                   ylabel2='Pitch (deg)',
                                   ylim2=(40, 180))
            # Add horizontal lines for the planning and caution limits
            plots[msid]['ax'].axhline(self.yellow[msid], linestyle='-', color='y',
                                      linewidth=2.0)
            plots[msid]['ax'].axhline(self.yellow[msid] - self.margin[msid], linestyle='--',
                                      color='y', linewidth=2.0)
            # Add a vertical line to mark the start of the load
            plots[msid]['ax'].axvline(load_start, linestyle='-', color='g',
                                      linewidth=2.0)
            # Set the left limit of the plot to be -2 days before the load start
            plots[msid]['ax'].set_xlim(plot_start, None)
            filename = self.MSIDs[self.name].lower() + '.png'
            outfile = os.path.join(outdir, filename)
            mylog.info('Writing plot file %s' % outfile)
            plots[msid]['fig'].savefig(outfile)
            plots[msid]['filename'] = filename

        fig_id += 1

        # Make a plot of ACIS CCDs and SIM-Z position
        plots['pow_sim'] = plot_two(
            fig_id=fig_id,
            title='ACIS CCDs and SIM-Z position',
            xlabel='Date',
            x=pointpair(states['tstart'], states['tstop']),
            y=pointpair(states['ccd_count']),
            ylabel='CCD_COUNT',
            ylim=(-0.1, 6.1),
            x2=pointpair(states['tstart'], states['tstop']),
            y2=pointpair(states['simpos']),
            ylabel2='SIM-Z (steps)',
            ylim2=(-105000, 105000),
            figsize=(7.5, 3.5))
        # Add a vertical line to mark the start time of the load
        plots['pow_sim']['ax'].axvline(load_start, linestyle='-', color='g',
                                       linewidth=2.0)
        # Set the left limit of the plot to be -2 days before the load start
        plots['pow_sim']['ax'].set_xlim(plot_start, None)
        # The next several lines ensure that the width of the axes
        # of all the weekly prediction plots are the same.
        w1, h1 = plots[self.name]['fig'].get_size_inches()
        w2, h2 = plots['pow_sim']['fig'].get_size_inches()
        lm = plots[self.name]['fig'].subplotpars.left*w1/w2
        rm = plots[self.name]['fig'].subplotpars.right*w1/w2
        plots['pow_sim']['fig'].subplots_adjust(left=lm, right=rm)
        filename = 'pow_sim.png'
        outfile = os.path.join(outdir, filename)
        mylog.info('Writing plot file %s' % outfile)
        plots['pow_sim']['fig'].savefig(outfile)
        plots['pow_sim']['filename'] = filename

        fig_id += 1

        # Make a plot of off-nominal roll
        plots['roll'] = plot_one(
            fig_id=4,
            title='Off-Nominal Roll',
            xlabel='Date',
            x=pointpair(states['tstart'], states['tstop']),
            y=pointpair(calc_off_nom_rolls(states)),
            ylabel='Roll Angle (deg)',
            ylim=(-20.0, 20.0),
            figsize=(7.5, 3.5))
        # Add a vertical line to mark the start time of the load
        plots['roll']['ax'].axvline(load_start, linestyle='-', color='g',
                                    linewidth=2.0)
        # Set the left limit of the plot to be -2 days before the load start
        plots['roll']['ax'].set_xlim(plot_start, None)
        # The next several lines ensure that the width of the axes
        # of all the weekly prediction plots are the same.
        w2, h2 = plots['roll']['fig'].get_size_inches()
        lm = plots[self.name]['fig'].subplotpars.left*w1/w2
        rm = plots[self.name]['fig'].subplotpars.right*w1/w2
        plots['roll']['fig'].subplots_adjust(left=lm, right=rm)
        filename = 'roll.png'
        outfile = os.path.join(outdir, filename)
        mylog.info('Writing plot file %s' % outfile)
        plots['roll']['fig'].savefig(outfile)
        plots['roll']['filename'] = filename

        plots['default'] = plots[self.name]

        return plots

    def get_histogram_mask(self, tlm, limit):
        """
        This method determines which values of telemetry
        should be used to construct the temperature 
        histogram plots, using limits provided by the 
        calling program to mask the array via a logical
        operation. The default implementation is to plot 
        values above a certain limit. This method may be 
        overriden by subclasses of ACISThermalCheck.

        Parameters
        ----------
        tlm : NumPy record array
            NumPy record array of telemetry
        limit : array of floats
            The limit or limits to use in the masking.
        """
        return tlm[self.msid] > limit

    def make_validation_plots(self, tlm, model_spec, outdir, run_start):
        """
        Make validation output plots by running the thermal model from a
        time in the past forward to the present and compare it to real
        telemetry

        Parameters
        ----------
        tlm : NumPy record array
            NumPy record array of telemetry
        model_spec : string
            The path to the thermal model specification.
        outdir : string
            The directory to write outputs to.
        run_start : string
            The starting date/time of the run. 
        """
        start = tlm['date'][0]
        stop = tlm['date'][-1]
        states = self.state_builder.get_validation_states(start, stop)

        mylog.info('Calculating %s thermal model for validation' % self.name.upper())

        # Run the thermal model from the beginning of obtained telemetry
        # to the end, so we can compare its outputs to the real values
        model = self.calc_model_wrapper(model_spec, states, start, stop)

        # Use an OrderedDict here because we want the plots on the validation
        # page to appear in this order
        pred = OrderedDict([(self.msid, model.comp[self.msid].mvals),
                            ('pitch', model.comp['pitch'].mvals),
                            ('tscpos', model.comp['sim_z'].mvals)])
        if "roll" in model.comp:
            pred["roll"] = model.comp['roll'].mvals

        # Interpolate the model and data to a consistent set of times
        idxs = Ska.Numpy.interpolate(np.arange(len(tlm)), tlm['date'], model.times,
                                     method='nearest')
        tlm = tlm[idxs]

        # Set up labels for validation plots
        labels = {self.msid: 'Degrees (C)',
                  'pitch': 'Pitch (degrees)',
                  'tscpos': 'SIM-Z (steps/1000)',
                  'roll': 'Off-Nominal Roll (degrees)'}

        scales = {'tscpos': 1000.}

        fmts = {self.msid: '%.2f',
                'pitch': '%.3f',
                'tscpos': '%d',
                'roll': '%.3f'}

        # Set up a mask of "good times" for which the validation is 
        # "valid", e.g., not during situations where we expect in 
        # advance that telemetry and model data will not match. This
        # is so we do not flag violations during these times
        good_mask = np.ones(len(tlm), dtype='bool')
        if hasattr(model, "bad_times"):
            for interval in model.bad_times:
                bad = ((tlm['date'] >= DateTime(interval[0]).secs)
                    & (tlm['date'] < DateTime(interval[1]).secs))
                good_mask[bad] = False

        # find perigee passages
        rzs = events.rad_zones.filter(start, stop)

        plots = []
        mylog.info('Making %s model validation plots and quantile table' % self.name.upper())
        quantiles = (1, 5, 16, 50, 84, 95, 99)
        # store lines of quantile table in a string and write out later
        quant_table = ''
        quant_head = ",".join(['MSID'] + ["quant%d" % x for x in quantiles])
        quant_table += quant_head + "\n"
        for fig_id, msid in enumerate(pred.keys()):
            plot = dict(msid=msid.upper())
            fig = plt.figure(10 + fig_id, figsize=(7, 3.5))
            fig.clf()
            scale = scales.get(msid, 1.0)
            ticklocs, fig, ax = plot_cxctime(model.times, tlm[msid] / scale,
                                             fig=fig, fmt='-r')
            ticklocs, fig, ax = plot_cxctime(model.times, pred[msid] / scale,
                                             fig=fig, fmt='-b')
            if np.any(~good_mask):
                ticklocs, fig, ax = plot_cxctime(model.times[~good_mask], tlm[msid][~good_mask] / scale,
                                                 fig=fig, fmt='.c')
            ax.set_title(msid.upper() + ' validation')
            ax.set_ylabel(labels[msid])
            ax.grid()
            # add lines for perigee passages
            for rz in rzs:
                ptimes = cxctime2plotdate([rz.tstart, rz.tstop])
                for ptime in ptimes:
                    ax.axvline(ptime, ls='--', color='g')
            filename = msid + '_valid.png'
            outfile = os.path.join(outdir, filename)
            mylog.info('Writing plot file %s' % outfile)
            fig.savefig(outfile)
            plot['lines'] = filename

            # Figure out histogram masks
            if msid == self.msid:
                ok = self.get_histogram_mask(tlm, self.hist_limit[0]) 
                ok = ok & good_mask
            else:
                ok = slice(None, None, None)
            diff = np.sort(tlm[msid][ok] - pred[msid][ok])
            # The PSMC model has a second histogram limit
            if len(self.hist_limit) == 2:
                if msid == self.msid:
                    ok2 = self.get_histogram_mask(tlm, self.hist_limit[1])
                    ok2 = ok2 & good_mask
                else:
                    ok2 = slice(None, None, None)
                diff2 = np.sort(tlm[msid][ok2] - pred[msid][ok2])
            else:
                ok2 = np.zeros(len(tlm[msid]), dtype=bool)
            quant_line = "%s" % msid
            for quant in quantiles:
                quant_val = diff[(len(diff) * quant) // 100]
                plot['quant%02d' % quant] = fmts[msid] % quant_val
                quant_line += (',' + fmts[msid] % quant_val)
            quant_table += quant_line + "\n"

            # We make two histogram plots for each validation,
            # one with linear and another with log scaling.
            for histscale in ('log', 'lin'):
                fig = plt.figure(20 + fig_id, figsize=(4, 3))
                fig.clf()
                ax = fig.gca()
                ax.hist(diff / scale, bins=50, log=(histscale == 'log'))
                if msid == self.msid and len(self.hist_limit) == 2 and ok2.any():
                    ax.hist(diff2 / scale, bins=50, log=(histscale == 'log'),
                            color = 'red')
                ax.set_title(msid.upper() + ' residuals: data - model')
                ax.set_xlabel(labels[msid])
                fig.subplots_adjust(bottom=0.18)
                filename = '%s_valid_hist_%s.png' % (msid, histscale)
                outfile = os.path.join(outdir, filename)
                mylog.info('Writing plot file %s' % outfile)
                fig.savefig(outfile)
                plot['hist' + histscale] = filename

            plots.append(plot)

        # Write quantile tables to a CSV file
        filename = os.path.join(outdir, 'validation_quant.csv')
        mylog.info('Writing quantile table %s' % filename)
        f = open(filename, 'w')
        f.write(quant_table)
        f.close()

        # If run_start is specified this is likely for regression testing
        # or other debugging.  In this case write out the full predicted and
        # telemetered dataset as a pickle.
        if run_start:
            filename = os.path.join(outdir, 'validation_data.pkl')
            mylog.info('Writing validation data %s' % filename)
            f = open(filename, 'wb')
            pickle.dump({'pred': pred, 'tlm': tlm}, f, protocol=-1)
            f.close()

        return plots

    def rst_to_html(self, outdir, proc):
        """Run rst2html.py to render index.rst as HTML]

        Parameters
        ----------
        outdir : string
            The path to the directory to which the outputs will be 
            written to.
        proc : dict
            A dictionary of general information used in the output
        """
        # First copy CSS files to outdir
        import Ska.Shell
        import docutils.writers.html4css1
        dirname = os.path.dirname(docutils.writers.html4css1.__file__)
        shutil.copy2(os.path.join(dirname, 'html4css1.css'), outdir)

        shutil.copy2(os.path.join(TASK_DATA, 'acis_thermal_check', 'templates', 
                                  'acis_thermal_check.css'), outdir)

        # Spawn a shell and call rst2html to generate HTML from the reST.
        spawn = Ska.Shell.Spawn(stdout=None)
        infile = os.path.join(outdir, 'index.rst')
        outfile = os.path.join(outdir, 'index.html')
        status = spawn.run(['rst2html.py',
                            '--stylesheet-path={}'
                            .format(os.path.join(outdir, 'acis_thermal_check.css')),
                            infile, outfile])
        if status != 0:
            proc['errors'].append('rst2html.py failed with status {}: see run log'
                                  .format(status))
            mylog.error('rst2html.py failed')
            mylog.error(''.join(spawn.outlines) + '\n')

        # Remove the stupid <colgroup> field that docbook inserts.  This
        # <colgroup> prevents HTML table auto-sizing.
        del_colgroup = re.compile(r'<colgroup>.*?</colgroup>', re.DOTALL)
        outtext = del_colgroup.sub('', open(outfile).read())
        open(outfile, 'w').write(outtext)

    def write_index_rst(self, bsdir, outdir, context, template_path=None):
        """
        Make output text (in ReST format) in outdir, using jinja2
        to fill out the template. 

        Parameters
        ----------
        bsdir : string
            Path to the directory containing the backstop file that was 
            used when running the model. May be None if that was not 
            the case.
        outdir : string
            Path to the location where the outputs will be written.
        context : dict
            Dictionary of items which will be written to the ReST file.
        template_path : string, optional
            Optional path to look for the ReST template. Default is to
            use the one internal to acis_thermal_check.
        """
        import jinja2
        if template_path is None:
            template_path = os.path.join(TASK_DATA, 'acis_thermal_check',
                                         'templates')
        outfile = os.path.join(outdir, 'index.rst')
        mylog.info('Writing report file %s' % outfile)
        # Open up the reST template and send the context to it using jinja2
        index_template_file = ('index_template.rst'
                               if bsdir else
                               'index_template_val_only.rst')
        index_template = open(os.path.join(template_path, 
                                           index_template_file)).read()
        index_template = re.sub(r' %}\n', ' %}', index_template)
        template = jinja2.Template(index_template)
        # Render the template and write it to a file
        open(outfile, 'w').write(template.render(**context))

    def _setup_proc_and_logger(self, args):
        """
        This method does some initial setup and logs important
        information.

        Parameters
        ----------
        args : ArgumentParser arguments
            The command-line options object, which has the options
            attached to it as attributes
        """
        if not os.path.exists(args.outdir):
            os.mkdir(args.outdir)

        # Configure the logger so that it knows which model
        # we are using and how verbose it is supposed to be
        config_logging(args.outdir, args.verbose)

        # Store info relevant to processing for use in outputs
        proc = dict(run_user=os.environ['USER'],
                    run_time=time.ctime(),
                    errors=[],
                    msid=self.msid.upper(),
                    name=self.name.upper(),
                    hist_limit=self.hist_limit)
        proc["msid_limit"] = self.yellow[self.name] - self.margin[self.name]
        mylog.info('##############################'
                   '#######################################')
        mylog.info('# %s_check run at %s by %s'
                   % (self.name, proc['run_time'], proc['run_user']))
        mylog.info('# acis_thermal_check version = %s' % version)
        mylog.info('# model_spec file = %s' % os.path.abspath(args.model_spec))
        mylog.info('###############################'
                   '######################################\n')
        mylog.info('Command line options:\n%s\n' % pformat(args.__dict__))

        mylog.info("ACISThermalCheck is using the '%s' state builder." % args.state_builder)

        if args.backstop_file is None:
            self.bsdir = None
        else:
            if os.path.isdir(args.backstop_file):
                self.bsdir = args.backstop_file
            else:
                self.bsdir = os.path.dirname(args.backstop_file)
        return proc

    def _determine_times(self, run_start, is_weekly_load):
        """
        Determine the start and stop times

        Parameters
        ----------
        run_start : string
            The starting date/time of the run.
        is_weekly_load : boolean
            Whether or not this is a weekly load.
        """
        tnow = DateTime(run_start).secs
        # Get tstart, tstop, commands from state builder
        if is_weekly_load:
            # If we are running a model for a particular load,
            # get tstart, tstop, commands from backstop file
            # in args.backstop_file
            tstart = self.state_builder.tstart
            tstop = self.state_builder.tstop
        else:
            # Otherwise, the start time for the run is whatever is in
            # args.run_start
            tstart = tnow
            tstop = None

        return tstart, tstop, tnow

    def get_telem_values(self, tstart, days=14):
        """
        Fetch last ``days`` of available telemetry values before
        time ``tstart``.

        Parameters
        ----------
        tstart: float
            Start time for telemetry (secs)
        days: integer, optional
            Length of telemetry request before ``tstart`` in days. Default: 14
        """
        # Get temperature and other telemetry for 3 weeks prior to min(tstart, NOW)
        the_msid = self.msid
        if self.other_map is not None:
            for key, value in self.other_map.items():
                if value == self.msid:
                    the_msid = key
                    break
        telem_msids = [the_msid, 'sim_z', 'dp_pitch', 'dp_dpa_power', 'roll']

        # If the calling program has other MSIDs it wishes us to check, add them
        # to the list which is supposed to be grabbed from the engineering archive
        if self.other_telem is not None:
            telem_msids += self.other_telem

        # This is a map of MSIDs
        name_map = {'sim_z': 'tscpos', 'dp_pitch': 'pitch'}
        if self.other_map is not None:
            name_map.update(self.other_map)

        tstart = DateTime(tstart).secs
        start = DateTime(tstart - days * 86400).date
        stop = DateTime(tstart).date
        mylog.info('Fetching telemetry between %s and %s' % (start, stop))
        msidset = fetch.MSIDset(telem_msids, start, stop, stat='5min')
        start = max(x.times[0] for x in msidset.values())
        stop = min(x.times[-1] for x in msidset.values())
        # Interpolate the MSIDs to a common set of times, 5 mins apart (328 s)
        msidset.interpolate(328.0, start, stop + 1)

        # Finished when we found at least 4 good records (20 mins)
        if len(msidset.times) < 4:
            raise ValueError('Found no telemetry within %d days of %s'
                             % (days, str(tstart)))

        # Construct the NumPy record array of telemetry values
        # for the different MSIDs (temperatures, pitch, etc).
        # In some cases we replace the MSID name with something
        # more human-readable.
        outnames = ['date'] + [name_map.get(x, x) for x in telem_msids]
        vals = {name_map.get(x, x): msidset[x].vals for x in telem_msids}
        vals['date'] = msidset.times
        out = Ska.Numpy.structured_array(vals, colnames=outnames)

        # tscpos needs to be converted to steps and must be in the right direction
        out['tscpos'] *= -397.7225924607

        return out
