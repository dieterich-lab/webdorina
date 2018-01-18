# !/usr/bin/env python3
# coding=utf-8

from setuptools import setup, find_packages

setup(
    name='webdorina',
    version='0.5',
    url='https://github.com/dieterich-lab/webdorina',
    license='AGPL-3.0 ',
    author="Kai Blin",
    author_email="kai.blin@age.mpg.de",
    maintainer="Thiago Britto Borges",
    maintainer_email="thiago.brittoborges@uni-heidelberg.de",
    keywords="bioinformatics",
    packages=find_packages(),
    description='web front-end for the doRiNA database',
    include_package_data=True,
    package_data={'wedorina.test.data': ['*'],
                  '': ['config.json']},
    install_requires='rq redis flask dorina daemon'.split(),
    tests_require=['nose']
)

