# vim: fdm=marker
'''
author:     Fabio Zanini
date:       09/01/15
content:    Quantify purifying selection on different subtype entropy classes,
            and, at the same time, the mutation rate.
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

from hivwholeseq.miseq import alpha, alphal
from hivwholeseq.patients.patients import load_patients, Patient
from hivwholeseq.utils.sequence import translate_with_gaps
import hivwholeseq.utils.plot
from hivwholeseq.analysis.explore_entropy_patsubtype import (
    get_subtype_reference_alignment, get_ali_entropy)
from hivwholeseq.cross_sectional.get_subtype_entropy import (
    get_subtype_reference_alignment_entropy)
from hivwholeseq.cross_sectional.get_subtype_consensus import (
    get_subtype_reference_alignment_consensus)
from hivwholeseq.patients.one_site_statistics import get_codons_n_polymorphic
from hivwholeseq.analysis.mutation_rate.explore_divergence_synonymous import translate_masked
from hivwholeseq.analysis.purifying_selection.filenames import get_fitness_cost_entropy_filename


# Globals
pnames = ['20097', '15376', '15823', '15241', '9669', '15319']
regions = ['p17', 'p24', 'nef', 'PR', 'RT', 'IN', 'vif']
fun = lambda x, l, u: l * (1 - np.exp(- u/l * x))



# Functions
def add_Sbins(data, bins=8, VERBOSE=0):
    '''Add entropy bins to the data'''
    #bins_S = np.array([0, 0.03, 0.06, 0.1, 0.25, 0.7, 3])
    if np.isscalar(bins):
        bins = np.array(data['Ssub'].quantile(q=np.linspace(0, 1, bins)))
    
    binsc = 0.5 * (bins[1:] + bins[:-1])

    data['Sbin'] = -1
    for b in bins:
        data.loc[data.loc[:, 'Ssub'] >= b, 'Sbin'] += 1
    data['Sbin'] = data['Sbin'].clip(0, len(binsc) - 1)

    return bins, binsc



# Script
if __name__ == '__main__':

    # Parse input args
    parser = argparse.ArgumentParser(
        description='Infer mutation rates AND fitness costs',
        formatter_class=argparse.ArgumentDefaultsHelpFormatter)    
    parser.add_argument('--patients', nargs='+', default=pnames,
                        help='Patient to analyze')
    parser.add_argument('--regions', nargs='+', default=regions,
                        help='Regions to analyze (e.g. F1 p17)')
    parser.add_argument('--verbose', type=int, default=2,
                        help='Verbosity level [0-4]')
    parser.add_argument('--plot', action='store_true',
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

    for region in regions:
        if VERBOSE >= 1:
            print region

        if VERBOSE >= 2:
            print 'Get subtype consensus (for checks only)'
        conssub = get_subtype_reference_alignment_consensus(region, VERBOSE=VERBOSE)

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
                    print 'No time points: skip'
                continue

            times = patient.times[ind]

            if VERBOSE >= 2:
                print 'Get coordinate map'
            coomap = patient.get_map_coordinates_reference(region, refname=('HXB2', region))

            icons = patient.get_initial_consensus_noinsertions(aft, VERBOSE=VERBOSE,
                                                               return_ind=True)
            consm = alpha[icons]
            protm = translate_masked(consm)
            
            # Premature stops in the initial consensus???
            if '*' in protm:
                # Trim the stop codon if still there (some proteins are also end of translation)
                if protm[-1] == '*':
                    if VERBOSE >= 2:
                        print 'Ends with a stop, trim it'
                    icons = icons[:-3]
                    consm = consm[:-3]
                    protm = protm[:-1]
                    aft = aft[:, :, :-3]
                    coomap = coomap[coomap[:, 1] < len(consm)]

                else:
                    continue

            # Get the map as a dictionary from patient to subtype
            coomapd = {'pat_to_subtype': dict(coomap[:, ::-1]),
                       'subtype_to_pat': dict(coomap)}

            # Get only codons with at most one polymorphic site, to avoid obvious epistasis
            ind_poly, _ = get_codons_n_polymorphic(aft, icons, n=[0, 1], VERBOSE=VERBOSE)
            ind_poly_dna = [i * 3 + j for i in ind_poly for j in xrange(3)]

            # FIXME: deal better with depth (this should be already there?)
            aft[aft < 2e-3] = 0

            for posdna in ind_poly_dna:
                # Get the entropy
                if posdna not in coomapd['pat_to_subtype']:
                    continue
                pos_sub = coomapd['pat_to_subtype'][posdna]
                if pos_sub >= len(Ssub):
                    continue
                Ssubpos = Ssub[pos_sub]

                # Get allele frequency trajectory
                aftpos = aft[:, :, posdna].T

                # Get only non-masked time points
                indpost = -aftpos[0].mask
                if indpost.sum() == 0:
                    continue
                timespos = times[indpost]
                aftpos = aftpos[:, indpost]

                anc = consm[posdna]
                ianc = icons[posdna]

                # Skip if the site is already polymorphic at the start
                if aftpos[ianc, 0] < 0.95:
                    continue

                # Skip if the site has sweeps (we are looking at purifying selection only)
                # Obviously, it is hard to distinguish between sweeps and unconstrained positions
                # but that's not crucial because sweeps happen at unconstrained positions anyway
                if (aftpos[ianc] < 0.6).any():
                    continue

                for inuc, af in enumerate(aftpos[:4]):
                    nuc = alpha[inuc]
                    if nuc == anc:
                        continue

                    mut = anc+'->'+nuc

                    # Define transition/transversion
                    if frozenset(nuc+anc) in (frozenset('CT'), frozenset('AG')):
                        trclass = 'ts'
                    else:
                        trclass = 'tv'

                    # Get the whole trajectory for plots against time
                    for af, time in izip(aftpos[inuc], timespos):
                        data.append((region, pcode,
                                     posdna, pos_sub,
                                     anc, nuc, mut,
                                     trclass,
                                     Ssubpos,
                                     time, af))

    data = pd.DataFrame(data=data,
                        columns=['region', 'pcode',
                                 'posdna', 'possub',
                                 'anc', 'der', 'mut',
                                 'tr',
                                 'Ssub',
                                 'time', 'af'])

    # Fits
    fits = []
    from scipy.optimize import minimize
    muts = np.unique(data['mut']).tolist()
    dataf = data.copy()
    dataf['mbin'] = map(muts.index, dataf['mut'])

    # Get initial estimate for mu from Abram2010, resorted
    from hivwholeseq.analysis.mutation_rate.comparison_Abram import get_mu_Abram2010
    mu0 = get_mu_Abram2010().loc[muts]

    # Get initial estimate for s from our fixed-mu estimate
    from hivwholeseq.analysis.purifying_selection.filenames import get_fitness_cost_entropy_filename
    sdata = pd.read_pickle(get_fitness_cost_entropy_filename('p17'))
    s = sdata['s']

    # Bin by subtype entropy, taking bins from fitness cost estimate
    bins = np.insert(np.array(sdata['Smax']), 0, 0)
    bins_S, binsc_S = add_Sbins(dataf, bins=bins, VERBOSE=VERBOSE)

    dataf = dataf.loc[:, ['mbin', 'Sbin', 'af', 'time']]
    p0 = np.concatenate(map(np.array, [mu0, s]))

    def fun_min(p):
        '''p is the parameters vector: #I mut rates + #J selection coefficients'''
        fun = lambda x, u, s: u / s * (1 - np.exp(- s * x))

        mu = p[:len(muts)]
        s = p[len(muts):]

        #res = 0
        #for (imb, isb), datum in dataf.groupby(['mbin', 'Sbin']):
        #    res += ((datum['af'] - fun(datum['time'], mu[imb], s[isb]))**2).sum()

        res = sum(((datum['af'] - fun(datum['time'], mu[imb], s[isb]))**2).sum()
                  for (imb, isb), datum in (dataf.groupby(['mbin', 'Sbin'])))

        return res
        

    def get_funmin_neighbourhood(fun_min, p0, plot=False, title=''):
        '''Calculate a few function evaluations for testing'''
        dynrangeexp = 0.5
        datap = []
        for i in xrange(len(p0)):
            if VERBOSE >= 2:
                print 'Parameter n.'+str(i+1)
            x = []
            y = []
            for factor in np.logspace(-dynrangeexp, dynrangeexp, 10):
                p = p0.copy()
                p[i] *= factor

                x.append(factor)
                y.append(fun_min(p))

            if i < len(muts):
                label = muts[i]
            else:
                label = 'S ~ {:.1G}'.format(binsc_S[i - len(muts)])

            color = cm.jet(1.0 * i / len(p0))

            datap.append({'x': x, 'y': y, 'label': label, 'color': color})

        # Plot
        if plot:
            fig, ax = plt.subplots()
            for datum in datap:
                x = datum['x']
                y = datum['y']
                label = datum['label']
                color = datum['color']

                ax.plot(x, y, lw=2, label=label, color=color)

            ax.set_xlabel('Factor change of parameter')
            ax.set_xscale('log')
            ax.set_ylabel('Fmin')
            ax.set_yscale('log')
            ax.set_xlim(10**(-dynrangeexp), 10**dynrangeexp)

            ax.grid(True)
            ax.legend(loc='upper center', ncol=3, fontsize=8)

            plt.tight_layout()

        return datap

    if plot:
        if VERBOSE >= 1:
            print 'Plot a few function evaluations for testing'

        datap0 = get_funmin_neighbourhood(fun_min, p0, plot=plot)

    if VERBOSE >= 1:
        print 'Minimize joint objective function'
    
    method = 'Powell' # minimize along each parameter at every iteration
    res = minimize(fun_min, p0, method=method,
                   options={'disp': True, 'maxiter': 10})
    print res
    pmin = res.x
    
    if plot:
        if VERBOSE >= 1:
            print 'Plot a few function evaluations after minimization'

        datapmin = get_funmin_neighbourhood(fun_min, pmin, plot=plot)

        plt.ion()
        plt.show()


    # Save results of minimization
    mu_min = pd.Series(pmin[:len(muts)], index=muts)
    s_min = pd.DataFrame(pmin[len(muts):], columns=['s'])
    s_min['Smin'] = sdata['Smin']
    s_min['Smax'] = sdata['Smax']
    s_min['S'] = sdata['S']

    from hivwholeseq.analysis.filenames import analysis_data_folder
    fn_out_mu = analysis_data_folder+'mu_joint.pickle'
    mu_min.to_pickle(fn_out_mu)

    fn_out_s = analysis_data_folder+'s_joint.pickle'
    s_min.to_pickle(fn_out_s)

