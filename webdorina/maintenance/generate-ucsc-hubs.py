#!/usr/bin/env python
# coding=utf-8
"""
This script processes a regulator directory hierarchy containing 
species, genomes, and associated regulators and produces track hub
text files for use with the UCSC genome browser.

col 5th must be 0 (zero)
remove _ (dash) from 1st col

Error line 2027 of /Volumes/prj/trackhubs/dorinaHub/h_sapiens/hg38/PARCLIP_ELAVL1MNASE_hg19.bed.0: name [PARCLIP#ELAVL1MNASE_hg19*NM_001102398_2219_2258NM_001102398_2219_2258NM_001102398_2259_2298NM_001102398_2259_2298NM_001102398_2299_2338NM_001102398_2299_2338NM_001102398_2339_2378NM_001102398_2339_2378NM_001102398_2379_2418NM_001102398_2379_2418NM_001102398_2419_2458NM_001102398_] is too long (must not exceed 255 characters)
Error line 6499 of /Volumes/prj/trackhubs/dorinaHub/h_sapiens/hg38/PARCLIP_AGO2MNASE_hg19.bed.0: name [PARCLIP#AGO2MNASE_hg19*NM_012342_1095_1134NM_012342_1097_1136NM_012342_1137_1176NM_012342_1142_1181NM_012342_1177_1216NM_012342_1185_1224NM_012342_1225_1264NM_012342_1225_1264NM_012342_1265_1304NM_012342_1276_1315NM_012342_1316_1355NM_012342_1319_1358NM_012342_1359_1398NM_01234] is too long (must not exceed 255 characters)

chmod -R 0755

for f in *.bed.0; /Users/tbrittoborges/bedSort $f $f; /Users/tbrittoborges/bedToBigBed $f  /Volumes/prj/dorina2/genomes/h_sapiens/hg38/hg38.chrom.sizes  (basename $f .bed.0).bb; end


curl http://hgdownload.soe.ucsc.edu/admin/exe/macOSX.x86_64/bedSort

~/hubCheck http://porta.dieterichlab.org/trackhubs/dorinaHub/hub.txt
"""
from __future__ import print_function
from __future__ import unicode_literals

import json
import os
import subprocess
import sys
from io import open
from pathlib import Path
from subprocess import CalledProcessError

DATA_PATH = Path("/Volumes/prj/dorina2/")
HUB_PATH = Path("/Volumes/prj/trackhubs/dorinaHub/")
GENOMES_PATH = Path(DATA_PATH / "genomes/")
REGULATORS_PATH = Path(DATA_PATH, "regulators")
HUB_GENOMES = []  # genomes.txt

# kent executables
bedToBigBed = Path("/Users/tbrittoborges/bedToBigBed")
bedSort = Path("/Users/tbrittoborges/bedSort")


# parse json file and return id and experiment
def json_parse(json_file):
    with open(json_file) as data_file:
        data = json.load(data_file)
        return data[0]  # the json files contain one-element lists


def write_html_description(path, json_file):
    with open(path, 'w+') as desc_file:
        for field in ('description', 'methods', 'references'):
            if field in json_file:
                desc_file.write("<H2>{}</H2>\n".format(field))
                desc_file.write(str(json_file[field]) + '\n')


def convert_bed_to_bigbed(bed_path, bb_path, remove_scores_path, coordinates):
    print(">>>>> START " + str(bed_path))
    try:
        with open(bed_path) as file_in, \
                open(remove_scores_path, 'w') as file_out:
            for line in file_in:
                fields = line.rstrip().split('\t')
                try:
                    # Replace score field with "0"
                    # trims the name field

                    if len(fields) > 4:
                        new_line = '\t'.join(fields[0:3] + [fields[3][:254]]
                                             + ["0"] + [fields[5]]) + '\n'
                    else:
                        # bed file without strand HITSCLIP_FOX2Yeo2009_hg19.bed
                        new_line = '\t'.join(fields[0:3] + [fields[3][:254]]
                                             + ["0", '+']) + '\n'

                except IndexError:
                    print(">>>>> ERROR: problematic line in " + str(
                        bed_path) + line)
                    continue

                file_out.write(new_line)

        # sort file
        subprocess.call([bedSort, remove_scores_path, remove_scores_path])
        # convert
        subprocess.call([bedToBigBed, remove_scores_path, coordinates, bb_path])
        print(">>>>> DONE " + str(bb_path))
    except CalledProcessError as e:
        print("BigBedConversionError: ", e, bed_path)


def process_hierarchy(root):
    """
    Traverse a hierarchy of species/genomes/regulators, converting
    metadata from JSON manifests into track information.
    """
    root = Path(root)
    for sp in (r.name for r in root.iterdir() if r.is_dir()):
        # trackDb.txt
        parents = []
        track_parents_entry = []
        track_slaves_entry = []

        # browse for all genomes
        for genome in (g.name for g in (
                    GENOMES_PATH / sp).iterdir() if g.is_dir()):

            # create target dir for genome
            hub_dir = Path(HUB_PATH) / sp / genome
            if not hub_dir.exists():
                hub_dir.mkdir(parents=True)

            # for all files with metadata in current genome
            for f in (root / sp / genome).iterdir():

                # only work on json manifests
                if f.suffix != ".json":
                    continue
                elif f.stem == 'description':
                    continue

                try:
                    json_info = json_parse(root / sp / genome / f)
                except KeyError:
                    print('error with {}'.format(root / sp / genome / f))
                    sys.exit(0)

                parent = json_info['experiment'].replace(' ', '-')
                if "miRNA" in parent:
                    long_label = parent
                else:
                    long_label = json_info['summary'].replace("\n", ' ')

                # run conversion only for associated bed files
                data_file_type = "bigBed"
                data_file_ext = "bb"
                bed_path = (root / sp / genome / f.stem).with_suffix(".bed")
                bb_path = (hub_dir / f.stem).with_suffix(".bb")
                remove_scores_path = (hub_dir / f.stem).with_suffix(".bed.0")
                coordinates = (GENOMES_PATH / sp / genome / genome).with_suffix(
                    ".genome")
                try:
                    convert_bed_to_bigbed(bed_path,
                                          bb_path,
                                          remove_scores_path,
                                          coordinates)
                except CalledProcessError:
                    continue

                # add parent track entry
                # experiment name for the first json entry
                if json_info['experiment'] not in parents and \
                                parent not in parents:
                    parents.append(parent)
                    track_parents_entry.append([
                        "track " + parent + '-p',
                        "superTrack on",
                        "shortLabel " + parent,
                        "longLabel " + parent,
                    ])

                track_info = [
                    "track " + f.stem,
                    "parent " + parent + '-p',
                    "bigDataUrl " + str(f.stem) + '.' + data_file_ext,
                    "shortLabel " + str(f.stem).replace(genome, ''),
                    "longLabel " + long_label,
                    "type " + data_file_type + " 6",
                    "html " + str(f.stem),
                    'visibility squish']

                if 'autoScale' in json_info and json_info['autoScale'] == 'on':
                    track_info.append("autoScale on")

                # add child track entry
                track_slaves_entry.append(track_info)

                # write html desc file
                write_html_description(
                    json_file=json_info,
                    path=(hub_dir / f.stem).with_suffix(".html"))

            with open(hub_dir / Path("trackDb.txt"), "w") as track_file:
                for p in track_parents_entry:
                    for e in p:
                        track_file.write(e + "\n")
                    track_file.write("\n")
                for s in track_slaves_entry:
                    for e in s:
                        track_file.write(e + "\n")
                    track_file.write("\n")
            track_file.close()

            # gather information for genomes.txt
            HUB_GENOMES.append(["genome " + str(genome) + "\n" + "trackDb " +
                                str(sp) + "/" + str(genome) + "/trackDb.txt\n"])


# start
process_hierarchy(REGULATORS_PATH)

# write genomes.txt
with open(os.path.join(HUB_PATH, "genomes.txt"), "w") as track_genomes_file:
    for g in HUB_GENOMES:
        track_genomes_file.write(g[0])
        track_genomes_file.write("\n")
track_genomes_file.close()
