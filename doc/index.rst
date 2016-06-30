.. acis_thermal_check documentation master file

ACIS Thermal Model Tools
========================

This suite provides the tools to use and maintain the Chandra ACIS
thermal models. The key elements are:

  - ``dea_check``: Thermal check of command loads and validate DEA
    model against recent telemetry
  - ``dpa_check``: Thermal check of command loads and validate DPA
    model against recent telemetry
  - ``psmc_check``: Thermal check of command loads and validate PSMC
    model against recent telemetry

These tools depend on Sybase tables and in particular the commanded states database
which is accessed primarily via the Chandra.cmd_states_ module.

.. _Chandra.cmd_states: http://cxc.harvard.edu/mta/ASPECT/tool_doc/cmd_states/

``acis_thermal_check``
======================

Overview
--------

This code generates backstop load review outputs for checking the ACIS temperatures
1DEAMZT, 1DPAMZT, and 1PDEAAT. It also generates model validation plots for these
temperatures comparing predicted values to telemetry for the previous three weeks.

Command line options
--------------------

Typical use case
^^^^^^^^^^^^^^^^

In the typical use case for doing load review the model check tools will
propagate forward from a 5-minute average of the last available telemetry using
the ``cmd_states`` table.  The following options control the runtime behavior
of the ``dea_check``, ``dpa_check``, and ``psmc_check`` scripts:

========================= ================================== ===================
Option                    Description                        Default           
========================= ================================== ===================
  --outdir=OUTDIR         Output directory                   out
  --oflsdir=OFLSDIR       Load products OFLS directory       None
  --model-spec=MODEL_SPEC Model specification file           *_model_spec.json
  --days=DAYS             Days of validation data (days)     21
  --run-start=RUN_START   Start time for regression testing  None
  --traceback=TRACEBACK   Enable tracebacks                  True
  --verbose=VERBOSE       Verbosity 0=quiet 1=normal 2=debug 1 (normal)
  --version               Print version                      
========================= ================================== ===================

where the ambiguity in the default value of the ``--model-spec`` option indicates
that the file appropriate to which model is being run will be used, e.g. ``dea_model_spec.json``.

Custom initial conditions
^^^^^^^^^^^^^^^^^^^^^^^^^

In the event that the Ska database is unavailable or specific initial conditions
are desired, the following options are provided.  The only required option is that of
the initial temperature, which depends on which script is being run:

*NOTE: Specifying custom conditions STILL REQUIRES the Ska database in the current release.*

========== ================ ==================================== ===================
Script     Option           Description                          Default
========== ================ ==================================== ===================
dea_check  --T-dea=T_DEA    Initial 1DEAMZT temperature (degC)   None
dpa_check  --T-dpa=T_DPA    Initial 1DPAMZT temperature (degC)   None
psmc_check --T-psmc=T_PSMC  Initial 1PDEAAT temperature (degC)   None
========== ================ ==================================== ===================

All the rest of the options are common to the various scripts (except ``dh_heater``,
which is specific to ``psmc_check``), and have default values that will produce a
conservative (hot) prediction:

========================= ==================================== ===================
Option                    Description                          Default
========================= ==================================== ===================
  --ccd-count=CCD_COUNT   Initial number of CCDs               6
  --fep-count=FEP_COUNT   Initial number of FEPs               6
  --vid-board=VID_BOARD   Initial state of ACIS vid_board      1
  --clocking=CLOCKING     Initial state of ACIS clocking       1
  --simpos=SIMPOS         Initial SIM-Z position (steps)       75616
  --pitch=PITCH           Initial pitch (degrees)              150
  --dh_heater=DH_HEATER   ACIS DH Heater on/off (PSMC only)    0
========================= ==================================== ===================

Usage
-----

The usual way to use the load review tool is via the script launchers, e.g.
``/proj/sot/ska/bin/dea_check``.  This script sets up the Ska runtime
environment to ensure access to the correct python libraries.  This must be run
on a 64-bit linux machine.

::

  /proj/sot/ska/bin/dea_check --oflsdir=/data/acis/LoadReviews/2009/MAY1809/oflsb \
                              --outdir=out 
  
  /proj/sot/ska/bin/dpa_check --oflsdir=/data/acis/LoadReviews/2009/MAY1809/oflsb \
                              --simpos=-99616 --pitch=130.0 --T-dpa=22.2 \
                              --ccd-count=1 --fep-count=1

  /proj/sot/ska/bin/psmc_check --outdir=regress2010 --run-start=2010:365 --days=360
 
