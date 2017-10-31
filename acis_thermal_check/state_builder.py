import os
import Ska.DBI
from Chandra.Time import DateTime
from pprint import pformat
import Chandra.cmd_states as cmd_states
import logging
from Ska.File import get_globfiles

class StateBuilder(object):
    """
    This is the base class for all StateBuilder objects. It
    should not be used by itself, but subclassed.
    """
    def __init__(self, logger=None):
        if logger is None:
            # Make a logger but with no output
            logger = logging.getLogger('statebuilder-no-logger')
        self.logger = logger

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
    def __init__(self, interrupt=False, backstop_file=None, 
                 cmd_states_db="sybase", logger=None):
        """
        Give the SQLStateBuilder arguments that were passed in 
        from the command line, and set up the connection to the 
        commanded states database.

        Parameters
        ----------
        interrupt : boolean
            If True, this is an interrupt load.
        backstop_file : string
            Path to the backstop file. If a directory, the backstop 
            file will be searched for within this directory.
        cmd_states_db : string
            Commanded states database server (sybase|sqlite). Default:
            sybase
        logger : Logger object, optional
            The Python Logger object to be used when logging.
        """
        super(SQLStateBuilder, self).__init__(logger=logger)
        self.interrupt = interrupt
        self.backstop_file = backstop_file
        # Connect to database (NEED TO USE aca_read for sybase; user is ignored for sqlite)
        server = ('sybase' if cmd_states_db == 'sybase' else
                  os.path.join(os.environ['SKA'], 'data', 'cmd_states', 'cmd_states.db3'))
        self.logger.info('Connecting to {} to get cmd_states'.format(server))
        self.db = Ska.DBI.DBI(dbi=cmd_states_db, server=server, user='aca_read',
                              database='aca')
        if self.backstop_file is not None:
            self._get_bs_cmds()

    def _get_bs_cmds(self):
        """
        Internal method used to obtain commands from the backstop 
        file and store them.
        """
        import Ska.ParseCM
        if os.path.isdir(self.backstop_file):
            # Returns a list but requires exactly 1 match
            backstop_file = get_globfiles(os.path.join(self.backstop_file,
                                                       'CR*.backstop'))[0]
        else:
            backstop_file = self.backstop_file
        self.logger.info('Using backstop file %s' % backstop_file)
        bs_cmds = Ska.ParseCM.read_backstop(backstop_file)
        self.logger.info('Found %d backstop commands between %s and %s' %
                         (len(bs_cmds), bs_cmds[0]['date'], bs_cmds[-1]['date']))
        self.bs_cmds = bs_cmds
        self.tstart = bs_cmds[0]['time']
        self.tstop = bs_cmds[-1]['time']

    def get_prediction_states(self, tbegin):
        """
        Get the states used for the prediction.

        Parameters
        ----------
        tbegin : string
            The starting date/time from which to obtain states for
            prediction.
        """

        """
        Get state0 as last cmd_state that starts within available telemetry. 
        The original logic in get_state0() is to return a state that
        is absolutely, positively reliable by insisting that the
        returned state is at least ``date_margin`` days old, where the
        default is 10 days. That is too conservative (given the way
        commanded states are actually managed) and not what is desired
        here, which is a recent state from which to start thermal propagation.

        Instead we supply ``date_margin=None`` so that get_state0 will
        find the newest state consistent with the ``date`` criterion
        and pcad_mode == 'NPNT'.
        """

        state0 = cmd_states.get_state0(tbegin, self.db, datepar='datestart',
                                       date_margin=None)

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
        interrupt = self.interrupt and self.bs_cmds[0]["time"] > current_time

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
                         (len(states), states[0]['datestart'], 
                          states[-1]['datestop']))

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
    def __init__(self, logger=None):
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
