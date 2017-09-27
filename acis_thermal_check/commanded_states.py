import os
import Ska.DBI
from Chandra.Time import DateTime
from pprint import pformat
import Chandra.cmd_states as cmd_states

class CommandedStates(object):
    def __init__(self, states):
        self.states = states

    def __getitem__(self, item):
        return self.states[item]

class StatesFromDatabase(CommandedStates):
    def __init__(self, thermal_check, opt, tstart, tstop):

        # Connect to database (NEED TO USE aca_read for sybase; user is ignored for sqlite)
        server = ('sybase' if opt.cmd_states_db == 'sybase' else
                  os.path.join(os.environ['SKA'], 'data', 'cmd_states', 'cmd_states.db3'))
        thermal_check.logger.info('Connecting to {} to get cmd_states'.format(server))
        db = Ska.DBI.DBI(dbi=opt.cmd_states_db, server=server, user='aca_read',
                         database='aca')

        # Try to make initial state0 from cmd line options
        opts = ['pitch', 'simpos', 'ccd_count', 'fep_count',
                'vid_board', 'clocking', thermal_check.t_msid]
        # self.other_opts will be filled from specific model tools
        if thermal_check.other_opts is not None:
            opts += thermal_check.other_opts

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
            state0 = thermal_check.set_initial_state(tlm, db)

        thermal_check.logger.debug('state0 at %s is\n%s' % (DateTime(state0['tstart']).date,
                                   pformat(state0)))

        # Get commands after end of state0 through first backstop command time
        cmds_datestart = state0['datestop']
        cmds_datestop = bs_cmds[0]['date']

        # Get timeline load segments including state0 and beyond.
        timeline_loads = db.fetchall("""SELECT * from timeline_loads
                                     WHERE datestop > '%s'
                                     and datestart < '%s'"""
                                     % (cmds_datestart, cmds_datestop))
        thermal_check.logger.info('Found {} timeline_loads  after {}'.format(
                                  len(timeline_loads), cmds_datestart))

        # Get cmds since datestart within timeline_loads
        db_cmds = cmd_states.get_cmds(cmds_datestart, db=db, update_db=False,
                                      timeline_loads=timeline_loads)

        # Delete non-load cmds that are within the backstop time span
        # => Keep if timeline_id is not None or date < bs_cmds[0]['time']
        db_cmds = [x for x in db_cmds if x['time'] < bs_cmds[0]['time']]

        thermal_check.logger.info('Got %d cmds from database between %s and %s' %
                                  (len(db_cmds), cmds_datestart, cmds_datestop))

        # Get the commanded states from state0 through the end of backstop commands
        states = cmd_states.get_states(state0, db_cmds + bs_cmds)
        states[-1].datestop = bs_cmds[-1]['date']
        states[-1].tstop = bs_cmds[-1]['time']
        thermal_check.logger.info('Found %d commanded states from %s to %s' %
                                  (len(states), states[0]['datestart'], states[-1]['datestop']))

        super(StatesFromDatabase, self).__init__(states)

class StatesFromBackstop(CommandedStates):
    def __init__(self):
        states = {}
        super(StatesFromDatabase, self).__init__(states)
