.. _install:

Installation and Development
----------------------------

.. note:: 

    If all you want to do is run the existing thermal models installed on
    flight Ska, you can safely ignore this section. 

This assumes that you have a cloned copy of ``acis_thermal_check`` from
http://github.com/acisops/acis_thermal_check. To install the package simply 
run:

.. code-block:: bash

    [~]$ python setup.py install

from the top-level directory of the package. This will install 
``acis_thermal_check`` as a Python package, which can then be imported into any 
Python script using the same ``python`` executable.

If you are doing frequent development and would like to be able to change the 
code on the fly and re-run without having to reinstall the code every time, you
can use the ``develop`` option of ``setup.py``, which lets you run the code from
the source directory itself:

.. code-block:: bash

    [~]$ python setup.py develop

All of the above presumes that you have write access to the Python stack which 
you are using. If you do not (e.g., it is flight Ska), then you can still 
install and/or develop a custom version of the package. You can do that by using 
the ``--user`` flag in addition to either of the above options:

.. code-block:: bash

    [~]$ python setup.py install --user

or 

.. code-block:: bash

    [~]$ python setup.py develop --user

This installs packages under the ``$HOME/.local`` directory structure. However, it 
is much more desirable to test in your own Ska environment. For information on how 
to create one, go `here <https://github.com/sot/skare3/wiki/Ska3-runtime-environment-for-users>`_. 




