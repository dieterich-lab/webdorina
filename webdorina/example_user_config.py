#!/usr/bin/env python
# -*- coding: utf-8
"""
Created on 15:08 18/01/2018 2018 

"""
import os

data_path=os.path.join(os.path.dirname(__file__), 'test', 'data')
SESSION_TTL=3600
RESULT_TTL=86400
REGULATORS_TTL=3600
MAX_RESULTS=100
SESSION_STORE="/tmp/dorina-{unique_id}"
HOST='0.0.0.0'
PORT=5000
