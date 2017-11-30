#!/usr/bin/env python
# coding=utf-8

from __future__ import print_function
from __future__ import unicode_literals
import shutil
import daemon
from os import path
from redis import StrictRedis


def callback(message):
    if message['data'].startswith('sessions:'):
        uuid = message['data'].split(':')[-1]
        session_dir = path.join('/tmp', "dorina-{}".format(uuid))
        print("deleting {session_dir}".format(session_dir=session_dir))
        if path.exists(session_dir):
            shutil.rmtree(session_dir, ignore_errors=True)


def main():
    r = StrictRedis()
    r.config_set('notify-keyspace-events', 'Ex')
    p = r.pubsub(ignore_subscribe_messages=True)
    p.psubscribe(**{'__keyevent@0__:expired': callback})
    # pop the subscribe message
    p.get_message()
    for message in p.listen():
        pass


if __name__ == "__main__":
    with daemon.DaemonContext():
        main()
