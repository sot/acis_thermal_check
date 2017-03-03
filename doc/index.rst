.. acis_thermal_check documentation master file

ACIS Thermal Model Tools (``acis_thermal_check``)
=================================================

Overview
--------

.. |Chandra_cmd_states| replace:: ``Chandra.cmd_states``
.. _Chandra_cmd_states: http://cxc.harvard.edu/mta/ASPECT/tool_doc/cmd_states/

.. |Ska_engarchive| replace:: ``Ska.engarchive``
.. _Ska_engarchive: http://http://cxc.cfa.harvard.edu/mta/ASPECT/tool_doc/eng_archive/

``acis_thermal_check`` is a library which provides the tools to use and maintain
the Chandra ACIS thermal models. These tools depend on the commanded states database
which is accessed primarily via the |Chandra_cmd_states|_ module, and the engineering
archive which is accessed via the |Ska_engarchive|_ module. More specifically,
``acis_thermal_check`` generates backstop load review outputs for checking ACIS
temperatures such as 1DEAMZT, 1DPAMZT, and 1PDEAAT. It also generates model validation
plots for these temperatures comparing predicted values to telemetry for the previous
three weeks.

Installation and Development
----------------------------

This assumes that you have a cloned copy of ``acis_thermal_check`` from
http://github.com/acisops/acis_thermal_check. If you have your own Python/Ska
environment available (on a laptop or some other machine), and you have write
permissions on it, to install the package simply run:

::

    python setup.py install

from the top-level directory of the package. This will install ``acis_thermal_check``
as a Python package, which can then be imported into any Python script using the same
``python`` executable.

If you are running and testing this package using the flight-approved Ska environment
on the HEAD LAN, you will not be able to directly install into this environment but
can install ``acis_thermal_check`` as a local package. In this case, the command
is slightly modified:

::

    python setup.py install --user

which will install the package under a path given by the ``site.USER_BASE`` variable
in Python, which on Linux is ``~/.local``. This path can be modified by setting the
environment variable ``PYTHONUSERBASE`` to the desired path before running the above
command. Then you will be able to ``import acis_thermal_check`` from any Python script
so long as you use the same ``python`` executable.

If you are doing frequent development and would like to be able to change the code
on the fly and re-run without having to reinstall the code every time, you can use the
``develop`` option of ``setup.py``, which lets you run the code from the source directory
itself:

::

    python setup.py develop [--user]

where the ``--user`` flag is again only necessary if you do not have write permissions for
the Python environment you are installing into. If you use ``develop``, all imports of
the ``acis_thermal_check`` package will refer back to the code in the source directory
that you are working from.