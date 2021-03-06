# vim: fdm=marker
'''
author:     Fabio Zanini
date:       14/10/13
content:    Quantify the distribution of insert sizes after mapping.
'''
# Modules
import os
import argparse
import pysam
import numpy as np

from hivwholeseq.sequencing.samples import load_sequencing_run
from hivwholeseq.sequencing.filenames import get_mapped_filename, get_premapped_filename, \
        get_insert_size_distribution_cumulative_filename, \
        get_insert_size_distribution_filename
from hivwholeseq.utils.mapping import pair_generator, convert_sam_to_bam



# Functions
def get_insert_size_distribution(data_folder, adaID, fragment, bins=None,
                                 maxreads=-1, VERBOSE=0, density=True):
    '''Get the distribution of insert sizes'''

    if maxreads <= 0:
        maxreads = 1e6
    
    insert_sizes = np.zeros(maxreads, np.int16)

    # Open BAM file
    if fragment == 'premapped':
        bamfilename = get_premapped_filename(data_folder, adaID, type='bam')
    else:
        bamfilename = get_mapped_filename(data_folder, adaID, fragment, type='bam',
                                          filtered=True)

    # Convert from SAM if necessary
    if not os.path.isfile(bamfilename):
        convert_sam_to_bam(bamfilename)

    # Open file
    with pysam.Samfile(bamfilename, 'rb') as bamfile:
        # Iterate over single reads (no linkage info needed)
        n_written = 0
        for i, reads in enumerate(pair_generator(bamfile)):

            if i == maxreads:
                if VERBOSE >= 2:
                    print 'Max reads reached:', maxreads
                break
        
            # Print output
            if (VERBOSE >= 3) and (not ((i +1) % 10000)):
                print (i+1)

            # If unmapped or unpaired, mini, or insert size mini, discard
            if reads[0].is_unmapped or (not reads[0].is_proper_pair) or \
               reads[1].is_unmapped or (not reads[1].is_proper_pair):
                continue
            
            # Store insert size
            i_fwd = reads[0].is_reverse
            insert_sizes[i] = reads[i_fwd].isize
            n_written += 1

    insert_sizes = insert_sizes[:n_written]
    insert_sizes.sort()

    # Bin it
    if bins is None:
        h = np.histogram(insert_sizes, density=density)
    else:
        h = np.histogram(insert_sizes, bins=bins, density=density)

    return insert_sizes, h


def plot_cumulative_histogram(data_folder, adaID, fragment, insert_sizes,
                              title=None,
                              ax=None,
                              show=False, savefig=False,
                              **kwargs):
    '''Plot cumulative histogram of insert sizes'''
    import matplotlib.pyplot as plt
    if ax is None:
        fig, ax = plt.subplots(1, 1)
    ax.plot(insert_sizes, np.linspace(0, 1, len(insert_sizes)), **kwargs)
    ax.set_xlabel('Insert size')
    ax.set_ylabel('Cumulative fraction')
    ax.set_xlim(-1, 1000)
    ax.set_ylim(-0.02, 1.02)
    if title is not None:
        ax.set_title(title)

    plt.tight_layout()

    if show:
        plt.ion()
        plt.show()

    if savefig:
        output_filename = get_insert_size_distribution_cumulative_filename(data_folder,
                                                                           adaID,
                                                                           fragment)
        from hivwholeseq.utils.generic import mkdirs
        from hivwholeseq.sequencing.filenames import get_figure_folder
        mkdirs(get_figure_folder(data_folder, adaID))
        fig.savefig(output_filename)


def plot_histogram(data_folder, adaID, fragment, h,
                   title=None,
                   ax=None,
                   show=False, savefig=False,
                   **kwargs):
    '''Plot histogram of insert sizes'''
    import matplotlib.pyplot as plt
    if ax is None:
        fig, ax = plt.subplots(1, 1)
    if title is not None:
        ax.set_title(title)
    x = 0.5 * (h[1][1:] + h[1][:-1])
    y = h[0]
    ax.plot(x, y, **kwargs)
    ax.set_xlabel('Insert size')
    ax.set_ylabel('Density')

    plt.tight_layout()

    if show:
        plt.ion()
        plt.show()

    if savefig:
        output_filename = get_insert_size_distribution_filename(data_folder, adaID,
                                                                fragment)

        from hivwholeseq.utils.generic import mkdirs
        from hivwholeseq.sequencing.filenames import get_figure_folder
        mkdirs(get_figure_folder(data_folder, adaID))
        plt.savefig(output_filename)



# Script
if __name__ == '__main__':

    # Input arguments
    parser = argparse.ArgumentParser(description='Get allele counts',
                                     formatter_class=argparse.ArgumentDefaultsHelpFormatter)    
    parser.add_argument('--run', required=True,
                        help='Seq run to analyze (e.g. Tue28)')
    parser.add_argument('--adaIDs', nargs='*',
                        help='Adapter IDs to analyze (e.g. TS2)')
    parser.add_argument('--fragments', nargs='*',
                        help='Fragments to analyze (e.g. F1 F6 or "premapped")')
    parser.add_argument('--verbose', type=int, default=0,
                        help='Verbosity level [0-3]')
    parser.add_argument('--maxreads', type=int, default=-1,
                        help='Maximal number of reads to analyze')
    parser.add_argument('--savefig', action='store_true',
                        help='Store figures')

    args = parser.parse_args()
    seq_run = args.run
    adaIDs = args.adaIDs
    fragments = args.fragments
    VERBOSE = args.verbose
    maxreads = args.maxreads
    savefig = args.savefig

    # Specify the dataset
    dataset = load_sequencing_run(seq_run)
    data_folder = dataset['folder']

    # If the script is called with no adaID, iterate over all
    samples = dataset.samples
    if adaIDs is not None:
        samples = samples.loc[samples.adapter.isin(adaIDs)]
    adaIDs = samples.adapter
    if VERBOSE >= 3:
        print 'adaIDs', adaIDs

    # If the script is called with no fragment, iterate over all
    if not fragments:
        fragments = ['F'+str(i) for i in xrange(1, 7)]
    if VERBOSE >= 3:
        print 'fragments', fragments

    # Set the bins
    bins = np.linspace(10, 1000, 100)

    # Make a single figure for the histograms
    import matplotlib.pyplot as plt
    from matplotlib import cm
    if not savefig:
        fig, axs = plt.subplots(1, 2, figsize=(15, 7))
        fig.suptitle('Insert size distribution')
    else:
        axs = [None, None]

    # Iterate over all requested samples
    for i, (samplename, sample) in enumerate(samples.iterrows()):
        adaID = sample.adapter
        if VERBOSE:
            print adaID, samplename,

        for j, fragment in enumerate(fragments):
            if VERBOSE:
                print fragment,

            isz, h = get_insert_size_distribution(data_folder, adaID, fragment,
                                                  bins=bins, maxreads=maxreads,
                                                  VERBOSE=VERBOSE)


            if not savefig:
                color = cm.jet(1.0 * (i * len(fragments) + j) / (len(adaIDs)*len(fragments)))
            else:
                color = 'b'

            plot_cumulative_histogram(seq_run, adaID, fragment, isz,
                                      ax=axs[1],
                                      lw=2,
                                      color=color,
                                      label=adaID+', '+samplename+', '+fragment,
                                      savefig=savefig)
            plot_histogram(seq_run, adaID, fragment, h, ax=axs[0],
                           lw=2,
                           color=color,
                           label=adaID+', '+samplename+', '+fragment,
                           savefig=savefig)

        if VERBOSE:
            print ''

    if not savefig:
        import matplotlib.pyplot as plt
        plt.legend(loc=4, fontsize=8)
        plt.tight_layout(rect=(0, 0, 1, 0.95))
        plt.ion()
        plt.show()


