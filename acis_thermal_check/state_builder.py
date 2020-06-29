import os
import numpy as np
import Ska.DBI
from Chandra.Time import DateTime
from pprint import pformat
import kadi.commands
import kadi.commands.states as kadi_states
import logging
from Ska.File import get_globfiles

STATE_KEYS = ['ccd_count', 'clocking', 'dec', 'dither',
              'fep_count', 'hetg', 'letg', 'obsid', 'pcad_mode', 'pitch',
              'power_cmd', 'q1', 'q2', 'q3', 'q4', 'ra', 'roll', 'si_mode',
              'simfa_pos', 'simpos',
              'vid_board']


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

    def _get_bs_cmds(self):
        """
        Internal method used to obtain commands from the backstop
        file and store them.
        """
        if os.path.isdir(self.backstop_file):
            # Returns a list but requires exactly 1 match
            backstop_file = get_globfiles(os.path.join(self.backstop_file,
                                                       'CR*.backstop'))[0]
            self.backstop_file = backstop_file

        self.logger.info('Using backstop file %s' % self.backstop_file)

        # Read the backstop commands and add a `time` column
        bs_cmds = kadi.commands.get_cmds_from_backstop(backstop_file)

        # Handle the special case of old loads (prior to backstop 6.9 in April
        # 2020) where there is no RLTT and the first command is AOACRSTD. This
        # indicates the beginning of a maneuver ATS which may overlap by 3 mins
        # with the previous loads because of the AOACRSTD command. So to get
        # continuity right just drop that command.
        if (bs_cmds[0]['tlmsid'] == 'AOACRSTD'
                and 'RUNNING_LOAD_TERMINATION_TIME' not in bs_cmds['event_type']):
            bs_cmds = bs_cmds[1:]

        bs_cmds['time'] = DateTime(bs_cmds['date']).secs

        self.bs_cmds = bs_cmds
        self.tstart = bs_cmds[0]['time']
        self.tstop = bs_cmds[-1]['time']

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
        start = DateTime(datestart)
        stop = DateTime(datestop)
        self.logger.info('Getting commanded states between %s - %s' %
                         (start.date, stop.date))

        states = kadi_states.get_states(start, stop, state_keys=STATE_KEYS,
                                        merge_identical=True)

        # Set start and end state date/times to match telemetry span.  Extend the
        # state durations by a small amount because of a precision issue converting
        # to date and back to secs.  (The reference tstop could be just over the
        # 0.001 precision of date and thus cause an out-of-bounds error when
        # interpolating state values).
        dt = 0.01 / 86400
        states['tstart'][0] = (start - dt).secs
        states['datestart'][0] = (start - dt).date
        states['tstop'][-1] = (stop + dt).secs
        states['datestop'][-1] = (stop + dt).date

        return states


class SQLStateBuilder(StateBuilder):
    """
    The SQLStateBuilder contains the original code used to
    obtain commanded states for prediction and validation of
    a thermal model for a particular command load. It can also
    be used for validation only.

    SQL is no longer relevant as the commands and states come from kadi.
    """
    def __init__(self, interrupt=False, backstop_file=None,
                 logger=None):
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
        logger : Logger object, optional
            The Python Logger object to be used when logging.
        """
        super(SQLStateBuilder, self).__init__(logger=logger)

        # Note: `interrupt` is ignored in this class. This concept is not needed
        # since backstop 6.9, which provides the RUNNING_LOAD_TERMINATION_TIME
        # (RLTT) that can be reliably used to remove scheduled commands that
        # will not be run.
        self.interrupt = interrupt
        self.backstop_file = backstop_file
        self._get_bs_cmds()

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
        bs_cmds = self.bs_cmds
        bs_dates = bs_cmds['date']

        # Running loads termination time is the last time of "current running loads"
        # (or in the case of a safing action, "current approved load commands" in
        # kadi commands) which should be included in propagation. Starting from
        # around 2020-April this is included as a commmand in the loads, while prior
        # to that we just use the first command in the backstop loads.
        ok = bs_cmds['event_type'] == 'RUNNING_LOAD_TERMINATION_TIME'
        rltt = DateTime(bs_dates[ok][0] if np.any(ok) else bs_dates[0])

        # Scheduled stop time is the end of propagation, either the explicit
        # time as a pseudo-command in the loads or the last backstop command time.
        ok = bs_cmds['event_type'] == 'SCHEDULED_STOP_TIME'
        sched_stop = DateTime(bs_dates[ok][0] if np.any(ok) else bs_dates[-1])

        self.logger.info(f'RLTT = {rltt.date}')
        self.logger.info(f'sched_stop = {sched_stop.date}')

        # Get currently running (or approved) commands from tbegin up to and
        # including commands at RLTT
        cmds = kadi.commands.get_cmds(tbegin, rltt, inclusive_stop=True)

        # Add in the backstop commands
        cmds = cmds.add_cmds(bs_cmds)

        # Get the continuity (state0) and states for available commands.
        states = kadi_states.get_states(cmds=cmds, start=tbegin, stop=sched_stop,
                                        state_keys=STATE_KEYS,
                                        merge_identical=False)
        trans_keys_list = []
        for state in states:
            trans_keys = sorted(key for key in state['trans_keys'] if key in STATE_KEYS)
            trans_keys_list.append(','.join(trans_keys))
        states['trans_keys'] = trans_keys_list
        states = states[sorted(states.colnames)]

        state0 = {key: states[0][key] for key in states.colnames}

        return states, state0


#-------------------------------------------------------------------------------
# ACIS Ops Load History assembly
#-------------------------------------------------------------------------------
class ACISStateBuilder(StateBuilder):

    def __init__(self, interrupt=False, backstop_file=None, nlet_file=None,
                 logger=None):
        """
        Give the ACISStateBuilder arguments that were passed in
        from the command line, and set up the connection to the
        commanded states database.

        Parameters
        ----------
        interrupt : boolean
            If True, this is an interrupt load.
        backstop_file : string
            Path to the backstop file. If a directory, the backstop
            file will be searched for within this directory.
        nlet_file : string
            full path to the Non-Load Event Tracking file
        logger : Logger object, optional
            The Python Logger object to be used when logging.
        """
        # Import the BackstopHistory class
        from backstop_history import BackstopHistory

        # Capture the full path to the NLET file to be used
        self.nlet_file = nlet_file

        # Create an instance of the Backstop Command class
        self.BSC = BackstopHistory.BackstopHistory('ACIS-Continuity.txt', self.nlet_file)

        # The Review Load backstop name
        self.rev_bs_name = None
        # Normally I would have created the self.rev_bs_cmds attribute
        # and used that however to work with ATC I changed it to bs_cmds.

        super(ACISStateBuilder, self).__init__(logger=logger)
        self.interrupt = interrupt
        self.backstop_file = backstop_file

        # if the user supplied a full path to the backstop file then
        # capture the backstop file name and the commands within the backstop file.
        if backstop_file is not None:
            # Get tstart, tstop, commands from backstop file in args.oflsdir
            # These are the REVIEW backstop commands.
            # NOTE: This method takes every command. it does not eliminate
            # commands that are not of interest as sot/cmd_states/get_cmds does.
            rev_bs_cmds,  self.rev_bs_name = self.BSC.get_bs_cmds(self.backstop_file)

            # Store the Review Load backstop commands in the class attribute and
            # also capture the Review load time of first command (TOFC) and
            # Time of Last Command (TOLC).
            self.bs_cmds = rev_bs_cmds
            self.tstart = rev_bs_cmds[0]['time']
            self.tstop = rev_bs_cmds[-1]['time']

            # Initialize the end time attribute for event searches within the BSC object
            # At the beginning, it will be the time of the last command in the Review Load
            self.BSC.end_event_time = rev_bs_cmds[-1]['time']

        # Connect to database (NEED TO USE aca_read for sybase; user is ignored for sqlite)
        # We only need this as the quick way to get the validation states.
        server = os.path.join(os.environ['SKA'], 'data', 'cmd_states', 'cmd_states.db3')
        self.logger.info('Connecting to {} to get cmd_states'.format(server))
        self.db = Ska.DBI.DBI(dbi="sqlite", server=server, user='aca_read',
                              database='aca')

    def get_prediction_states(self, tbegin):
        """
        Get the states used for the prediction.  This includes both the
        states from the review load backstop file and all the
        states between the latest telemetry data and the beginning
        of that review load backstop file.

        The Review Backstop commands already obtained.
        Telemtry from 21 days back to  the latest in Ska obtained.

        So now the task is to backchain through the loads and assemble
        any states missing between the end of telemetry through the start
        of the review load.

        Parameters
        ----------
        tbegin : string
            The starting date/time from which to obtain states for
            prediction. This is tlm['date'][-5]) or, in other words, the
            date used is 5 enteries back from the end of the fetched telemetry
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
        # If an OFLS directory has been specified, get the backstop commands
        # stored in the backstop file in that directory

        # Ok ready to start the collection of continuity commands
        #
        # Make a copy of the Review Load Commands. This will have
        # Continuity commands concatenated to it and will be the final product

        import copy

        bs_cmds = copy.copy(self.bs_cmds)

        # Capture the start time of the review load
        bs_start_time = bs_cmds[0]['time']

        # Capture the path to the ofls directory
        present_ofls_dir = copy.copy(self.backstop_file)

        # So long as the earliest command in bs_cmds is after the state0
        # time, keep concatenating continuity commands to bs_cmds based upon
        # the type of load.
        # Note that as you march back in time along the load chain, 
        # "present_ofls_dir" will change.

        # First we need a State0 because cmd_states.get_states cannot translate
        # backstop commands into commanded states without one. cmd_states.get_state0
        # is written such that if you don't give it a database object it will
        # create one for itself and use that. Here, all that really matters
        # is the value of 'tbegin', the specification of the date parameter to be used
        # and the date_margin.
        state0 = cmd_states.get_state0(tbegin, self.db, datepar='datestart',
                                       date_margin=None)
        # WHILE
        # The big while loop that backchains through previous loads and concatenates the
        # proper load sections to the review load.
        while state0['tstart'] < bs_start_time:

            # Read the Continuity information of the present ofls directory
            cont_load_path, present_load_type, scs107_date = self.BSC.get_continuity_file_info(present_ofls_dir)

            #---------------------- NORMAL ----------------------------------------
            # If the load type is "normal" then grab the continuity command
            # set and concatenate those commands to the start of bs_cmds
            if present_load_type.upper() == 'NORMAL':
                # Obtain the continuity load commands
                cont_bs_cmds, cont_bs_name = self.BSC.get_bs_cmds(cont_load_path)

                # Combine the continuity commands with the bs_cmds. The result
                # is stored in bs_cmds
                bs_cmds = self.BSC.CombineNormal(cont_bs_cmds, bs_cmds)

                # Reset the backstop collection start time for the While loop
                bs_start_time = bs_cmds[0]['time']
                # Now point the operative ofls directory to the Continuity directory
                present_ofls_dir = cont_load_path

            #---------------------- TOO ----------------------------------------
            # If the load type is "too" then grab the continuity command
            # set and concatenate those commands to the start of bs_cmds
            elif present_load_type.upper() == 'TOO':
                # Obtain the continuity load commands
                cont_bs_cmds, cont_bs_name = self.BSC.get_bs_cmds(cont_load_path)

                # Combine the continuity commands with the bs_cmds
                bs_cmds = self.BSC.CombineTOO(cont_bs_cmds, bs_cmds)

                # Reset the backstop collection start time for the While loop
                bs_start_time = bs_cmds[0]['time']
                # Now point the operative ofls directory to the Continuity directory
                present_ofls_dir = cont_load_path

            #---------------------- STOP ----------------------------------------
            # If the load type is "STOP" then grab the continuity command
            # set and concatenate those commands to the start of bs_cmds
            # Take into account the SCS-107 commands which shut ACIS down
            # and any LTCTI run
            elif present_load_type.upper() == 'STOP':

                # Obtain the continuity load commands
                cont_bs_cmds, cont_bs_name = self.BSC.get_bs_cmds(cont_load_path)

                # CombineSTOP the continuity commands with the bs_cmds
                bs_cmds = self.BSC.CombineSTOP(cont_bs_cmds, bs_cmds, scs107_date )

                # Reset the backstop collection start time for the While loop
                bs_start_time = bs_cmds[0]['time']
                # Now point the operative ofls directory to the Continuity directory
                present_ofls_dir = cont_load_path

            #---------------------- SCS-107 ----------------------------------------
            # If the load type is "STOP" then grab the continuity command
            # set and concatenate those commands to the start of bs_cmds
            # Take into account the SCS-107 commands which shut ACIS down
            # and any LTCTI run
            elif present_load_type.upper() == 'SCS-107':
                # Obtain the continuity load commands
                cont_bs_cmds, cont_bs_name = self.BSC.get_bs_cmds(cont_load_path)
                # Store the continuity bs commands as a chunk in the chunk list

                # Obtain the CONTINUITY load Vehicle-Only file
                vo_bs_cmds, vo_bs_name = self.BSC.get_vehicle_only_bs_cmds(cont_load_path)

                # Combine107 the continuity commands with the bs_cmds
                bs_cmds = self.BSC.Combine107(cont_bs_cmds, vo_bs_cmds, bs_cmds, scs107_date )

                # Reset the backstop collection start time for the While loop
                bs_start_time = bs_cmds[0]['time']
                # Now point the operative ofls directory to the Continuity directory
                present_ofls_dir = cont_load_path

        # Convert the assembled backstop command history into commanded states
        # from state0 through the end of the Review Load backstop commands.
        # get_states trims the list to any command whose time is AFTER the state0 START
        # time and then converts each relevant backstop command, in that resultant list,
        # into a pseudo-commanded states state
        states = cmd_states.get_states(state0, bs_cmds)

        # Get rid of the 2099 placeholder stop date
        states[-1].datestop = bs_cmds[-1]['date']
        states[-1].tstop = bs_cmds[-1]['time']

        self.logger.debug('state0 at %s is\n%s' % (DateTime(state0['tstart']).date,
                                                   pformat(state0)))

        return states, state0


state_builders = {"sql": SQLStateBuilder,
                  "acis": ACISStateBuilder}
