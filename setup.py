#!/usr/bin/env python
from setuptools import setup, find_packages
import glob

templates = glob.glob("templates/*")
model_spec = glob.glob("acis_thermal_check/*_check/*.json")

print find_packages()
print templates
print model_spec

entry_points = {}
entry_points['console_scripts'] = [
    'dea_check = acis_thermal_check.dea_check.dea_check:main',
    'dpa_check = acis_thermal_check.dpa_check.dpa_check:main',
    'psmc_check = acis_thermal_check.psmc_check.psmc_check:main',
]


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
      classifiers=[
          'Intended Audience :: Science/Research',
          'Operating System :: OS Independent',
          'Programming Language :: Python :: 2.7',
      ],
      entry_points=entry_points,
      )
