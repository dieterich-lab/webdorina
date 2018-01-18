#!/usr/bin/env python
# coding=utf-8
"""
This script processes a regulator directory hierarchy containing 
species, genomes, and associated regulators and produces track hub
text files for use with the UCSC genome browser.

It's not at all a pretty script but it works for us.  YMMV.  Patches
are most welcome.

col 5th must be 0 (zero)
remove _ (dash) from 1st col
"""
from __future__ import print_function
from __future__ import unicode_literals
import os
import json
import shutil
import subprocess
from subprocess import CalledProcessError

# paths
DATA_PATH = os.path.join("/data/projects/doRiNA2/")
HUB_PATH = os.path.join("/data/dorinaHub")
GENOMES_PATH = os.path.join(DATA_PATH, "genomes")
REGULATORS_PATH = os.path.join(DATA_PATH, "regulators")

# paths to kent executables
bedToBigBed = "/usr/local/bin/bedToBigBed"
bedSort = "/usr/local/bin/bedSort"

# ugly global variable
HUB_GENOMES = []  # genomes.txt


# parse json file and return id and experiment
def json_parse(json_file):
    with open(json_file) as data_file:
        data = json.load(data_file)
    data_file.close()
    return data[0]  # the json files contain one-element lists


def generate_html_desc(path, description, methods, references):
    with open(path, 'w+') as desc_file:
        if description:
            desc_file.write("<H2>Description</H2>")
            desc_file.write(description.encode('utf-8'))
        if methods:
            desc_file.write("<H2>Methods</H2>")
            desc_file.write(methods.encode('utf-8'))
        if references:
            desc_file.write("<H2>References</H2>")
            desc_file.write(references.encode('utf-8'))
    desc_file.close()


def convert_bed_to_bigbed(bed_path, bb_path, remove_scores_path, coordinates):
    # skip conversion if conversion already done in the past
    if os.path.exists(bb_path):
        return

    print(">>>>> START " + bed_path)
    try:
        # Replace score field with "0"
        # Make sure we have only 6 columns
        with open(bed_path, 'r') as f, open(remove_scores_path, 'w') as g:
            for line in f:
                fields = line.split('\t')
                new_line = '\t'.join(fields[0:4] + ["0"] + [fields[5]]) + "\n"
                g.write(new_line)

        # sort file
        subprocess.call([bedSort, remove_scores_path, remove_scores_path])
        # convert
        subprocess.call([bedToBigBed, remove_scores_path, coordinates, bb_path])
        print(">>>>> DONE " + bb_path)
    except CalledProcessError as e:
        print("ERROR: " + e.returncode)


# for each species
def process_hierarchy(root):
    """Traverse a hierarchy of species/genomes/regulators, converting
metadata from JSON manifests into track information."""
    for sp in os.listdir(root):
        # trackDb.txt
        PARENTS = []
        TRACK_PARENTS_ENTRY = []
        TRACK_SLAVES_ENTRY = []

        # browse for all genomes
        for g in os.listdir(os.path.join(root, sp)):  # genome list
            # create target dir for genome
            hub_genome_dir = os.path.join(HUB_PATH, sp, g)
            if not os.path.exists(hub_genome_dir):
                os.makedirs(hub_genome_dir)

            # for all files with metadata in current genome
            for f in sorted(os.listdir(os.path.join(root, sp, g))):
                # only work on json manifests
                if f[-4:] != "json":
                    continue
                # ignore concatenated files
                if "_all.json" in f:
                    continue
                # ignore dummy files
                if "dummy.json" in f:
                    continue

                basename = f[:-5]

                json_path = os.path.join(root, sp, g, f)
                json_info = json_parse(json_path)
                print(json_path)

                parent = json_info['experiment'].replace(' ', '-')
                if "miRNA" in parent:
                    longLabel = parent
                else:
                    longLabel = json_info['summary'].replace("\n", ' ')

                # run conversion only for associated bed files
                bed_path = os.path.join(root, sp, g, basename + ".bed")
                if os.path.exists(bed_path):
                    data_file_type = "bigBed"
                    data_file_ext = "bb"
                    bb_path = os.path.join(hub_genome_dir, basename + ".bb")
                    remove_scores_path = os.path.join(
                        hub_genome_dir, basename + "bed.0")
                    coordinates = os.path.join(
                        GENOMES_PATH, sp, g, g + ".genome")
                    convert_bed_to_bigbed(bed_path,
                                          bb_path,
                                          remove_scores_path,
                                          coordinates)

                bigwig_path = os.path.join(root, sp, g, basename + ".bw")
                if os.path.exists(bigwig_path):
                    data_file_type = "bigWig"
                    data_file_ext = "bw"
                    # copy the data file to hub target dir
                    shutil.copy2(bigwig_path, os.path.join(
                        hub_genome_dir, basename + ".bw"))

                # add parent track entry
                # experiment name for the first json entry
                # <- must be adjusted ???     # slave track TODO
                if json_info[
                    'experiment'] not in PARENTS and parent not in PARENTS:
                    PARENTS.append(parent)
                    TRACK_PARENTS_ENTRY.append([
                        "track " + parent,
                        "superTrack on",
                        "shortLabel " + parent,
                        "longLabel " + parent,
                    ])

                track_info = [
                    "track " + basename,
                    "parent " + parent,
                    "bigDataUrl " + basename + '.' + data_file_ext,
                    "shortLabel " + basename,
                    "longLabel " + longLabel,
                    "type " + data_file_type + " 6",
                    "html " + basename
                ]

                if 'autoScale' in json_info and json_info['autoScale'] == 'on':
                    track_info.append("autoScale on")

                # add child track entry
                TRACK_SLAVES_ENTRY.append(track_info)

                # write html desc file
                generate_html_desc(os.path.join(hub_genome_dir, basename + ".html"),
                                   json_info['description'],
                                   json_info['methods'],
                                   json_info['references'])
            # write trackDB.txt file
            with open(os.path.join(
                    hub_genome_dir, "trackDb.txt"), "wb") as track_file:
                for p in TRACK_PARENTS_ENTRY:
                    for e in p:
                        track_file.write(e.encode('utf-8') + "\n")
                    track_file.write(b"\n")
                for s in TRACK_SLAVES_ENTRY:
                    for e in s:
                        track_file.write(e.encode('utf-8') + "\n")
                    track_file.write(b"\n")
            track_file.close()

            # gather information for genomes.txt
            HUB_GENOMES.append(
                ["genome " + g + "\n" + "trackDb " + sp + "/" + g + "/trackDb.txt\n"])


# start
process_hierarchy(REGULATORS_PATH)

# write genomes.txt
with open(os.path.join(HUB_PATH, "genomes.txt"), "wb") as track_genomes_file:
    for g in HUB_GENOMES:
        track_genomes_file.write(g[0])
        track_genomes_file.write(b"\n")
track_genomes_file.close()