# vim: fdm=marker
'''
author:     Fabio Zanini
date:       11/02/14
content:    Collection of functions to do single site statistics (allele counts,
            coverage, allele frequencies) on patients.
'''
# Modules
import numpy as np
from Bio.Seq import Seq
from Bio.Alphabet.IUPAC import ambiguous_dna
from Bio import SeqIO

from hivwholeseq.miseq import alpha



# Functions
def get_allele_frequency_trajectories(pname, samples, fragment, qual_min=30, VERBOSE=0):
    '''Scan the reads of all samples and write to a single file'''
    if VERBOSE >= 1:
        print 'Getting allele frequency trajectories:', pname

    from hivwholeseq.patients.filenames import get_initial_consensus_filename, \
            get_mapped_to_initial_filename, get_allele_frequency_trajectories_filename, \
            get_allele_count_trajectories_filename
    from hivwholeseq.one_site_statistics import get_allele_counts_insertions_from_file, \
            get_allele_counts_insertions_from_file_unfiltered, \
            filter_nus

    refseq = SeqIO.read(get_initial_consensus_filename(pname, fragment), 'fasta')

    # Prepare output data structures
    cos_traj = np.zeros((len(samples), len(alpha), len(refseq)), int)
    nus_traj = np.zeros((len(samples), len(alpha), len(refseq)))
    
    for it, sample in enumerate(samples):
        if VERBOSE >= 2:
            print pname, it, sample

        input_filename = get_mapped_to_initial_filename(pname, sample, fragment, type='bam')
        (counts, inserts) = get_allele_counts_insertions_from_file_unfiltered(input_filename,
                                                                   len(refseq),
                                                                   qual_min=qual_min,
                                                                   VERBOSE=VERBOSE)
        # Take the total counts, blending in the read types
        cou = counts.sum(axis=0)
        cos_traj[it] = cou

        # Take the filtered frequencies, blending in the read types
        nu = filter_nus(counts)
        nus_traj[it] = nu

    #FIXME: test, etc.

    return (cos_traj, nus_traj)


def plot_allele_frequency_trajectories(times, nus, title='', VERBOSE=0,
                                       threshold=0.1, options=[]):
    '''Plot the allele frequency trajectories from a patient'''
    import matplotlib.pyplot as plt
    from matplotlib import cm

    fig, ax = plt.subplots(1, 1)
    for i in xrange(nus.shape[2]):
        for j in xrange(nus.shape[1]):
            nu = nus[:, j, i]
            if (nu[0] < 0.5) and (nu > threshold).any():

                # Use dashed lines for synonymous if requested
                if 'syn-nonsyn' in options:
                    cod_initial = alpha[nus[0, :, i - i%3: i - i%3 + 3].argmax(axis=0)]
                    cod_mut = cod_initial.copy()
                    cod_mut[i%3] = alpha[j]
                    if ('-' in cod_mut) or \
                       (str(Seq(''.join(cod_initial), ambiguous_dna).translate()) != \
                        str(Seq(''.join(cod_mut), ambiguous_dna).translate())):
                        ls = '-'
                    else:
                        ls= '--'
                else:
                    ls = '-'

                ax.plot(times, nu + 1e-4, lw=1.5, ls=ls,
                        color=cm.jet(int(255.0 * i / nus.shape[2])))

    ax.set_xlim(times[0] -10, times[-1] + 10)
    ax.set_xlabel('Time [days from initial sample]')
    ax.set_ylim(9e-5, 1.5)
    ax.set_yscale('log')
    ax.set_ylabel(r'$\nu$', fontsize=16)
    ax.set_title(title)


def plot_allele_frequency_trajectories_3d(times, nus, title='', VERBOSE=0,
                                          threshold=0.1):
    '''Plot the allele freq traj in 3D'''
    from mpl_toolkits.mplot3d import Axes3D
    from matplotlib import cm
    import matplotlib.pyplot as plt
    import numpy as np

    fig = plt.figure(figsize=(12, 12))
    ax = fig.gca(projection='3d')
    ax.view_init(5, 150)

    for i in xrange(nus.shape[2]):
        for j in xrange(nus.shape[1]):
            nu = nus[:, j, i]
            if (nu[0] < 0.5) and (nu > threshold).any():
                ax.plot(times, [i] * len(times), np.log10(nu + 1e-4),
                        lw=2,
                        color=cm.jet(int(255.0 * i / nus.shape[2])))

    ax.set_xlim(times[0] -10, times[-1] + 10)
    ax.set_xlabel('Time [days from initial sample]')
    ax.set_ylabel('Position [bp]')
    ax.set_zlim(-4.1, 0.1)
    ax.set_zlabel(r'$\log_{10} \nu$', fontsize=18)
    ax.set_title(title)
    ax.grid(True)