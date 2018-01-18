#!/usr/bin/env python
# coding=utf-8
"""
Concatenate JSON manifests to provide collections of all related
experiments.
"""
from __future__ import print_function
from __future__ import unicode_literals
import os
import json
import glob
import subprocess
import re
from collections import defaultdict

DATA_PATH = os.path.join("/data/projects/doRiNA2/")
REGULATORS_PATH = os.path.join(DATA_PATH, "regulators")
OUTPUT_PATH = REGULATORS_PATH  # os.path.join(DATA_PATH, "concats")
bedtools = os.path.join("/usr/bin/bedtools")


# parse json file and return id and experiment
def json_parse(json_file):
    with open(json_file) as data_file:
        data = json.load(data_file)
    data_file.close()
    return data[0]


# :: Dict -> String -> String -> String -> IO ()
def concatenate(table, assembly, source_path, target_path):
    # bail out if table is empty
    if not table:
        return

    # prepare output directory
    if not os.path.exists(target_path):
        os.makedirs(target_path)

    for experiment in table:
        basename = os.path.join(
            target_path, "{0}_{1}_all".format(experiment, assembly))
        filename_json = basename + '.json'
        filename_bed = basename + '.bed'

        # collect sites count from each json file
        filenames = [os.path.join(
            source_path, j['id'] + '.json') for j in table[experiment]]
        sites = 0
        for json_file in filenames:
            data = json_parse(json_file)
            sites += data['sites']

        # concatenate the associated bed files
        filenames = [os.path.join(
            source_path, j['id'] + '.bed') for j in table[experiment]]
        with open(filename_bed, "w") as f:
            for bed_file in filenames:
                out = subprocess.check_output(
                    [bedtools, 'bed12tobed6', '-i', bed_file])
                f.write(out)
                f.flush()

        # create new JSON file for
        json_contents = [
            {"id": "{0}_{1}_all".format(experiment, assembly),
             "experiment": experiment,
             "summary": "all {} target sites ({})".format(experiment, assembly),
             "description": "",
             "methods": "",
             "references": "",
             "sites": sites
             }
        ]

        with open(filename_json, "w") as f:
            json.dump(json_contents, f, indent=2)


# :: String -> Dict
def gather_experiments(path):
    data_by_experiment = defaultdict(list)
    for json_file in glob.glob(path + '/*.json'):
        # ignore those files that end on "_all.json"
        if re.match('.*_all.json', json_file):
            print('skipping ' + json_file)
            continue

        with open(json_file, "r") as f:
            data = json.load(f)

        # only process those files that have a single data set
        if len(data) == 1:
            data = data[0]
            data_by_experiment[data['experiment']].append(data)
        else:
            print('multi ' + json_file)

    return data_by_experiment


def walk_tree():
    # for each species
    for species in os.listdir(REGULATORS_PATH):
        species_path = os.path.join(REGULATORS_PATH, species)

        # and for each genome assembly
        for genome in os.listdir(species_path):
            genome_path = os.path.join(species_path, genome)

            # create a big lookup table of all json data by experiment
            table = gather_experiments(genome_path)

            # for each of the experiments, create a concatenated json file
            # containing all data sets
            target_path = os.path.join(OUTPUT_PATH, species, genome)
            concatenate(table, genome, genome_path, target_path)


walk_tree()
