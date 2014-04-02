#!/usr/bin/env python

from flask import Flask, render_template, jsonify
from argparse import Namespace
from dorina import utils, config

# basic doRiNA settings
options = Namespace()
options.data = Namespace()
#options.data.path = "/home/kblin/mpi/code/data"
options.data.path = "/data/projects/doRiNA2/"

app = Flask(__name__)

@app.route('/')
def index():
    return render_template('index.html')


@app.route('/clades')
def list_clades():
    config.set_config(options)
    available_genomes = utils.get_genomes()
    clades = available_genomes.keys()
    return jsonify(dict(clades=clades))


@app.route('/genomes/<clade>')
def list_genomes(clade):
    config.set_config(options)
    available_genomes = utils.get_genomes()
    if not clade in available_genomes:
        return jsonify(dict(clade=''))
    genomes = available_genomes[clade].keys()
    genomes.sort()
    return jsonify(dict(clade=clade, genomes=genomes))


@app.route('/assemblies/<clade>/<genome>')
def list_assemblies(clade, genome):
    config.set_config(options)
    available_genomes = utils.get_genomes()
    if not clade in available_genomes:
        return jsonify(dict(clade=''))
    if not genome in available_genomes[clade]:
        return jsonify(dict(clade=clade, genome=''))
    assemblies = available_genomes[clade][genome].keys()
    assemblies.sort()
    return jsonify(dict(clade=clade, genome=genome, assemblies=assemblies))


@app.route('/regulators/<clade>/<genome>/<assembly>')
def list_regulators(clade, genome, assembly):
    config.set_config(options)
    available_regulators = utils.get_regulators()
    if not clade in available_regulators:
        return jsonify(dict(clade=''))
    if not genome in available_regulators[clade]:
        return jsonify(dict(clade=clade, genome=''))
    if not assembly in available_regulators[clade][genome]:
        return jsonify(dict(clade=clade, genome=genome, assembly=''))

    regulators = {}
    for key, val in available_regulators[clade][genome][assembly].items():
        regulators[key] = val

    return jsonify(regulators)


@app.route('/search', methods=['POST'])
def search():
    results = [
        dict(track='FAKE', gene='FAKE1', data_source='PAR-CLIP', score=42,
             site="FAKE_0123456", location="chr23:1234-5678", strand="+")
    ]
    return jsonify(dict(results=results))


if __name__ == "__main__":
    app.run(debug=True)
