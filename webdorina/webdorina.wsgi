#!/usr/bin/env python
# coding=utf-8
import os
import sys
import logging
import site

# The path of the webdorina project directory is the same as the directory of this file
PROJECT_DIR = os.path.dirname(os.path.realpath(__file__))

logging.basicConfig(stream=sys.stderr)

site.addsitedir(PROJECT_DIR)
sys.path.append(PROJECT_DIR)

from webdorina import app as application
