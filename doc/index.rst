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

Installation and Development
----------------------------

This assumes that you have a cloned copy of ``acis_thermal_check`` from
http://github.com/acisops/acis_thermal_check. If you have your own Python/Ska
environment available (on a laptop or some other machine), and you have write
permissions on it, to install the package simply run:

::

    python setup.py install

from the top-level directory of the package. This will install the three scripts
``dea_check``, ``dpa_check``, and ``psmc_check`` into your path, and install
``acis_thermal_check`` as a Python package, which can then be imported into any Python
script using the same ``python`` executable.

If you are running and testing this package using the flight-approved Ska environment
on the HEAD LAN, you will not be able to directly install into this environment but
can install ``acis_thermal_check`` as a local package. In this case, the command
is slightly modified:

::

    python setup.py install --user

which will install the package under ``${HOME}/.local/lib`` and the scripts under
``${HOME}/.local/bin``. You will need to add the latter to your ``PATH`` in order to
run the scripts from there, but you will be able to ``import acis_thermal_check`` from
any Python script so long as you use the same ``python`` executable.

If you are doing frequent development and would like to be able to change the code
on the fly and re-run without having to reinstall the code every time, you can use the
``develop`` option of ``setup.py``, which lets you run the code from the source directory itself:

::

    python setup.py develop [--user]

where the ``--user`` flag is again only necessary if you do not have write permissions for
the Python environment you are installing into. If you use ``develop``, all imports of
the ``acis_thermal_check`` package will refer back to the code in the source directory
that you are working from.

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

The usual way to use the load review tool is via the script launchers, e.g. ``dea_check``:

::

  dea_check --oflsdir=/data/acis/LoadReviews/2009/MAY1809/oflsb --outdir=out 
  
  dpa_check --oflsdir=/data/acis/LoadReviews/2009/MAY1809/oflsb --simpos=-99616 \
            --pitch=130.0 --T-dpa=22.2 --ccd-count=1 --fep-count=1

  psmc_check --outdir=regress2010 --run-start=2010:365 --days=360
  

Running Regression Tests
------------------------

``acis_thermal_check`` comes with a regression test suite which uses `py.test <http://pytest.org/>`_ 
to run the tests by comparing the answers given by the code to a "gold standard" set of answers.
To determine if code changes pass these tests, within a cloned copy of ``acis_thermal_check`` in
the ``acis_thermal_check/acis_thermal_check/tests`` subdirectory run:

::

    py.test -s

The ``-s`` flag outputs the ``stdout`` and ``stderr`` to screen so you can see what's going on.
If you'd rather not see that, just remove the flag. 

If you have changed the model specification file or made another change that will change the answers,
to generate new answers run:

::

    py.test -s --generate_answers=answer_dir

where ``answer_dir`` is a directory to output the new answers to. The new answers should be reviewed
with the ACIS operations team before copying to the default location for the "gold standard"
answers.

Answers should be generated using the ``py.test`` that is part of the flight Ska environment.
