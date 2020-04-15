.. _developing-models:

Developing a New Thermal Model for Use with ``acis_thermal_check``
------------------------------------------------------------------

To develop a new thermal model for use with ``acis_thermal_check``, the 
following steps should be followed. A new model needs the following:

* A subclass of the ``ACISThermalCheck`` class, e.g. ``DPACheck``.
* This subclass should have 
* Testing needs to be set up. 

Developing a new thermal model to use with ``acis_thermal_check`` is fairly
straightforward. What is typically only needed is to provide the model-specific 
elements such as the limits for validation, the JSON file containing the model
specification, and the code which actually runs the ``xija`` model. There will
also need to be some mainly boilerplate driver code which collects command line 
arguments and runs the model. Finally, one will need to set up testing. 

In the following, we will use the Python package for ``dpa_check`` as a guide 
on how to create a model and run it with ``acis_thermal_check``. 

The Overall Design of the Package
=================================

The structure of the ``dpa_check`` package is designed to be a typical Python
package and looks like this:

.. code-block:: bash

    dpa_check/
        dpa_check/
            __init__.py
            dpa_check.py
            dpa_model_spec.json
            tests/
                __init__.py
                dpa_test_spec.json
                test_dpa_acis.py
                test_dpa_sql.py
                test_dpa_viols.py
    conftest.py
    setup.py
    MANIFEST.in
    .gitignore
    .gitattributes
    .git_archival.txt

At the top level, we have ``setup.py``, ``MANIFEST.in``, and ``.gitignore``. 

``setup.py`` is the file that is used to determine how the package should be
installed. It has a fairly boilerplate structure, but there are some items that
should be noted. The ``setup.py`` for ``dpa_check`` looks like this:

.. code-block:: python

    #!/usr/bin/env python
    from setuptools import setup
    
    try:
        from testr.setup_helper import cmdclass
    except ImportError:
        cmdclass = {}
    
    entry_points = {'console_scripts': 'dpa_check = dpa_check.dpa_check:main'}
    
    setup(name='dpa_check',
          packages=["dpa_check"],
          use_scm_version=True,
          setup_requires=['setuptools_scm', 'setuptools_scm_git_archive'],
          description='ACIS Thermal Model for 1DPAMZT',
          author='John ZuHone',
          author_email='jzuhone@gmail.com',
          url='http://github.com/acisops/dpa_check',
          include_package_data=True,
          entry_points=entry_points,
          zip_safe=False,
          tests_require=["pytest"],
          cmdclass=cmdclass,
          )

Your ``setup.py`` script should look essentially the same as this one, except 
that wherever there is a reference to ``dpa_check`` or 1DPAMZT you should change
it to the appropriate name for your package. Note the ``entry_points`` 
dictionary: what it does is tell the installer that we want to make an 
executable wrapper for the ``dpa_check.py`` script that can be run from the 
command line. It does this for you, you just need to make sure it points to the
correct package name. 

``MANIFEST.in`` contains a list of data files and file wildcards that need to be 
installed along with the package. This includes the model specification file 
``dpa_model_spec.json``, and whatever "gold standard" testing answers are 
present in the package:

.. code-block:: none

    include dpa_check/dpa_model_spec.json
    include dpa_check/dpa_check/tests/answers/*

There are several git-related files which also need to be included. 
``.gitignore`` is simply a list of files and file wildcards that one wants git 
to ignore so they don't get accidentally committed to the repository. These 
include things like byte-compiled files (``*.pyc``) and other directories and 
files that are created when the package is installed. The ``.gitignore`` for 
``dpa_check`` looks like this:

.. code-block:: none
    
    build
    dist
    *.pyc
    dpa_check.egg-info

``.gitattributes`` only needs to contain the following:

.. code-block:: none

    .git_archival.txt  export-subst

and ``.git_archival.txt`` only needs to contain this:

.. code-block:: none

    ref-names: $Format:%D$

The Main Script
===============

The following describes how one designs the script that uses 
``acis_thermal_check`` to

Front Matter
++++++++++++

The beginning part of the script should contain the following:

.. code-block:: python

    #!/usr/bin/env python

    """
    ========================
    dpa_check
    ========================
    
    This code generates backstop load review outputs for checking the ACIS
    DPA temperature 1DPAMZT.  It also generates DPA model validation
    plots comparing predicted values to telemetry for the previous three
    weeks.
    """
    
    # Matplotlib setup
    # Use Agg backend for command-line (non-interactive) operation
    import matplotlib
    matplotlib.use('Agg')
    
    import sys
    from acis_thermal_check import \
        ACISThermalCheck, \
        get_options
    import os
    
    model_path = os.path.abspath(os.path.dirname(__file__))

This includes the required imports and a beginning comment about what the
script is for, the latter of which should be modified for your model case. 

Subclassing ``ACISThermalCheck``
++++++++++++++++++++++++++++++++

The bulk of the script is contained

``main`` Function
+++++++++++++++++

The ``main`` function is called when the model script is run from the command
line. What it needs to do is gather the command-line arguments using the 
``get_options`` function, create an instance of the subclass of the 
``ACISThermalCheck`` we created above, and then call that instance's ``run``
method using the arguments. It's also a good idea to run the model within a 
``try...except`` block in case any exceptions are raised, because then we 
can control whether or not the traceback is printed to screen via the 
``--traceback`` command-line argument.

.. code-block:: python

    def main():
        args = get_options("dpa", model_path) # collect the arguments
        dpa_check = DPACheck() # create an instance of the subclass
        try:
            dpa_check.run(args) # run the model using the arguments
        except Exception as msg:
            # handle any errors
            if args.traceback:
                raise
            else:
                print("ERROR:", msg)
                sys.exit(1)
    
    # This ensures main() is called when run from the command line
    if __name__ == '__main__':
        main()





Set Up Limits
+++++++++++++

First, ``acis_thermal_check`` needs to know two "health and safety" limits for 
the modeled temperature in question: the yellow/caution limit and the "planning"
limit, which is defined as a margin away from the yellow limit. These limits are
handled by the ``get_acis_limits`` function which is in the 
``acis_thermal_check.utils`` module. If you have a brand-new model which 
``get_acis_limits`` does not 

It is also necessary to specify validation limits, which correspond to limits on
the differences between the data and the model. Violations of these limits will
be flagged in the validation report on the web page. For each MSID, the 
violation limits are given as a list of tuples, where the first item in each 
tuple is the percentile of the distribution of the model error, and the second
item is the amount of allowed error corresponding to that percentile. These are
specified in the ``VALIDATION_LIMITS`` dictionary, which should be specified at
the top of the script. 

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


Define ``_calc_model_supp`` Method
++++++++++++++++++++++++++++++++++

The next thing to do is to supply a ``calc_model`` function that actually 
performs the ``xija`` model calculation. If your thermal model is sensitive to 
the spacecraft roll angle, ``acis_thermal_check`` also provides the 
``calc_off_nom_rolls`` function which can be used in ``calc_model``. The example
of how to set up the DPA model is shown below:

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
this particular model does not depend on the state of the detector housing 
heater, the optional arguments are still required in the signature of the 
function. 

The Full Script
+++++++++++++++

For reference, the full script containing all of these elements in the case 
of the 1DPAMZT model is shown below:

.. code-block:: python
    
    #!/usr/bin/env python
    
    """
    ========================
    dpa_check
    ========================
    
    This code generates backstop load review outputs for checking the ACIS
    DPA temperature 1DPAMZT.  It also generates DPA model validation
    plots comparing predicted values to telemetry for the previous three
    weeks.
    """
    
    # Matplotlib setup
    # Use Agg backend for command-line (non-interactive) operation
    import matplotlib
    matplotlib.use('Agg')
    
    import sys
    from acis_thermal_check import \
        ACISThermalCheck, \
        get_options
    import os
    
    model_path = os.path.abspath(os.path.dirname(__file__))
    
    
    class DPACheck(ACISThermalCheck):
        def __init__(self):
            valid_limits = {'1DPAMZT': [(1, 2.0), (50, 1.0), (99, 2.0)],
                            'PITCH': [(1, 3.0), (99, 3.0)],
                            'TSCPOS': [(1, 2.5), (99, 2.5)]
                            }
            hist_limit = [20.0]
            super(DPACheck, self).__init__("1dpamzt", "dpa", valid_limits,
                                           hist_limit)
    
        def _calc_model_supp(self, model, state_times, states, ephem, state0):
            """
            Update to initialize the dpa0 pseudo-node. If 1dpamzt
            has an initial value (T_dpa) - which it does at
            prediction time (gets it from state0), then T_dpa0 
            is set to that.  If we are running the validation,
            T_dpa is set to None so we use the dvals in model.comp
    
            NOTE: If you change the name of the dpa0 pseudo node you
                  have to edit the new name into the if statement
                  below.
            """
            if 'dpa0' in model.comp:
                if state0 is None:
                    T_dpa0 = model.comp["1dpamzt"].dvals
                else:
                    T_dpa0 = state0["1dpamzt"]
                model.comp['dpa0'].set_data(T_dpa0, model.times)
    
    
    def main():
        args = get_options("dpa", model_path)
        dpa_check = DPACheck()
        try:
            dpa_check.run(args)
        except Exception as msg:
            if args.traceback:
                raise
            else:
                print("ERROR:", msg)
                sys.exit(1)
    
    
    if __name__ == '__main__':
        main()

Testing Files
-------------