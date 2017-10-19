.. acis_thermal_check documentation master file

ACIS Thermal Model Tools (``acis_thermal_check``)
=================================================

Overview
--------

.. |Chandra_cmd_states| replace:: ``Chandra.cmd_states``
.. _Chandra_cmd_states: http://cxc.harvard.edu/mta/ASPECT/tool_doc/cmd_states/

.. |Ska_engarchive| replace:: ``Ska.engarchive``
.. _Ska_engarchive: http://cxc.cfa.harvard.edu/mta/ASPECT/tool_doc/eng_archive/

.. |xija| replace:: ``xija``
.. _xija: http://cxc.cfa.harvard.edu/mta/ASPECT/tool_doc/xija/

``acis_thermal_check`` is a library which provides the tools to use and maintain
*Chandra* thermal models. These tools depend on the commanded states database
which is accessed primarily via the |Chandra_cmd_states|_ module, and the engineering
archive which is accessed via the |Ska_engarchive|_ module. More specifically,
``acis_thermal_check`` generates backstop load review outputs for checking ACIS
temperatures such as 1DEAMZT, 1DPAMZT, and 1PDEAAT. It also generates model validation
plots for these temperatures comparing predicted values to telemetry for the previous
three weeks.

Installation and Development
----------------------------

This assumes that you have a cloned copy of ``acis_thermal_check`` from
http://github.com/acisops/acis_thermal_check. To install the package simply 
run:

::

    python setup.py install

from the top-level directory of the package. This will install 
``acis_thermal_check`` as a Python package, which can then be imported into any 
Python script using the same ``python`` executable.

If you are doing frequent development and would like to be able to change the code
on the fly and re-run without having to reinstall the code every time, you can use the
``develop`` option of ``setup.py``, which lets you run the code from the source directory
itself:

::

    python setup.py develop


Running a Thermal Model with ``acis_thermal_check``
---------------------------------------------------

Base Command-Line Arguments
+++++++++++++++++++++++++++

.. code-block:: text

  --outdir OUTDIR       Output directory. Default: 'out'
  --backstop_file BACKSTOP_FILE
                        Path to the backstop file. If a directory, the
                        backstop file will be searched for within this
                        directory. Default: None
  --oflsdir OFLSDIR     Path to the directory containing the backstop file
                        (legacy argument). If specified, it will override
                        the value of the backstop_file argument. Default: None
  --model-spec MODEL_SPEC
                        Model specification file. Defaults to the one included
                        with the model package.
  --days DAYS           Days of validation data. Default: 21
  --run-start RUN_START
                        Reference time to replace run start time for
                        regression testing. The default is to use the current
                        time.
  --interrupt           Set this flag if this is an interrupt load.
  --traceback TRACEBACK
                        Enable tracebacks. Default: True
  --verbose VERBOSE     Verbosity (0=quiet, 1=normal, 2=debug)
  --T-init T_INIT       Starting temperature (degC or degF, depending on the
                        model). Default is to compute it from telemetry.
  --cmd-states-db CMD_STATES_DB
                        Commanded states database server (sybase|sqlite). Only
                        used if state-builder=legacy. Default: sybase
  --state-builder STATE_BUILDER
                        StateBuilder to use (legacy|acis|hdf5). Default:
                        legacy
  --version             Print version

Running Thermal Models for a Load Review
++++++++++++++++++++++++++++++++++++++++

The most common application for any model based on ``acis_thermal_check`` is to
run the model for a load. In this case, the minimum command-line arguments are
the path to the backstop file and the output directory for the files:

.. code-block:: bash

    [~]$ dpa_check --backstop_file=/data/acis/LoadReviews/2017/OCT1617 --outdir=dpa_oct1617 

If the load being reviewed is a return to science from a shutdown, or a replan
due to a TOO, or any other interrupt, the thermal model should be run with the
``--interrupt`` flag to ensure commanded states are properly determined:

.. code-block:: bash

    [~]$ dpa_check --backstop_file=/data/acis/LoadReviews/2017/AUG3017 --interrupt --outdir=dpa_aug3017

By default, the initial temperature for the model will be set using an average of 
telemetry in a few minutes around the run start time. However, the model can be started
with a specific temperature value using the ``--T-init`` argument, which is assumed to
be in the same units of the temperature in the model (degrees C or F):

.. code-block:: bash

    [~]$ dpa_check --backstop_file=/data/acis/LoadReviews/2017/OCT1617 --outdir=dpa_oct1617 --T-init=22.0

Running Thermal Models for Validation Only
++++++++++++++++++++++++++++++++++++++++++

The ``StateBuilder`` Object
---------------------------


Developing a New Thermal Model for Use with ``acis_thermal_check``
------------------------------------------------------------------

Developing a new thermal model to use with ``acis_thermal_check`` is fairly
straightforward. What is typically only needed is to provide the model-specific 
elements such as the health and safety limits, limits for validation, and 
the code which actually runs the ``xija`` model.

Set Up Limits
+++++++++++++

``acis_thermal_check`` needs to know two "health and safety" limits for the
modeled temperature in question: the yellow/caution limit and the "planning"
limit, which is defined as a margin away from the yellow limit. 

.. code-block:: python

    MSID = {"dpa": '1DPAMZT'} # Dict containing map from short name to MSID name
    YELLOW = {"dpa": 37.5} # Dict containing map from short name to yellow limit
    MARGIN = {"dpa": 2.0} # Dict containing map from short name to margin
    # planning limit = YELLOW-MARGIN
    
    # These are validation limits for various MSIDs.
    VALIDATION_LIMITS = {'1DPAMZT': [(1, 2.0), (50, 1.0), (99, 2.0)],
                         'PITCH': [(1, 3.0), (99, 3.0)],
                         'TSCPOS': [(1, 2.5), (99, 2.5)]
                         }
    
    HIST_LIMIT = [20.]


Define ``calc_model`` Function
++++++++++++++++++++++++++++++

The next thing to do is to supply a ``calc_model`` function that actually performs
the ``xija`` model calculation. If your thermal model is sensitive to the spacecraft 
roll angle, ``acis_thermal_check`` also provides the ``calc_off_nom_rolls`` function 
which can be used in ``calc_model`. The example of how to set up the DPA model is
shown below:

.. code-block:: python

    import xija
    import numpy as np
    from acis_thermal_check import calc_off_nom_rolls

    def calc_model(model_spec, states, start, stop, T_dpa=None, T_dpa_times=None):
        model = xija.ThermalModel('dpa', start=start, stop=stop,
                                  model_spec=model_spec)
        times = np.array([states['tstart'], states['tstop']])
        model.comp['sim_z'].set_data(states['simpos'], times)
        model.comp['eclipse'].set_data(False)
        model.comp['1dpamzt'].set_data(T_dpa, T_dpa_times)
        model.comp['roll'].set_data(calc_off_nom_rolls(states), times)
        for name in ('ccd_count', 'fep_count', 'vid_board', 'clocking', 'pitch'):
            model.comp[name].set_data(states[name], times)
    
        model.make()
        model.calc()
        return model

The ``calc_model`` function must have this exact signature, with the first four
required arguments and the last two optional arguments. 

Create ``ACISThermalCheck`` Object
++++++++++++++++++++++++++++++++++
