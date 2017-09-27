import os
import Ska.DBI
from Chandra.Time import DateTime
from pprint import pformat
import Chandra.cmd_states as cmd_states
import numpy as np
from acis_thermal_check.utils import globfile

class StateBuilder(object):
    def __init__(self, thermal_check):
        self.thermal_check = thermal_check
        self.logger = self.thermal_check.logger

    def set_options(self, args):
        self.args = args

class LegacyStateBuilder(StateBuilder):
    def set_options(self, args):
        # Connect to database (NEED TO USE aca_read for sybase; user is ignored for sqlite)
        server = ('sybase' if args.cmd_states_db == 'sybase' else
                  os.path.join(os.environ['SKA'], 'data', 'cmd_states', 'cmd_states.db3'))
        self.logger.info('Connecting to {} to get cmd_states'.format(server))
        self.db = Ska.DBI.DBI(dbi=args.cmd_states_db, server=server, user='aca_read',
                              database='aca')
        super(LegacyStateBuilder, self).set_options(args)

    def get_bs_cmds(self):
        """
        Return commands for the backstop file in opt.backstop_file.
        """
        import Ska.ParseCM
        if os.path.isdir(self.args.backstop_file):
            backstop_file = globfile(os.path.join(self.args.backstop_file, 
                                                  'CR*.backstop'))
        else:
            backstop_file = self.args.backstop_file
        self.logger.info('Using backstop file %s' % backstop_file)
        bs_cmds = Ska.ParseCM.read_backstop(backstop_file)
        self.logger.info('Found %d backstop commands between %s and %s' %
                         (len(bs_cmds), bs_cmds[0]['date'], bs_cmds[-1]['date']))
        self.bs_cmds = bs_cmds
        return bs_cmds

    def set_initial_state(self, tlm):
        """
        Get the initial state corresponding to the end of available telemetry (minus a
        bit).

        The original logic in get_state0() is to return a state that is absolutely,
        positively reliable by insisting that the returned state is at least
        ``date_margin`` days old, where the default is 10 days.  That is too conservative
        (given the way commanded states are actually managed) and not what is desired
        here, which is a recent state from which to start thermal propagation.

        Instead we supply ``date_margin=None`` so that get_state0 will find the newest
        state consistent with the ``date`` criterion and pcad_mode == 'NPNT'.
        """
        state0 = cmd_states.get_state0(DateTime(tlm['date'][-5]).date, self.db,
                                       datepar='datestart', date_margin=None)
        ok = ((tlm['date'] >= state0['tstart'] - 700) &
              (tlm['date'] <= state0['tstart'] + 700))
        state0.update({self.thermal_check.t_msid: np.mean(tlm[self.thermal_check.msid][ok])})

        return state0

    def get_predict_states(self, opt, tlm, tstart, tstop):
        # Try to make initial state0 from cmd line options
        opts = ['pitch', 'simpos', 'ccd_count', 'fep_count',
                'vid_board', 'clocking', self.thermal_check.t_msid]
        # self.other_opts will be filled from specific model tools
        if self.thermal_check.other_opts is not None:
            opts += self.thermal_check.other_opts

        # Create the initial state in state0, attempting to use the values from the
        # command line. We set this up with an initial dummy quaternion and a
        # 30-second state duration.
        state0 = dict((x, getattr(opt, x)) for x in opts)
        state0.update({'tstart': tstart - 30,
                       'tstop': tstart,
                       'datestart': DateTime(tstart - 30).date,
                       'datestop': DateTime(tstart).date,
                       'q1': 0.0, 'q2': 0.0, 'q3': 0.0, 'q4': 1.0})

        # If command-line options were not fully specified then get state0 as last
        # cmd_state that starts within available telemetry. We also add to this
        # dict the mean temperature at the start of state0.
        if None in state0.values():
            state0 = self.set_initial_state(tlm)

        self.logger.debug('state0 at %s is\n%s' % (DateTime(state0['tstart']).date,
                          pformat(state0)))

        # Get commands after end of state0 through first backstop command time
        cmds_datestart = state0['datestop']
        cmds_datestop = self.bs_cmds[0]['date']

        # Get timeline load segments including state0 and beyond.
        timeline_loads = self.db.fetchall("""SELECT * from timeline_loads
                                          WHERE datestop > '%s'
                                          and datestart < '%s'"""
                                          % (cmds_datestart, cmds_datestop))
        self.logger.info('Found {} timeline_loads  after {}'.format(
                         len(timeline_loads), cmds_datestart))

        # Get cmds since datestart within timeline_loads
        db_cmds = cmd_states.get_cmds(cmds_datestart, db=self.db, update_db=False,
                                      timeline_loads=timeline_loads)

        # Delete non-load cmds that are within the backstop time span
        # => Keep if timeline_id is not None or date < bs_cmds[0]['time']
        db_cmds = [x for x in db_cmds if x['time'] < self.bs_cmds[0]['time']]

        self.logger.info('Got %d cmds from database between %s and %s' %
                         (len(db_cmds), cmds_datestart, cmds_datestop))

        # Get the commanded states from state0 through the end of backstop commands
        states = cmd_states.get_states(state0, db_cmds + self.bs_cmds)
        states[-1].datestop = self.bs_cmds[-1]['date']
        states[-1].tstop = self.bs_cmds[-1]['time']
        self.logger.info('Found %d commanded states from %s to %s' %
                         (len(states), states[0]['datestart'], states[-1]['datestop']))

        return states, state0

    def get_validation_states(self, datestart, datestop):
        """
        Get states exactly covering date range

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
        states = self.db.fetchall(cmd)
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

class ACISStateBuilder(StateBuilder):
    def __init__(self, thermal_check):
        raise NotImplementedError

state_builders = {"legacy": LegacyStateBuilder,
                  "acis": ACISStateBuilder}
