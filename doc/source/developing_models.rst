.. _developing-models:

Developing a New Thermal Model for Use with ``acis_thermal_check``
------------------------------------------------------------------

Developing a new thermal model to use with ``acis_thermal_check`` is fairly
straightforward. What is typically only needed is to provide the model-specific 
elements such as the limits for validation and the code which actually runs the 
``xija`` model. Following this will be some mainly boilerplate driver code which 
collects command line arguments and runs the model.

In the following, we will use the command-line runnable Python script for
``dpa_check`` as a guide on how to create a model and run it with 
``acis_thermal_check``. 

Set Up Limits
+++++++++++++

First, ``acis_thermal_check`` needs to know two "health and safety" limits 
for the modeled temperature in question: the yellow/caution limit and the 
"planning" limit, which is defined as a margin away from the yellow limit. 
These limits are handled by the ``get_acis_limits`` function which is in
the ``acis_thermal_check.utils`` module. If you have a brand-new model which
``get_acis_limits`` does not 

It is also necessary to specify validation limits, which correspond to limits
on the differences between the data and the model. Violations of these 
limits will be flagged in the validation report on the web page. For each
MSID, the violation limits are given as a list of tuples, where the first
item in each tuple is the percentile of the distribution of the model error,
and the second item is the amount of allowed error corresponding to that 
percentile. These are specified in the ``VALIDATION_LIMITS`` dictionary, which 
should be specified at the top of the script. 

Lastly, the histograms produced as a part of the validation report do not 
display the histogram for all temperatures, but only for those temperatures
greater than a lower limit, which is contained in the ``HIST_LIMIT`` list. 

Including the necessary imports, the top of the script should look like this:

.. code-block:: python

    from __future__ import print_function

    import matplotlib
    matplotlib.use('Agg')
    
    import numpy as np
    import xija
    import sys
    from acis_thermal_check import \
        ACISThermalCheck, \
        calc_off_nom_rolls, \
        get_options
    import os

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

    def calc_model(model_spec, states, start, stop, T_dpa=None, T_dpa_times=None,
                   dh_heater=None, dh_heater_times=None):
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
required arguments and the last four optional arguments. Note that even though 
this particular model does not depend on the state of the detector housing heater,
the optional arguments are still required in the signature of the function. 

Create ``ACISThermalCheck`` Object
++++++++++++++++++++++++++++++++++

The last thing to do is to create a ``main`` function which will be run when the 
script is run. This function will collect the command-line arguments using the
``get_options`` function, create the ``ACISThermalCheck`` object with the arguments
it needs, and then use the ``run`` method of ``ACISThermalCheck`` to run the model. 
It's a good idea to run the model within a ``try...except`` block in case any 
exceptions are raised, because then we can control whether or not the traceback is 
printed to screen via the ``--traceback`` command-line argument.

.. code-block:: python

    def main():
        args = get_options("dpa", model_path)
        dpa_check = ACISThermalCheck("1dpamzt", "dpa", VALIDATION_LIMITS,
                                     HIST_LIMIT, calc_model, args)
        try:
            dpa_check.run()
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
        get_options
    import os
    
    model_path = os.path.abspath(os.path.dirname(__file__))
        
    VALIDATION_LIMITS = {'1DPAMZT': [(1, 2.0), (50, 1.0), (99, 2.0)],
                         'PITCH': [(1, 3.0), (99, 3.0)],
                         'TSCPOS': [(1, 2.5), (99, 2.5)]
                         }
    
    HIST_LIMIT = [20.]
    
    def calc_model(model_spec, states, start, stop, T_dpa=None, T_dpa_times=None,
                   dh_heater=None, dh_heater_times=None):
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
        dpa_check = ACISThermalCheck("1dpamzt", "dpa", VALIDATION_LIMITS,
                                     HIST_LIMIT, calc_model, args)
        try:
            dpa_check.run()
        except Exception as msg:
            if args.traceback:
                raise
            else:
                print("ERROR:", msg)
                sys.exit(1)
    
    if __name__ == '__main__':
        main()

