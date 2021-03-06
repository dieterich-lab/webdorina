#!/usr/bin/env python
# coding=utf-8
import os
import sys
import logging
import site

# The path of the webdorina project directory is the same as the directory of this file
PROJECT_DIR = os.path.dirname(os.path.realpath(__file__))

logging.basicConfig(level=logging.DEBUG)

site.addsitedir(PROJECT_DIR)
sys.path.append(PROJECT_DIR)

from webdorina.app import app as application
