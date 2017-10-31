.. _developing-models:

Developing a New Thermal Model for Use with ``acis_thermal_check``
------------------------------------------------------------------

Developing a new thermal model to use with ``acis_thermal_check`` is fairly
straightforward. What is typically only needed is to provide the model-specific 
elements such as the health and safety limits, limits for validation, and 
the code which actually runs the ``xija`` model. Following this will be some
mainly boilerplate driver code which collects command line arguments and runs
the model.

In the following, we will use the command-line runnable Python script for
``dpa_check`` as a guide on how to create a model and run it with 
``acis_thermal_check``. 

Set Up Limits
+++++++++++++

After any necessary imports, at the top of the script, a number of limits 
need to be specified.

First, ``acis_thermal_check`` needs to know two "health and safety" limits 
for the modeled temperature in question: the yellow/caution limit and the 
"planning" limit, which is defined as a margin away from the yellow limit. 
These limits are specified in dictionaries 

It is also necessary to specify validation limits, which correspond to limits
on the differences between the data and the model. Violations of these 
limits will be flagged in the validation report on the web page. For each
MSID, the violation limits are given as a list of tuples, where the first
item in each tuple is the percentile of the distribution of the model error,
and the second item is the amount of allowed error corresponding to that 
percentile. These are specified in the ``VALIDATION_LIMITS`` dictionary. 

Lastly, the histograms produced as a part of the validation report do not 
display the histogram for all temperatures, but only for those temperatures
greater than a lower limit, which is contained in the ``HIST_LIMIT`` list. 

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
    
    # These are the temperatures above which histograms of data-model will be
    # displayed. Multiple values in this list will result in multiple 
    # histograms with different colors on the same plot. 
    HIST_LIMIT = [20.]


Define ``calc_model`` Function
++++++++++++++++++++++++++++++

The next thing to do is to supply a ``calc_model`` function that actually performs
the ``xija`` model calculation. If your thermal model is sensitive to the spacecraft 
roll angle, ``acis_thermal_check`` also provides the ``calc_off_nom_rolls`` function 
which can be used in ``calc_model``. The example of how to set up the DPA model is
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

.. code-block:: python

    def main():
        # Gather command-line arguments
        args = get_options("dpa", model_path)
        # Create ACISThermalCheck object
        dpa_check = ACISThermalCheck("1dpamzt", "dpa",
                                     state_builders[args.state_builder], MSID,
                                     YELLOW, MARGIN, VALIDATION_LIMITS,
                                     HIST_LIMIT, calc_model)
        try:
            # Run ACISThermalCheck driver with command-line arguments
            dpa_check.driver(args)
        except Exception as msg:
            if args.traceback:
                raise
            else:
                print("ERROR:", msg)
                sys.exit(1)
    
    if __name__ == '__main__':
        main()

The Full Script
+++++++++++++++

The full script containing all of these elements in the case of the 1DPAMZT
model is shown below:

.. code-block:: python

    #!/usr/bin/env python
    
    from __future__ import print_function
    import matplotlib
    matplotlib.use('Agg')
    import numpy as np
    import xija
    import sys
    from acis_thermal_check import \
        ACISThermalCheck, \
        calc_off_nom_rolls, \
        get_options, \
        state_builders, \
        get_acis_limits
    import os
    
    model_path = os.path.abspath(os.path.dirname(__file__))
    
    yellow_hi, red_hi = get_acis_limits("1dpamzt")
    
    MSID = {"dpa": '1DPAMZT'}
    YELLOW = {"dpa": yellow_hi}
    MARGIN = {"dpa": 2.0}
    VALIDATION_LIMITS = {'1DPAMZT': [(1, 2.0), (50, 1.0), (99, 2.0)],
                         'PITCH': [(1, 3.0), (99, 3.0)],
                         'TSCPOS': [(1, 2.5), (99, 2.5)]
                         }
    
    HIST_LIMIT = [20.]
    
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
    
    def main():
        args = get_options("dpa", model_path)
        dpa_check = ACISThermalCheck("1dpamzt", "dpa",
                                     state_builders[args.state_builder], MSID,
                                     YELLOW, MARGIN, VALIDATION_LIMITS,
                                     HIST_LIMIT, calc_model)
        try:
            dpa_check.driver(args)
        except Exception as msg:
            if args.traceback:
                raise
            else:
                print("ERROR:", msg)
                sys.exit(1)
    
    if __name__ == '__main__':
        main()

.. _state-builder:

The ``StateBuilder`` Object
---------------------------
