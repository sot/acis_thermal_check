#!/usr/bin/env python
from setuptools import setup
import glob

templates = glob.glob("templates/*")
data = glob.glob("data/*")

setup(name='acis_thermal_check',
      packages=["acis_thermal_check"],
      use_scm_version=True,
      setup_requires=['setuptools_scm', 'setuptools_scm_git_archive'],
      description='ACIS Thermal Model Library',
      author='John ZuHone',
      author_email='john.zuhone@cfa.harvard.edu',
      url='http://github.com/acisops/acis_thermal_check',
      data_files=[('templates', templates), ('data', data)],
      include_package_data=True,
      )
