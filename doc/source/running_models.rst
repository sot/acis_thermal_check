.. _running-models:

Running a Thermal Model with ``acis_thermal_check``
---------------------------------------------------

``acis_thermal_check`` models are adapted to each use case and run from the
command line. This section provides a brief description on how to use 

Base Command-Line Arguments
+++++++++++++++++++++++++++

The following is a brief description of the base collection of command-line 
arguments accepted by a model using ``acis_thermal_check``. Additional
arguments may be added by individual models in the call to 
:func:`~acis_thermal_check.utils.get_options`, as further detailed in
:ref:`developing-models`. 

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

If one is using the legacy state builder, one can also choose to access the 
commanded states database via Sybase or SQLite. The former only works with Python 2, so
if Python 3 is used, the latter will be chosen automatically. To choose which one to use
(if you have the option), set the ``--cmd-states-db`` flag:

.. code-block:: bash

    [~]$ dpa_check --backstop_file=/data/acis/LoadReviews/2017/OCT1617 --outdir=dpa_oct1617 --cmd-states-db=sqlite

Running Thermal Models for Validation Only
++++++++++++++++++++++++++++++++++++++++++