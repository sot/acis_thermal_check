#!/usr/bin/env python
from setuptools import setup, find_packages
import glob

scripts = glob.glob("acis_thermal_check/*_check/*_check.py")
templates = glob.glob("templates/*")
model_spec = glob.glob("acis_thermal_check/*_check/*.json")

print find_packages()
print templates
print model_spec
print scripts

setup(name='acis_thermal_check',
      packages=find_packages(),
      version='1.0.0',
      description='ACIS Thermal Model Library',
      author='John ZuHone',
      author_email='jzuhone@gmail.com',
      url='http://github.com/acisops/acis_thermal_check',
      download_url='https://github.com/acisops/acis_thermal_check/tarball/1.0.0',
      data_files=[('templates', templates),
                  ('model_spec', model_spec)],
      scripts=scripts,
      classifiers=[
          'Intended Audience :: Science/Research',
          'Operating System :: OS Independent',
          'Programming Language :: Python :: 2.7',
      ],
      )
