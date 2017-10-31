.. _install:

Installation and Development
----------------------------

This assumes that you have a cloned copy of ``acis_thermal_check`` from
http://github.com/acisops/acis_thermal_check. To install the package simply 
run:

.. code-block:: bash

    [~]$ python setup.py install

from the top-level directory of the package. This will install 
``acis_thermal_check`` as a Python package, which can then be imported into any 
Python script using the same ``python`` executable.

If you are doing frequent development and would like to be able to change the code
on the fly and re-run without having to reinstall the code every time, you can use the
``develop`` option of ``setup.py``, which lets you run the code from the source directory
itself:

.. code-block:: bash

    [~]$ python setup.py develop

