import os
import Ska.DBI
from Chandra.Time import DateTime
from pprint import pformat
import Chandra.cmd_states as cmd_states
import numpy as np
from acis_thermal_check.utils import globfile

class StateBuilder(object):
    """
    This is the base class for all StateBuilder objects. It
    should not be used by itself, but subclassed.

    Parameters
    ----------
    thermal_check : :class:`~acis_thermal_check.main.ACISThermalCheck` object
        The ACISThermalCheck object this StateBuilder is attached to.
    """
    def __init__(self, thermal_check):
        self.thermal_check = thermal_check
        self.logger = self.thermal_check.logger

    def set_options(self, args):
        """
        Give the StateBuilder arguments that were passed in
        from the command line

        Subclasses may want to overload this to do other things
        with the arguments. 

        Parameters
        ----------
        args : ArgumentParser object
            Command line arguments
        """
        self.args = args

    def get_prediction_states(self, tlm):
        """
        Get the states used for the thermal prediction.

        Parameters
        ----------
        tlm : dictionary
            Dictionary containg temperature and other telemetry
        """
        raise NotImplementedError("'StateBuilder should be subclassed!")

    def get_validation_states(self, datestart, datestop):
        """
        Get states for validation of the thermal model.

        Parameters
        ----------
        datestart : string
            The start date to grab states afterward.
        datestop : string
            The end date to grab states before.
        """
        raise NotImplementedError("'StateBuilder should be subclassed!")

class SQLStateBuilder(StateBuilder):
    """
    The SQLStateBuilder contains the original code used to 
    obtain commanded states for prediction and validation of
    a thermal model for a particular command load. It can also
    be used for validation only.
    """
    def set_options(self, args):
        """
        Give the SQLStateBuilder arguments that were passed in 
        from the command line, and set up the connection to the 
        commanded states database

        Parameters
        ----------
        args : ArgumentParser object
            Command line arguments
        """
        # Connect to database (NEED TO USE aca_read for sybase; user is ignored for sqlite)
        server = ('sybase' if args.cmd_states_db == 'sybase' else
                  os.path.join(os.environ['SKA'], 'data', 'cmd_states', 'cmd_states.db3'))
        self.logger.info('Connecting to {} to get cmd_states'.format(server))
        self.db = Ska.DBI.DBI(dbi=args.cmd_states_db, server=server, user='aca_read',
                              database='aca')
        super(SQLStateBuilder, self).set_options(args)
        if self.args.backstop_file is not None:
            self._get_bs_cmds()

    def _get_bs_cmds(self):
        """
        Internal method used to btain commands from the backstop 
        file and store them.
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
        self.tstart = bs_cmds[0]['time']
        self.tstop = bs_cmds[-1]['time']

    def _set_initial_state(self, tlm):
        """
        Internal method used to get the initial state corresponding 
        to the end of available telemetry (minus a bit).

        The original logic in get_state0() is to return a state that 
        is absolutely, positively reliable by insisting that the 
        returned state is at least ``date_margin`` days old, where the 
        default is 10 days. That is too conservative (given the way 
        commanded states are actually managed) and not what is desired
        here, which is a recent state from which to start thermal propagation.

        Instead we supply ``date_margin=None`` so that get_state0 will 
        find the newest state consistent with the ``date`` criterion 
        and pcad_mode == 'NPNT'.

        Parameters
        ----------
        tlm : dictionary
            Dictionary containg temperature and other telemetry
        """
        # The -5 here has us back off from the last telemetry reading just a bit
        start = DateTime(tlm['date'][-5])
        state0 = cmd_states.get_state0(start.date, self.db, datepar='datestart', 
                                       date_margin=None)

        if self.args.T_init is not None:
            # If we have an initial temperature input from the
            # command line, use it
            T_init = self.args.T_init
        else:
            # Otherwise, construct T_init from the last 10 samples 
            # of available telemetry
            ok = ((tlm['date'] >= state0['tstart'] - 700) &
                  (tlm['date'] <= state0['tstart'] + 700))
            T_init = np.mean(tlm[self.thermal_check.msid][ok])

        state0.update({self.thermal_check.t_msid: T_init})

        return state0

    def get_prediction_states(self, tlm):
        """
        Get the states used for the thermal prediction.

        Parameters
        ----------
        tlm : dictionary
            Dictionary containg temperature and other telemetry
        """
        # Get state0 as last cmd_state that starts within available telemetry. 
        # We also add to this dict the mean temperature at the start of state0.
        state0 = self._set_initial_state(tlm)

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
        # => Keep if timeline_id is not None (if a normal load)
        # or date < bs_cmds[0]['time']

        # If this is an interrupt load, we don't want to include the end 
        # commands from the continuity load since not all of them will be valid,
        # and we could end up evolving on states which would not be present in 
        # the load under review. However, once the load has been approved and is
        # running / has run on the spacecraft, the states in the database will 
        # be correct, and we will want to include all relevant commands from the
        # continuity load. To check for this, we find the current time and see 
        # the load under review is still in the future. If it is, we then treat
        # this as an interrupt if requested, otherwise, we don't. 
        current_time = DateTime().secs
        interrupt = self.args.interrupt and self.bs_cmds[0]["time"] > current_time

        db_cmds = [x for x in db_cmds
                   if ((x['timeline_id'] is not None and not interrupt) or
                       x['time'] < self.bs_cmds[0]['time'])]

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
        Get states for validation of the thermal model.

        Parameters
        ----------
        datestart : string
            The start date to grab states afterward.
        datestop : string
            The end date to grab states before.
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

class HDF5StateBuilder(StateBuilder):
    """
    The HDF5StateBuilder obtains states from the commanded
    states database using Chandra.cmd_states.fetch_states.
    It can only be used for model validation and not prediction,
    since this database is only updated after load products
    are approved.
    """
    def get_prediction_states(self, tlm):
        """
        Get the states used for the thermal prediction.
        NOT IMPLEMENTED for HDF5StateBuilder.

        Parameters
        ----------
        tlm : dictionary
            Dictionary containg temperature and other telemetry
        """
        raise NotImplementedError("The 'hdf5' state builder can only "
                                  "be used for validation, not prediction!")

    def get_validation_states(self, datestart, datestop):
        """
        Get states for validation of the thermal model.

        Parameters
        ----------
        datestart : string
            The start date to grab states afterward.
        datestop : string
            The end date to grab states before.
        """
        datestart = DateTime(datestart).date
        datestop = DateTime(datestop).date
        self.logger.info('Getting commanded states between %s - %s' %
                         (datestart, datestop))
        return cmd_states.fetch_states(datestart, datestop)

state_builders = {"sql": SQLStateBuilder,
                  "acis": ACISStateBuilder,
                  "hdf5": HDF5StateBuilder}
