# vim: fdm=marker
'''
author:     Fabio Zanini
date:       08/10/14
content:    Module containing basic paths for the whole analysis.
'''
# Modules
import os

import hivwholeseq as self


# Globals
stampy_bin = None
spades_bin = None
bwa_bin = None
# FIXME: use env vars and similia
if os.path.isdir('/media/FZ_MPI/HIV_Sweden/'):
    root_data_folder = '/media/FZ_MPI/HIV_Sweden/'
    stampy_bin = '/usr/bin/stampy'
elif os.path.isdir('/var/www/hivwholeweb/'):
    root_data_folder = '/var/www/hivwholeweb/app/hiv/static/data/'
elif os.path.isdir('/home/fabio/') and (not os.path.isdir('/ebio/ag-neher/share/data')):
    root_data_folder = '/home/fabio/university/phd/sequencing/data/'
else:
    root_data_folder = '/ebio/ag-neher/share/data/MiSeq_HIV_Karolinska/'
    fasttree_bin = 'fasttree'
    stampy_bin = '/ebio/ag-neher/share/programs/bundles/stampy-1.0.22/stampy.py'
    spades_bin = '/ebio/ag-neher/share/programs/bundles/SPAdes-2.5.0-Linux/bin/spades.py'
    bwa_bin = '/ebio/ag-neher/share/programs/bin/bwa'

if os.path.isdir('/home/fabio/'):
    fasttree_bin = 'FastTree'
else:
    fasttree_bin = 'fasttree'

tmp_folder = root_data_folder+'tmp/'
reference_folder = root_data_folder+'reference/'
theory_folder = root_data_folder+'theory/'
table_folder = self.__path__[0] + '/tables/'
table_filename = table_folder+'HIV_reservoir_all.xlsx'



# Functions
def get_custom_reference_filename(reference, format='fasta'):
    '''Get the filename of a custom reference sequence'''
    filename = reference
    filename = filename+'.'+format
    return reference_folder+filename


def get_custom_alignment_filename(aliname, format='fasta'):
    '''Get the filename of a custom alignment'''
    filename = 'alignments/'+aliname
    filename = filename+'.'+format
    return reference_folder+filename
