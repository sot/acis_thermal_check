import os
from pprint import pformat
import re
import time
import pickle
import numpy as np
import Ska.DBI
import Ska.Table
import Ska.Numpy
from Chandra.Time import DateTime
import Chandra.cmd_states as cmd_states
import matplotlib.pyplot as plt
from Ska.Matplotlib import cxctime2plotdate, pointpair, plot_cxctime
import Ska.engarchive.fetch_sci as fetch
import Ska.Sun
import shutil
import glob
import logging

TASK_DATA = os.path.dirname(__file__)

def calc_off_nom_rolls(states):
    off_nom_rolls = []
    for state in states:
        att = [state[x] for x in ['q1', 'q2', 'q3', 'q4']]
        time = (state['tstart'] + state['tstop']) / 2
        off_nom_rolls.append(Ska.Sun.off_nominal_roll(att, time))
    return np.array(off_nom_rolls)

class ModelCheck(object):
    def __init__(self, msid, short_msid, MSIDs, yellow, margin,
                 validation_limits, hist_limit, calc_model,
                 version, other_telem=None, other_map=None,
                 other_opts=None):
        self.msid = msid
        self.short_msid = short_msid
        self.MSIDs = MSIDs
        self.yellow = yellow
        self.margin = margin
        self.validation_limits = validation_limits
        self.hist_limit = hist_limit
        self.calc_model = calc_model
        self.logger = logging.getLogger('%s_check' % self.short_msid)
        self.version = version
        self.other_telem = other_telem
        self.other_map = other_map
        self.other_opts = other_opts

    def driver(self, opt):
        if not os.path.exists(opt.outdir):
            os.mkdir(opt.outdir)

        config_logging(opt.outdir, opt.verbose, self.short_msid)

        # Store info relevant to processing for use in outputs
        proc = dict(run_user=os.environ['USER'],
                    run_time=time.ctime(),
                    errors=[],
                    msid=self.msid.upper(),
                    short_msid=self.short_msid.upper())
        proc["msid_limit"] = self.yellow[self.short_msid] - self.margin[self.short_msid]
        self.logger.info('##############################'
                    '#######################################')
        self.logger.info('# %s_check.py run at %s by %s'
                    % (self.short_msid, proc['run_time'], proc['run_user']))
        self.logger.info('# %s_check version = %s' % (self.short_msid, self.version))
        self.logger.info('# model_spec file = %s' % os.path.abspath(opt.model_spec))
        self.logger.info('###############################'
                    '######################################\n')

        self.logger.info('Command line options:\n%s\n' % pformat(opt.__dict__))

        # Connect to database (NEED TO USE aca_read)
        self.logger.info('Connecting to database to get cmd_states')
        db = Ska.DBI.DBI(dbi='sybase', server='sybase', user='aca_read',
                         database='aca')

        tnow = DateTime(opt.run_start).secs
        if opt.oflsdir is not None:
            # Get tstart, tstop, commands from backstop file in opt.oflsdir
            bs_cmds = self.get_bs_cmds(opt.oflsdir)
            tstart = bs_cmds[0]['time']
            tstop = bs_cmds[-1]['time']

            proc.update(dict(datestart=DateTime(tstart).date,
                             datestop=DateTime(tstop).date))
        else:
            tstart = tnow

        # Get temperature telemetry for 3 weeks prior to min(tstart, NOW)
        telem_msids = [self.msid, 'sim_z', 'aosares1', 'dp_dpa_power']
        if self.other_telem is not None:
            telem_msids += self.other_telem
        name_map = {'sim_z': 'tscpos', 'aosares1': 'pitch'}
        if self.other_map is not None:
            name_map.update(self.other_map)
        tlm = self.get_telem_values(min(tstart, tnow),
                                    telem_msids,
                                    days=opt.days,
                                    name_map=name_map)
        tlm['tscpos'] *= -397.7225924607

        # make predictions on oflsdir if defined
        if opt.oflsdir is not None:
            pred = self.make_week_predict(opt, tstart, tstop, bs_cmds, tlm, db)
        else:
            pred = dict(plots=None, viols=None, times=None, states=None,
                        temps=None)

        # Validation
        URL = "http://cxc.harvard.edu/mta/ASPECT/%s_daily_check" % self.short_msid
        plots_validation = self.make_validation_plots(opt, tlm, db)
        valid_viols = self.make_validation_viols(plots_validation)
        if len(valid_viols) > 0:
            # generate daily plot url if outdir in expected year/day format
            daymatch = re.match('.*(\d{4})/(\d{3})', opt.outdir)
            if opt.oflsdir is None and daymatch:
                url = os.path.join(URL, daymatch.group(1), daymatch.group(2))
                self.logger.info('validation warning(s) at %s' % url)
            else:
                self.logger.info('validation warning(s) in output at %s' % opt.outdir)

        self.write_index_rst(opt, proc, plots_validation, valid_viols=valid_viols,
                        plots=pred['plots'], viols=pred['viols'])
        self.rst_to_html(opt, proc)

        return dict(opt=opt, states=pred['states'], times=pred['times'],
                    temps=pred['temps'], plots=pred['plots'],
                    viols=pred['viols'], proc=proc,
                    plots_validation=plots_validation)

    def make_week_predict(self, opt, tstart, tstop, bs_cmds, tlm, db):
        # Try to make initial state0 from cmd line options
        t_msid = 'T_%s' % self.short_msid
        opts = ['pitch', 'simpos', 'ccd_count', 'fep_count', 'vid_board', 'clocking', t_msid]
        if self.other_opts is not None:
            opts += self.other_opts
        state0 = dict((x, getattr(opt, x)) for x in opts)

        state0.update({'tstart': tstart - 30,
                       'tstop': tstart,
                       'datestart': DateTime(tstart - 30).date,
                       'datestop': DateTime(tstart).date,
                       'q1': 0.0, 'q2': 0.0, 'q3': 0.0, 'q4': 1.0,
                       }
                      )
        
        # If cmd lines options were not fully specified then get state0 as last
        # cmd_state that starts within available telemetry.  Update with the
        # mean temperatures at the start of state0.
        if None in state0.values():
            state0 = self.set_initial_state(tlm, db, t_msid)

        # TEMPORARY HACK: core model doesn't actually support predictive
        # active heater yet.  Initial temperature determines active heater
        # state for predictions now.
        if state0[t_msid] < 15:
            state0[t_msid] = 15.0
    
        self.logger.debug('state0 at %s is\n%s' % (DateTime(state0['tstart']).date,
                                                   pformat(state0)))
    
        # Get commands after end of state0 through first backstop command time
        cmds_datestart = state0['datestop']
        cmds_datestop = bs_cmds[0]['date']
    
        # Get timeline load segments including state0 and beyond.
        timeline_loads = db.fetchall("""SELECT * from timeline_loads
                                     WHERE datestop > '%s'
                                     and datestart < '%s'"""
                                     % (cmds_datestart, cmds_datestop))
        self.logger.info('Found {} timeline_loads  after {}'.format(
                         len(timeline_loads), cmds_datestart))
    
        # Get cmds since datestart within timeline_loads
        db_cmds = cmd_states.get_cmds(cmds_datestart, db=db, update_db=False,
                                      timeline_loads=timeline_loads)
    
        # Delete non-load cmds that are within the backstop time span
        # => Keep if timeline_id is not None or date < bs_cmds[0]['time']
        db_cmds = [x for x in db_cmds if (x['timeline_id'] is not None or
                                          x['time'] < bs_cmds[0]['time'])]
    
        self.logger.info('Got %d cmds from database between %s and %s' %
                         (len(db_cmds), cmds_datestart, cmds_datestop))
    
        # Get the commanded states from state0 through the end of backstop commands
        states = cmd_states.get_states(state0, db_cmds + bs_cmds)
        states[-1].datestop = bs_cmds[-1]['date']
        states[-1].tstop = bs_cmds[-1]['time']
        self.logger.info('Found %d commanded states from %s to %s' %
                         (len(states), states[0]['datestart'], states[-1]['datestop']))
    
        # Create array of times at which to calculate temps, then do it.
        self.logger.info('Calculating %s thermal model' % self.short_msid.upper())

        return self.run_model_make_plots(opt, states, state0, tstart, tstop, t_msid)

    def set_initial_state(self, tlm, db, t_msid):
        state0 = cmd_states.get_state0(tlm['date'][-5], db,
                                           datepar='datestart')
        ok = ((tlm['date'] >= state0['tstart'] - 700) &
              (tlm['date'] <= state0['tstart'] + 700))
        state0.update({t_msid: np.mean(tlm[self.msid][ok])})
        return state0

    def run_model_make_plots(self, opt, states, state0, tstart, tstop, t_msid):
        model = self.calc_model(opt.model_spec, states, state0['tstart'], tstop,
                                state0[t_msid])
        # Make the limit check plots and data files
        plt.rc("axes", labelsize=10, titlesize=12)
        plt.rc("xtick", labelsize=10)
        plt.rc("ytick", labelsize=10)
        temps = {self.short_msid: model.comp[self.msid].mvals}
        plots = self.make_check_plots(opt, states, model.times, temps, tstart)
        viols = self.make_viols(opt, states, model.times, temps)
        self.write_states(opt, states)
        self.write_temps(opt, model.times, temps)

        return dict(opt=opt, states=states, times=model.times, temps=temps,
                    plots=plots, viols=viols)

    def make_validation_viols(self, plots_validation):
        """
        Find limit violations where MSID quantile values are outside the
        allowed range.
        """
    
        self.logger.info('Checking for validation violations')
    
        viols = []
    
        for plot in plots_validation:
            # 'plot' is actually a structure with plot info and stats about the
            #  plotted data for a particular MSID.  'msid' can be a real MSID
            #  (1DEAMZT) or pseudo like 'POWER'
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
                    self.logger.info('WARNING: %s %d%% quantile value of %s exceeds '
                                     'limit of %.2f' %
                                     (msid, quantile, msid_quantile_value, limit))
    
        return viols

    def make_viols(self, opt, states, times, temps):
        """
        Find limit violations where predicted temperature is above the
        yellow limit minus margin.
        """
        self.logger.info('Checking for limit violations')

        viols = dict((x, []) for x in self.MSIDs)
        for msid in self.MSIDs:
            temp = temps[msid]
            plan_limit = self.yellow[msid] - self.margin[msid]
            bad = np.concatenate(([False], temp >= plan_limit, [False]))
            changes = np.flatnonzero(bad[1:] != bad[:-1]).reshape(-1, 2)
            for change in changes:
                viol = {'datestart': DateTime(times[change[0]]).date,
                        'datestop': DateTime(times[change[1] - 1]).date,
                        'maxtemp': temp[change[0]:change[1]].max()
                        }
                self.logger.info('WARNING: %s exceeds planning limit of %.2f '
                                 'degC from %s to %s'
                                 % (self.MSIDs[msid], plan_limit, viol['datestart'],
                                    viol['datestop']))
                viols[msid].append(viol)

        viols["default"] = viols[self.short_msid]

        return viols

    def write_states(self, opt, states):
        """Write states recarray to file states.dat"""
        outfile = os.path.join(opt.outdir, 'states.dat')
        self.logger.info('Writing states to %s' % outfile)
        out = open(outfile, 'w')
        fmt = {'power': '%.1f',
               'pitch': '%.2f',
               'tstart': '%.2f',
               'tstop': '%.2f',
               }
        newcols = list(states.dtype.names)
        newcols.remove('T_%s' % self.short_msid)
        newstates = np.rec.fromarrays([states[x] for x in newcols], names=newcols)
        Ska.Numpy.pprint(newstates, fmt, out)
        out.close()

    def write_temps(self, opt, times, temps):
        """Write temperature predictions to file temperatures.dat"""
        outfile = os.path.join(opt.outdir, 'temperatures.dat')
        self.logger.info('Writing temperatures to %s' % outfile)
        T = temps[self.short_msid]
        temp_recs = [(times[i], DateTime(times[i]).date, T[i])
                     for i in range(len(times))]
        temp_array = np.rec.fromrecords(
            temp_recs, names=('time', 'date', self.msid))

        fmt = {self.msid: '%.2f',
               'time': '%.2f'}
        out = open(outfile, 'w')
        Ska.Numpy.pprint(temp_array, fmt, out)
        out.close()

    def make_check_plots(self, opt, states, times, temps, tstart):
        """
        Make output plots.

        :param opt: options
        :param states: commanded states
        :param times: time stamps (sec) for temperature arrays
        :param temps: dict of temperatures
        :param tstart: load start time
        :rtype: dict of review information including plot file names
        """
        plots = {}

        # Start time of loads being reviewed expressed in units for plotdate()
        load_start = cxctime2plotdate([tstart])[0]

        self.logger.info('Making temperature check plots')
        for fig_id, msid in enumerate((self.short_msid,)):
            plots[msid] = plot_two(fig_id=fig_id + 1,
                                   x=times,
                                   y=temps[msid],
                                   x2=pointpair(states['tstart'], states['tstop']),
                                   y2=pointpair(states['pitch']),
                                   title=self.MSIDs[msid],
                                   xlabel='Date',
                                   ylabel='Temperature (C)',
                                   ylabel2='Pitch (deg)',
                                   ylim2=(40, 180),
                                   )
            plots[msid]['ax'].axhline(self.yellow[msid], linestyle='-', color='y',
                                      linewidth=2.0)
            plots[msid]['ax'].axhline(self.yellow[msid] - self.margin[msid], linestyle='--',
                                      color='y', linewidth=2.0)
            plots[msid]['ax'].axvline(load_start, linestyle=':', color='g',
                                      linewidth=1.0)
            filename = self.MSIDs[self.short_msid].lower() + '.png'
            outfile = os.path.join(opt.outdir, filename)
            self.logger.info('Writing plot file %s' % outfile)
            plots[msid]['fig'].savefig(outfile)
            plots[msid]['filename'] = filename

        plots['pow_sim'] = plot_two(
            fig_id=3,
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
            figsize=(7.5, 3.5),
            )
        plots['pow_sim']['ax'].axvline(load_start, linestyle=':', color='g',
                                       linewidth=1.0)
        # The next several lines ensure that the width of the axes
        # of all the weekly prediction plots are the same.
        w1, h1 = plots[self.short_msid]['fig'].get_size_inches()
        w2, h2 = plots['pow_sim']['fig'].get_size_inches()
        lm = plots[self.short_msid]['fig'].subplotpars.left*w1/w2
        rm = plots[self.short_msid]['fig'].subplotpars.right*w1/w2
        plots['pow_sim']['fig'].subplots_adjust(left=lm, right=rm)
        filename = 'pow_sim.png'
        outfile = os.path.join(opt.outdir, filename)
        self.logger.info('Writing plot file %s' % outfile)
        plots['pow_sim']['fig'].savefig(outfile)
        plots['pow_sim']['filename'] = filename

        plots['default'] = plots[self.short_msid]

        return plots

    def make_validation_plots(self, opt, tlm, db):
        """
        Make validation output plots.

        :param tlm: telemetry
        :param db: database handle
        :returns: list of plot info including plot file names
        """
        outdir = opt.outdir
        start = tlm['date'][0]
        stop = tlm['date'][-1]
        states = self.get_states(start, stop, db)

        # Create array of times at which to calculate temperatures, then do it
        self.logger.info('Calculating %s thermal model for validation' % self.short_msid.upper())

        model = self.calc_model(opt.model_spec, states, start, stop)

        # Interpolate states onto the tlm.date grid
        # state_vals = cmd_states.interpolate_states(states, model.times)
        pred = {self.msid: model.comp[self.msid].mvals,
                'pitch': model.comp['pitch'].mvals,
                'tscpos': model.comp['sim_z'].mvals
                }

        idxs = Ska.Numpy.interpolate(np.arange(len(tlm)), tlm['date'], model.times,
                                     method='nearest')
        tlm = tlm[idxs]

        labels = {self.msid: 'Degrees (C)',
                  'pitch': 'Pitch (degrees)',
                  'tscpos': 'SIM-Z (steps/1000)',
                  }

        scales = {'tscpos': 1000.}

        fmts = {self.msid: '%.2f',
                'pitch': '%.3f',
                'tscpos': '%d'}

        good_mask = np.ones(len(tlm), dtype='bool')
        if hasattr(model, "bad_times"):
            for interval in model.bad_times:
                bad = ((tlm['date'] >= DateTime(interval[0]).secs)
                    & (tlm['date'] < DateTime(interval[1]).secs))
                good_mask[bad] = False

        plots = []
        self.logger.info('Making %s model validation plots and quantile table' % self.short_msid.upper())
        quantiles = (1, 5, 16, 50, 84, 95, 99)
        # store lines of quantile table in a string and write out later
        quant_table = ''
        quant_head = ",".join(['MSID'] + ["quant%d" % x for x in quantiles])
        quant_table += quant_head + "\n"
        for fig_id, msid in enumerate(sorted(pred)):
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
            filename = msid + '_valid.png'
            outfile = os.path.join(outdir, filename)
            self.logger.info('Writing plot file %s' % outfile)
            fig.savefig(outfile)
            plot['lines'] = filename

            # Make quantiles
            if msid == self.msid:
                ok = ((tlm[msid] > self.hist_limit[0]) & good_mask)
            else:
                ok = np.ones(len(tlm[msid]), dtype=bool)
            diff = np.sort(tlm[msid][ok] - pred[msid][ok])
            if len(self.hist_limit) == 2:
                if msid == self.msid:
                    ok2 = ((tlm[msid] > 40.0) & good_mask)
                else:
                    ok2 = np.ones(len(tlm[msid]), dtype=bool)
                diff2 = np.sort(tlm[msid][ok2] - pred[msid][ok2])
            quant_line = "%s" % msid
            for quant in quantiles:
                quant_val = diff[(len(diff) * quant) // 100]
                plot['quant%02d' % quant] = fmts[msid] % quant_val
                quant_line += (',' + fmts[msid] % quant_val)
            quant_table += quant_line + "\n"

            for histscale in ('log', 'lin'):
                fig = plt.figure(20 + fig_id, figsize=(4, 3))
                fig.clf()
                ax = fig.gca()
                ax.hist(diff / scale, bins=50, log=(histscale == 'log'))
                if msid == self.msid and len(self.hist_limit) == 2:
                    ax.hist(diff2 / scale, bins=50, log=(histscale == 'log'),
                            color = 'red')
                ax.set_title(msid.upper() + ' residuals: data - model')
                ax.set_xlabel(labels[msid])
                fig.subplots_adjust(bottom=0.18)
                filename = '%s_valid_hist_%s.png' % (msid, histscale)
                outfile = os.path.join(outdir, filename)
                self.logger.info('Writing plot file %s' % outfile)
                fig.savefig(outfile)
                plot['hist' + histscale] = filename

            plots.append(plot)

        filename = os.path.join(outdir, 'validation_quant.csv')
        self.logger.info('Writing quantile table %s' % filename)
        f = open(filename, 'w')
        f.write(quant_table)
        f.close()

        # If run_start is specified this is likely for regression testing
        # or other debugging.  In this case write out the full predicted and
        # telemetered dataset as a pickle.
        if opt.run_start:
            filename = os.path.join(outdir, 'validation_data.pkl')
            self.logger.info('Writing validation data %s' % filename)
            f = open(filename, 'w')
            pickle.dump({'pred': pred, 'tlm': tlm}, f, protocol=-1)
            f.close()

        return plots

    def rst_to_html(self, opt, proc):
        """Run rst2html.py to render index.rst as HTML"""

        # First copy CSS files to outdir
        import Ska.Shell
        import docutils.writers.html4css1
        dirname = os.path.dirname(docutils.writers.html4css1.__file__)
        shutil.copy2(os.path.join(dirname, 'html4css1.css'), opt.outdir)

        shutil.copy2(os.path.join(TASK_DATA, 'model_check.css'), opt.outdir)

        spawn = Ska.Shell.Spawn(stdout=None)
        infile = os.path.join(opt.outdir, 'index.rst')
        outfile = os.path.join(opt.outdir, 'index.html')
        status = spawn.run(['rst2html.py',
                            '--stylesheet-path={}'
                            .format(os.path.join(opt.outdir, 'model_check.css')),
                            infile, outfile])
        if status != 0:
            proc['errors'].append('rst2html.py failed with status {}: see run log'
                                  .format(status))
            self.logger.error('rst2html.py failed')
            self.logger.error(''.join(spawn.outlines) + '\n')

        # Remove the stupid <colgroup> field that docbook inserts.  This
        # <colgroup> prevents HTML table auto-sizing.
        del_colgroup = re.compile(r'<colgroup>.*?</colgroup>', re.DOTALL)
        outtext = del_colgroup.sub('', open(outfile).read())
        open(outfile, 'w').write(outtext)

    def write_index_rst(self, opt, proc, plots_validation, valid_viols=None,
                        plots=None, viols=None):
        """
        Make output text (in ReST format) in opt.outdir.
        """
        # Django setup (used for template rendering)
        import django.template
        import django.conf
        try:
            django.conf.settings.configure()
        except RuntimeError, msg:
            print msg

        outfile = os.path.join(opt.outdir, 'index.rst')
        self.logger.info('Writing report file %s' % outfile)
        django_context = django.template.Context(
            {'opt': opt,
             'plots': plots,
             'viols': viols,
             'valid_viols': valid_viols,
             'proc': proc,
             'plots_validation': plots_validation,
             })
        index_template_file = ('index_template.rst'
                               if opt.oflsdir else
                               'index_template_val_only.rst')
        index_template = open(os.path.join(TASK_DATA, index_template_file)).read()
        index_template = re.sub(r' %}\n', ' %}', index_template)
        template = django.template.Template(index_template)
        open(outfile, 'w').write(template.render(django_context))

    def get_states(self, datestart, datestop, db):
        """Get states exactly covering date range

        :param datestart: start date
        :param datestop: stop date
        :param db: database handle
        :returns: np recarry of states
        """
        datestart = DateTime(datestart).date
        datestop = DateTime(datestop).date
        self.logger.info('Getting commanded states between %s - %s' %
                     (datestart, datestop))

        # Get all states that intersect specified date range
        cmd = """SELECT * FROM cmd_states
                 WHERE datestop > '%s' AND datestart < '%s'
                 ORDER BY datestart""" % (datestart, datestop)
        self.logger.debug('Query command: %s' % cmd)
        states = db.fetchall(cmd)
        self.logger.info('Found %d commanded states' % len(states))

        # Set start and end state date/times to match telemetry span.  Extend the
        # state durations by a small amount because of a precision issue converting
        # to date and back to secs.  (The reference tstop could be just over the
        # 0.001 precision of date and thus cause an out-of-bounds error when
        # interpolating state values).
        states[0].tstart = DateTime(datestart).secs - 0.01
        states[0].datestart = DateTime(states[0].tstart).date
        states[-1].tstop = DateTime(datestop).secs + 0.01
        states[-1].datestop = DateTime(states[-1].tstop).date

        return states

    def get_bs_cmds(self, oflsdir):
        """Return commands for the backstop file in opt.oflsdir.
        """
        import Ska.ParseCM
        backstop_file = globfile(os.path.join(oflsdir, 'CR*.backstop'))
        self.logger.info('Using backstop file %s' % backstop_file)
        bs_cmds = Ska.ParseCM.read_backstop(backstop_file)
        self.logger.info('Found %d backstop commands between %s and %s' %
                         (len(bs_cmds), bs_cmds[0]['date'], bs_cmds[-1]['date']))
        return bs_cmds

    def get_telem_values(self, tstart, msids, days=14, name_map={}):
        """
        Fetch last ``days`` of available ``msids`` telemetry values before
        time ``tstart``.

        :param tstart: start time for telemetry (secs)
        :param msids: fetch msids list
        :param days: length of telemetry request before ``tstart``
        :param dt: sample time (secs)
        :param name_map: dict mapping msid to recarray col name
        :returns: np recarray of requested telemetry values from fetch
        """
        tstart = DateTime(tstart).secs
        start = DateTime(tstart - days * 86400).date
        stop = DateTime(tstart).date
        self.logger.info('Fetching telemetry between %s and %s' % (start, stop))
        msidset = fetch.MSIDset(msids, start, stop, stat='5min')
        start = max(x.times[0] for x in msidset.values())
        stop = min(x.times[-1] for x in msidset.values())
        msidset.interpolate(328.0, start, stop + 1)  # 328 for '5min' stat

        # Finished when we found at least 4 good records (20 mins)
        if len(msidset.times) < 4:
            raise ValueError('Found no telemetry within %d days of %s'
                             % (days, str(tstart)))

        outnames = ['date'] + [name_map.get(x, x) for x in msids]
        vals = {name_map.get(x, x): msidset[x].vals for x in msids}
        vals['date'] = msidset.times
        out = Ska.Numpy.structured_array(vals, colnames=outnames)

        return out


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
