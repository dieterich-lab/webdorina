#!/usr/bin/env python3
# -*- coding: utf-8 -*-

import site
site.addsitedir('/home/carina/.local/lib/python3.4/site-packages')

from flask import Flask

app = Flask(__name__)

@app.route("/")
def hello():
    return "<h1 style='color:blue'>Hello There!</h1>"

if __name__ == "__main__":
    app.run(host='0.0.0.0', debug=True, port=49200)