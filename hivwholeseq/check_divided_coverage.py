# vim: fdm=marker
'''
author:     Fabio Zanini
date:       30/10/13
content:    After division into fragments, check quickly coverage and minor
            allele frequencies, just to spot major issues.
'''
# Modules
import argparse
import numpy as np
from Bio import SeqIO
import matplotlib.pyplot as plt

from hivwholeseq.datasets import MiSeq_runs
from hivwholeseq.miseq import read_types
from hivwholeseq.reference import load_HXB2
from hivwholeseq.filenames import get_divided_filename, get_reference_premap_filename
from hivwholeseq.one_site_statistics import get_allele_counts_insertions_from_file
from hivwholeseq.minor_allele_frequency import get_minor_allele_counts
from hivwholeseq.samples import samples



# Functions
def plot_coverage_minor_allele(counts, suptitle):
    '''Plot the coverage and the minor allele frequency'''
    cov = counts.sum(axis=1)
    cov_tot = cov.sum(axis=0)
    counts_minor = get_minor_allele_counts(counts)[1, :, :, 1]
    # Use pseudocounts so-so (it is only rough)
    nus_minor = 1.0 * counts_minor / (1 + cov)

    import matplotlib.pyplot as plt
    from matplotlib import cm
    fig, axs = plt.subplots(1, 2, figsize=(10, 6))
    axs[0].plot(cov_tot.T, lw=2, c='k', label=read_types)
    axs[0].set_xlabel('Position [bases]')
    axs[0].set_ylabel('Coverage')

    for i, nu_minor in enumerate(nus_minor):
        color = cm.jet(int(255.0 * i / len(read_types)))
        axs[1].plot(nu_minor, label=read_types, c=color)
        axs[1].scatter(np.arange(counts.shape[-1]), nu_minor,
                       s=30, c=color,
                       label=read_types)
    axs[1].set_xlabel('Position [bases]')
    axs[1].set_ylabel('Minor allele frequency')
    axs[1].set_yscale('log')
    fig.suptitle(suptitle, fontsize=18)

    plt.tight_layout(rect=(0, 0, 1, 0.95))

    plt.ion()
    plt.show()
    


def check_division(seq_run, adaID, fragment, qual_min=35,
                   reference='HXB2', maxreads=-1, VERBOSE=0):
    '''Check division into fragments: coverage, etc.'''
    # Specify the dataset
    dataset = MiSeq_runs[seq_run]
    data_folder = dataset['folder']

    refseq = SeqIO.read(get_reference_premap_filename(data_folder, adaID, fragment),
                        'fasta')

    # Scan reads
    input_filename = get_divided_filename(data_folder, adaID, fragment, type='bam')
    counts, inserts = get_allele_counts_insertions_from_file(input_filename,
                                                             len(refseq),
                                                             maxreads=maxreads,
                                                             VERBOSE=VERBOSE)

    # Plot results
    title=', '.join(map(lambda x: ' '.join([x[0], str(x[1])]),
                        [['run', seq_run],
                         ['adaID', adaID],
                         ['fragment', fragment],
                         ['maxreads', maxreads],
                        ]))
    plot_coverage_minor_allele(counts,
                               suptitle=title)


                



# Script
if __name__ == '__main__':

    # Parse input args
    parser = argparse.ArgumentParser(description='Check consensus')
    parser.add_argument('--run', required=True,
                        help='Seq run to analyze (e.g. Tue28)')
    parser.add_argument('--adaIDs', nargs='*',
                        help='Adapter IDs to analyze (e.g. TS2)')
    parser.add_argument('--fragments', nargs='*',
                        help='Fragment to map (e.g. F1 F6)')
    parser.add_argument('--maxreads', type=int, default=1000,
                        help='Number of reads analyzed')
    parser.add_argument('--verbose', type=int, default=0,
                        help='Verbosity level [0-3]')

    args = parser.parse_args()
    seq_run = args.run
    adaIDs = args.adaIDs
    fragments = args.fragments
    maxreads = args.maxreads
    VERBOSE = args.verbose

    # Specify the dataset
    dataset = MiSeq_runs[seq_run]
    data_folder = dataset['folder']

    # If the script is called with no adaID, iterate over all
    if not adaIDs:
        adaIDs = MiSeq_runs[seq_run]['adapters']
    if VERBOSE >= 3:
        print 'adaIDs', adaIDs

    # Iterate over samples and fragments
    for adaID in adaIDs:
        samplename = dataset['samples'][dataset['adapters'].index(adaID)]
        fragments_sample = samples[samplename]['fragments']
        if VERBOSE:
            print adaID, samplename

        for fragment in fragments_sample:
            frag_gen = fragment[:2]
            if (fragments is None) or (frag_gen in fragments):
                check_division(seq_run, adaID, fragment,
                               maxreads=maxreads,
                               VERBOSE=VERBOSE)


