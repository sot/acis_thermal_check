.. _test_suite:

Using the ``acis_thermal_check`` Regression Testing
---------------------------------------------------

``acis_thermal_check`` includes a regression test fremework which allows one to
develop tests for a given thermal model against a set of "gold standard" model 
outputs for a number of load weeks. This section describes the test suite, how 
to run it, how to add new loads for testing, and how to update the gold standard
model answers.

An Overview of ``acis_thermal_check`` Regression Testing
++++++++++++++++++++++++++++++++++++++++++++++++++++++++

When an ``acis_thermal_check`` model is run, it produces numerical outputs for 
model prediction and validation in addition to the plots and tables on the 
webpages. The ``acis_thermal_check`` regression testing framework compares this
numerical output from model runs against a set of "gold standard" stored 
outputs. The idea is that code developments should not change the values 
compared to those stored in the gold standard, or if they do, that the reasons
for the changes are understood and deemed necessary (e.g., you found
a bug, you added a feature to a model, etc.). This allows us to track the effect
of code changes in a systematic way and flag those changes which are not 
expected to change results but do, so that bugs can be identified and fixed 
before merging the new code into master. 

A model specification file in JSON format is set aside for testing, and can be
different from the one currently in use for thermal models. It should only be
updated sparingly, usually if there are major changes to the structure of a 
model.

Running the Test Suite for a Particular Model
+++++++++++++++++++++++++++++++++++++++++++++

There are two equivalent ways to invoke the ``acis_thermal_check``
tests for a given model. 

If you are making changes to a model, you can go to the root of the model code
directory (e.g., ``dpa_check``) and run ``py.test`` like so:

.. code-block:: bash

    [~]$ cd ~/Source/dpa_check

    [~]$ py.test -s .

The ``-s`` flag is optionally included here so that the output has maximum verbosity.

You can also import any model package from an interactive Python session and run the 
``test()`` method on it:

.. code-block:: pycon

    >>> import acisfp_check
    >>> acisfp_check.test()

Updating the "Gold Standard" Answers for a Particular Model
+++++++++++++++++++++++++++++++++++++++++++++++++++++++++++

New "gold standard" answers for a given model may need to be generated for two
reasons. First, you may be making a new model and need to generate the initial 
set of answers. Second, if you are updating ACIS code and the regression tests 
failed to pass for one or more models, but the failures are understood and they 
are due to changes you made which need to become part of the software (such as 
a bugfix or a feature enhancement), then the "gold standard" answers need to be
updated. 

To generate new answers, go to the root of the model code directory that you are
working in, and run ``py.test``, with the ``--answer_store`` argument:

.. code-block:: bash

    [~]$ cd ~/Source/dpa_check

    [~]$ py.test -s . --answer_store

This will overwrite the old answers, but since they are also under git version 
control you will be able to check any differences before committing the new
answers. 
