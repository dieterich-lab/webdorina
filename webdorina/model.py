#!/usr/bin/env python
# -*- coding: utf-8
"""
Created on 09:03 27/02/2018 2018 


"""
flask_sqlalchemy
from flask_sqlalchemy import SQLAlchemy

db = SQLAlchemy()


class Result(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    experiment = db.Column(db.String(80), unique=True, nullable=False)
    reference = db.Column(db.String(80), unique=True, nullable=False)
    description = db.Column(db.String(None), unique=True, nullable=False)
    assembly = db.Column(db.String(80), unique=True, nullable=False)
    organism = db.Column(db.String(80), unique=True, nullable=False)
    target = db.Column(db.String(80), unique=True, nullable=False)

    bed = db.Column()
    bb = db.Column()

    def __repr__(self):
        return '<Result %r>' % self.experiment, self.target, self.assembly
