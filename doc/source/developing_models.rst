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

At the top level, we have ``setup.py``, ``MANIFEST.in``, and three git-related
files. 

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

Package Initialization File
===========================

This file defines the public API for the model package and sets up some other 
important information. It must use ``ska_helpers`` to obtain the version number
of the package, import some basic objects for public use, and provide a hook
for testing. The manner in which this is done for the 1DPAMZT model is shown
here:

.. code-block:: python

    import ska_helpers
    
    __version__ = ska_helpers.get_version(__package__)
    
    from .dpa_check import \
        DPACheck, main, \
        model_path
    
    
    def test(*args, **kwargs):
        """
        Run py.test unit tests.
        """
        import testr
        return testr.test(*args, **kwargs)

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

The bulk of the script is contained in a subclass of the ``ACISThermalCheck``
class that is model-specific. This subclass will contain information specific
to the model. In the case of the 1DPAMZT model, this class is called 
``DPACheck``. 

This class definition will require an ``__init__`` method which takes no 
arguments beyond ``self``. Inside it, validation limits for various MSIDs should
be specified, which correspond to limits on the differences between the data and
the model. Violations of these limits will be flagged in the validation report 
on the web page. For each MSID, the violation limits are given as a list of 
tuples, where the first item in each tuple is the percentile of the distribution
of the model error, and the second item is the amount of allowed error 
corresponding to that percentile. These are specified in the ``valid_limits`` 
dictionary, which is defined in ``__init__``.

Also, the histograms produced as a part of the validation report do not 
display the histogram for all temperatures, but only for those temperatures 
greater than a lower limit, which is contained in the ``hist_limit`` list. This
should also be defined in ``__init__``. 

The example of this class definition for the 1DPAMZT model is shown here. Both
limit objects that were created are passed to the ``__init__`` of the superclass.

.. code-block:: python

    class DPACheck(ACISThermalCheck):
        def __init__(self):
            # Specify the validation limits 
            valid_limits = {'1DPAMZT': [(1, 2.0), (50, 1.0), (99, 2.0)],
                            'PITCH': [(1, 3.0), (99, 3.0)],
                            'TSCPOS': [(1, 2.5), (99, 2.5)]
                            }
            # Specify the validation histogram limits
            hist_limit = [20.0]
            # Call the superclass' __init__ with the arguments
            super(DPACheck, self).__init__("1dpamzt", "dpa", valid_limits,
                                           hist_limit)
                                           
The ``_calc_model_supp`` Method
+++++++++++++++++++++++++++++++

The subclass of the ``ACISThermalCheck`` class will probably require a 
``_calc_model_supp`` method to be defined. For the default ``ACISThermalCheck``
class, this method does nothing. But in the case of each individual model, it 
will set up states, components, or nodes which are specific to that model.

The next thing to do is to supply a ``_calc_model`` function that actually 
performs the ``xija`` model calculation. If your thermal model is sensitive to 
the spacecraft roll angle, ``acis_thermal_check`` also provides the 
``calc_off_nom_rolls`` function which can be used in ``calc_model``. The example
of how to set up this method for the 1DPAMZT model is shown below:

.. code-block:: python

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

Note that the method requires the ``XijaModel model`` object, the array of 
``state_times``, the commanded ``states`` array, the ephemeris ``MSIDSet`` 
``ephem``, and the ``state0`` dictionary providing the initial state. These
are all defined and set up in ``ACISThermalCheck``, so the model developer 
does not need to do this. The ``_calc_model_supp`` method must have this 
exact signature. 

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

Testing Scripts and Data
------------------------

Several files are required to ensure that the model package can run tests. 
First, the ``conftest.py`` file which ``pytest`` uses to configure the tests
must be set up like this at the top level of the package:

.. code-block::

    from acis_thermal_check.conftest import *

All this does is import the relevant testing configuration machinery from the
``acis_thermal_check`` package itself. 

Second, within the package's code directory, there should be a ``tests``
directory, with an empty ``__init__.py``, an initially empty ``answers``
directory, a model specification file, and three Python scripts for testing.
These include: 


