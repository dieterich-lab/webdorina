#!/usr/bin/env python3
# -*- coding: utf-8 -*-
import os, sys, logging, site

# The path of the webdorina project directory is the same as the directory of this file
PROJECT_DIR = os.path.dirname(os.path.realpath(__file__))

logging.basicConfig(stream=sys.stderr)

site.addsitedir(PROJECT_DIR)
sys.path.append(PROJECT_DIR)

from webdorina import app as application
