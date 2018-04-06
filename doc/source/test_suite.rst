.. _test-suite:

Using the ``acis_thermal_check`` Regression Testing
---------------------------------------------------

``acis_thermal_check`` includes a regression test fremework which allows one to
develop tests for a given thermal model against a set of "gold standard" model 
outputs for a number of load weeks. This section describes the test suite, how 
to run it, how to add new loads for testing, and how to update the gold standard
model answers.

A Overview of ``acis_thermal_check`` Regression Testing
+++++++++++++++++++++++++++++++++++++++++++++++++++++++

When an ``acis_thermal_check`` model is run, it produces numerical outputs for 
model prediction and validation in addition to the plots and tables on the 
webpages. The ``acis_thermal_check`` regression testing framework compares this
numerical output from model runs against a set of "gold standard" stored 
outputs. The idea is that code developments should not change the values 
compared to those stored in the gold standard, or if they do, that the reasons
for the changes are understood and deemed necessary (e.g., you found
a bug, you updated the model specification, or you added a feature to 
a model). Though this means that the gold standard answers might 
change regularly (so maybe more of a floating currency), the idea is to
track the effect of code changes in a systematic way and flag those 
changes which are not expected to change results but do, so that bugs
can be identified and fixed before merging the new code into master. 

Running the Test Suite for a Particular Model
+++++++++++++++++++++++++++++++++++++++++++++

There are a few equivalent ways to invoke the ``acis_thermal_check``
tests for a given model. 

If you are making changes to a model, you can go to the root of the model code
directory (e.g., ``dpa_check``) and just run ``py.test``:

.. code-block:: bash

    [~]$ py.test -s 

The ``-s`` flag is optionally included so that the output has maximum verbosity.

Adding the Basic Test Suite to a New Model
++++++++++++++++++++++++++++++++++++++++++

Updating the "Gold Standard" Answers
++++++++++++++++++++++++++++++++++++

If the regression tests failed to pass for one or more models, 
but you understand the failures and they are due to changes you
made which need to become part of the software (such as a bugfix
or a feature enhancement), then the "gold standard" answers need 
to be updated. In theory, updating these could be as simple as 
generating new answers and copying them into the appropriate
directory, but to be safe there is a script, ``update_atc_answers``,
which handles this for you in a transparent way with prompts and
outputs to screen so that you are sure you are doing the right thing
and that you see what is actually being done. 

First, you should change your group to ``acisops``:

.. code-block:: bash
    
    [~]$ newgrp acisops

This enables you to write to the set of thermal model gold standard answers
which are owned by the user ``acisdude`` under the group ``acisops``. These 
are located in the directory ``/data/acis/thermal_model_tests``. 