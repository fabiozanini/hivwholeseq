# vim: fdm=marker
'''
author:     Fabio Zanini
date:       09/01/15
content:    Study the site frequency spectrum to and against subtype consensus.
'''
# Modules
import os
import sys
import argparse
from itertools import izip
from collections import defaultdict, Counter
import numpy as np
import pandas as pd
from matplotlib import cm
import matplotlib.pyplot as plt
import hivwholeseq.utils.plot

from hivwholeseq.miseq import alpha, alphal
from hivwholeseq.patients.patients import load_patients, Patient
from hivwholeseq.cross_sectional.get_subtype_reference_alignment import (
    get_subtype_reference_alignment)
from hivwholeseq.cross_sectional.get_subtype_consensus import (
    get_subtype_reference_alignment_consensus)
from hivwholeseq.cross_sectional.get_subtype_entropy import (
    get_subtype_reference_alignment_entropy)
from hivwholeseq.cross_sectional.get_subtype_allele_frequencies import (
    get_subtype_reference_alignment_allele_frequencies)
from hivwholeseq.patients.one_site_statistics import get_codons_n_polymorphic
from hivwholeseq.utils.sequence import get_allele_frequencies_from_MSA



# Functions
def get_distance_matrix_in_coordinates_subtype(ds, seq, protsub, VERTBOSE=0):
    '''Get the distance as a dict in subtype coordinates'''
    from seqanpy import align_overlap
    score, alisub, alistr = align_overlap(protsub, seq, score_gapopen=-20)

    pmap = {}
    pos_sub = 0
    pos_str = 0
    for i in xrange(len(alisub)):
        if alistr == '-':
            pos_sub += 1
            continue
        if alisub == '-':
            pos_str += 1
            continue

        # Match: add the distance
        pmap[pos_str] = pos_sub

        pos_sub += 1
        pos_str += 1

    if VERBOSE >= 3:
        print pmap

    poss = set()
    dsub = {}
    for p1, psub1 in pmap.iteritems():
        for p2, psub2 in pmap.iteritems():
            # The sequence might have trailing residues (e.g. drugs)
            if (p1 < ds.shape[0]) and (p2 < ds.shape[0]):
                dsub[(psub1, psub2)] = ds[p1, p2]
                poss.add(psub1)
                poss.add(psub2)

    L = max(poss) + 1
    dsubm = np.ma.masked_all((L, L))
    for key, value in dsub.iteritems():
        dsubm[key[0], key[1]] = value

    return dsubm



# Script
if __name__ == '__main__':

    # Parse input args
    parser = argparse.ArgumentParser(
        description='Accumulation of minor alleles stratified by abundance difference in subtype',
        formatter_class=argparse.ArgumentDefaultsHelpFormatter)    
    parser.add_argument('--patients', nargs='+',
                        help='Patient to analyze')
    parser.add_argument('--regions', nargs='+', required=True,
                        help='Regions to analyze (e.g. F1 p17)')
    parser.add_argument('--verbose', type=int, default=0,
                        help='Verbosity level [0-4]')
    parser.add_argument('--plot', nargs='?', default=None, const='2D',
                        help='Plot results')

    args = parser.parse_args()
    pnames = args.patients
    regions = args.regions
    VERBOSE = args.verbose
    plot = args.plot


    data = []

    patients = load_patients()
    if pnames is not None:
        patients = patients.loc[pnames]

    # FIXME
    pbads = ('15313', '15107')
    patients = patients.loc[-patients.index.isin(pbads)]

    for region in regions:
        if VERBOSE >= 1:
            print region

        if VERBOSE >= 2:
            print 'Get subtype consensus'
        conssub = get_subtype_reference_alignment_consensus(region, VERBOSE=VERBOSE)

        if VERBOSE >= 2:
            print 'Get subtype allele frequencies'
        af_sub = get_subtype_reference_alignment_allele_frequencies(region)

        if VERBOSE >= 2:
            print 'Get subtype entropy'
        Ssub = get_subtype_reference_alignment_entropy(region, VERBOSE=VERBOSE)

        for ipat, (pname, patient) in enumerate(patients.iterrows()):
            pcode = patient.code
            if VERBOSE >= 2:
                print pname, pcode

            patient = Patient(patient)
            aft, ind = patient.get_allele_frequency_trajectories(region,
                                                                 cov_min=1000,
                                                                 depth_min=300,
                                                                 VERBOSE=VERBOSE)
            if len(ind) == 0:
                if VERBOSE >= 2:
                    print 'Skip'
                continue

            times = patient.times[ind]

            if VERBOSE >= 2:
                print 'Get coordinate map'
            coomap = patient.get_map_coordinates_reference(region, refname=('HXB2', region))

            icons = patient.get_initial_consensus_noinsertions(aft, VERBOSE=VERBOSE,
                                                               return_ind=True)
            consm = alpha[icons]

            # Get the map as a dictionary from patient to subtype
            coomapd = dict(coomap[:, ::-1])

            # FIXME: deal better with depth (this should be already there?)
            aft[aft < 2e-3] = 0

            for posdna in xrange(aft.shape[-1]):
                if VERBOSE >= 3:
                    print posdna

                # Look for this position in the subtype alignment
                if posdna not in coomapd:
                    continue
                pos_sub = coomapd[posdna]
                if (pos_sub >= af_sub.shape[1]):
                    continue

                # Ancestral allele
                ianc = icons[posdna]
                anc = alpha[ianc]

                # Discard if the initial time point is already polymorphic
                aft_anc0 = aft[0, ianc, posdna]
                if aft_anc0 < 0.9:
                    continue

                # Get subtype features of this position
                Spos_sub = Ssub[pos_sub]
                conspos_sub = conssub[pos_sub]

                # Keep only reversions, i.e. discard positions for which the ancestral
                # allele agrees with subtype consensus (these are most of them)
                if anc == conspos_sub:
                    continue

                # Get the reversion nucleotide (derived allele)
                der = conspos_sub
                ider = alphal.index(der)
                mut = anc + '->' + der

                # Get only non-masked time points
                aft_der = aft[:, ider, posdna]
                indpost = -aft_der.mask
                if indpost.sum() == 0:
                    continue
                timespos = times[indpost]
                aft_der = aft_der[indpost]
                

                # Get the difference in subtype abundances
                afanc_sub = af_sub[ianc, pos_sub]
                afder_sub = af_sub[ider, pos_sub]

                # Keep only sites that do NOT revert
                afmax = aft_der.max()
                if afmax < 0.1:
                    data.append((region, pcode,
                                 anc, der, mut,
                                 afanc_sub, afder_sub,
                                 posdna, pos_sub,
                                 Spos_sub,
                                 afmax))

    data = pd.DataFrame(data=data, columns=('region', 'pcode',
                                            'anc', 'der', 'mut',
                                            'afancsub', 'afdersub',
                                            'posdna', 'possub',
                                            'Ssub', 'afmax',
                                            ))


    # Select subset of positions that are at high frequency in the subtype, i.e.
    # for which we suspect strong fitness effects
    data_cons = data[data['afdersub'] - data['afancsub'] > 0.8] 

    for region, datar in data_cons.groupby('region'):
        ali = get_subtype_reference_alignment(region, VERBOSE=VERBOSE)
        alim = np.array(ali)

        # Get protein structure
        from hivwholeseq.utils.structure import get_chainseq, get_distance_matrix
        from hivwholeseq.structure.get_PDB import get_PDB
        pdb, chinds = get_PDB(region, VERBOSE=VERBOSE)
        ch = list(pdb.get_chains())[chinds[0]]
        seq = get_chainseq(ch)
        ds = get_distance_matrix(ch)

        conssub = get_subtype_reference_alignment_consensus(region, VERBOSE=VERBOSE)
        protsub = str(conssub.seq.translate())

        dsub = get_distance_matrix_in_coordinates_subtype(ds, seq, protsub)

        if plot:
            fig, ax = plt.subplots()
            h = ax.imshow(dsub, interpolation='nearest')
            cb = plt.colorbar(h)
            ax.set_title(region)
            cb.set_label('Distance [Angstrom]', rotation=270, labelpad=30)

        for _, datum in datar.iterrows():

            # Get subalignment conditioned on this allele
            alim1 = alim[alim[:, datum['possub']] == datum['anc']]
            alim2 = alim[alim[:, datum['possub']] == datum['der']]

            # If the mutation is extremely rare, there will be no statistics in
            # the alignment
            if alim1.shape[0] < 10:
                continue

            # Get allele frequencies
            af1 = get_allele_frequencies_from_MSA(alim1)
            af2 = get_allele_frequencies_from_MSA(alim2)
            
            # Get positions with highest differences
            # The top scoring is the focal allele by definition
            daf = np.abs(af1 - af2).max(axis=0)
            ind = np.argsort(daf)[::-1][1:]
            ind = ind[daf[ind] > 0.3]

            if not len(ind):
                continue

            print 'Focal position:', datum['possub']
            print 'Subalignment with', datum['anc']+':', alim1.shape[0]
            print 'Subalignment with', datum['der']+':', alim2.shape[0]
            for i in ind[:3]:
                print i, '(d = '+str(np.abs(i - datum['possub']))+')'
                if (i // 3 < dsub.shape[0]) and (datum['possub'] // 3 < dsub.shape[0]):
                    # FIXME: 3D distance is tricky for multimers (e.g. PR, p24)
                    print '3D distance [A]:', dsub[i // 3, datum['possub'] // 3]
                    if plot:
                        ax.scatter(i // 3, datum['possub'] // 3, s=40, c='k')
                print 'Subalignment with', datum['anc'], ' '.join(map('{:2.2f}'.format, af1[:, i]))
                print 'Subalignment with', datum['der'], ' '.join(map('{:2.2f}'.format, af2[:, i]))


            print ''

        if plot:
            ax.set_xlim(0, dsub.shape[0])
            ax.set_ylim(0, dsub.shape[0])
            plt.ion()
            plt.show()

    if plot:
        fig, ax = plt.subplots()
        ax.hist(data['Ssub'])

        ax.set_xlabel('Entropy in subtype [bits]')
        ax.set_ylabel('# sites')


        plt.ion()
        plt.show()
