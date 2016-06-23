#!/usr/bin/env python
from setuptools import setup
import glob

scripts = glob.glob("scripts/*")

setup(name='acis_thermal_check',
      packages=['acis_thermal_check'],
      version='1.0.0',
      description='ACIS Thermal Model Validation Library',
      author='John ZuHone',
      author_email='jzuhone@gmail.com',
      url='http://github.com/acisops/acis_thermal_check',
      download_url='https://github.com/acisops/acis_thermal_check/tarball/1.0.0',
      scripts=scripts,
      classifiers=[
          'Intended Audience :: Science/Research',
          'Operating System :: OS Independent',
          'Programming Language :: Python :: 2.7',
          'Programming Language :: Python :: 3.4',
          'Programming Language :: Python :: 3.5',
          'Topic :: Scientific/Engineering :: Visualization',
      ],
      )
