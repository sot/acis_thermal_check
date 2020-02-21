#!/usr/bin/env python
from setuptools import setup
import glob

templates = glob.glob("templates/*")
scripts = glob.glob("scripts/*")

setup(name='acis_thermal_check',
      packages=["acis_thermal_check"],
      use_scm_version=True,
      setup_requires=['setuptools_scm', 'setuptools_scm_git_archive'],
      description='ACIS Thermal Model Library',
      author='John ZuHone',
      author_email='john.zuhone@cfa.harvard.edu',
      url='http://github.com/acisops/acis_thermal_check',
      data_files=[('templates', templates)],
      scripts=scripts,
      include_package_data=True,
      )
