.. _test-suite:

Using the ``acis_thermal_check`` Regression Testing
---------------------------------------------------

``acis_thermal_check`` includes a regression test fremework which

A Overview of ``acis_thermal_check`` Regression Testing
+++++++++++++++++++++++++++++++++++++++++++++++++++++++

Running the Test Suite for a Particular Model
+++++++++++++++++++++++++++++++++++++++++++++

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
    
    newgrp acisops

This enables you to write to the set of thermal model gold standard answers
which are owned by ``acisdude``. 