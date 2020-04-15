.. _running-models:

Running a Thermal Model with ``acis_thermal_check``
---------------------------------------------------

``acis_thermal_check`` models are adapted to each use case and run from the
command line. This section provides a brief description on how to run the 
models, including what the various options are. 

Base Command-Line Arguments
+++++++++++++++++++++++++++

The following is a brief description of the base collection of command-line 
arguments accepted by a model using ``acis_thermal_check``. Additional arguments
may be added by individual models in the call to, as further detailed in
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
  --pred-only           Only make predictions. Default: False
  --verbose VERBOSE     Verbosity (0=quiet, 1=normal, 2=debug)
  --T-init T_INIT       Starting temperature (degC). Default is to compute it 
                        from telemetry.
  --state-builder STATE_BUILDER
                        StateBuilder to use (legacy|acis). Default:
                        legacy
  --nlet_file NLET_FILE
                        Full path to the Non-Load Event Tracking that should
                        be used for this model run
  --version             Print version

Running Thermal Models: Examples
++++++++++++++++++++++++++++++++

The most common application for any model based on ``acis_thermal_check`` is to
run the model for a load. In this case, the minimum command-line arguments are
the path to the backstop file and the output directory for the files:

.. code-block:: bash

    [~]$ dpa_check --backstop_file=/data/acis/LoadReviews/2017/OCT1617/ofls --outdir=dpa_oct1617 

In this case, we only supplied the directory containing the backstop file, 
assuming that there is only one present. If the load being reviewed is a return 
to science from a shutdown, or a replan due to a TOO, or any other interrupt, 
the thermal model should be run with the ``--interrupt`` flag to ensure 
commanded states are properly determined:

.. code-block:: bash

    [~]$ psmc_check --backstop_file=/data/acis/LoadReviews/2017/AUG3017/ofls --interrupt --outdir=psmc_aug3017

By default, the initial temperature for the model will be set using an average 
of telemetry in a few minutes around the run start time. However, the model can
be started with a specific temperature value using the ``--T-init`` argument, 
which is assumed to be in degrees C:

.. code-block:: bash

    [~]$ acisfp_check --backstop_file=/data/acis/LoadReviews/2017/OCT1617/ofls --outdir=acisfp_oct1617 --T-init=22.0

If necessary, thermal model runs can be run for a particular load for predictions only,
using the ``--pred-only`` flag:

.. code-block:: bash

    [~]$ dea_check --backstop_file=/data/acis/LoadReviews/2017/AUG3017/ofls --outdir=dea_aug3017 --pred-only

Finally, if one wishes to run validation without prediction for a specific load,
simply omit the ``backstop_file`` argument. It may make sense here to supply a 
``run_start`` argument, if one wants a different time than the current time to 
validate:

.. code-block:: bash

    [~]$ dpa_check --run-start=2019:300:12:50:00 --outdir=validate_dec2019