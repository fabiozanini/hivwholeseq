# vim: fdm=marker
'''
author:     Fabio Zanini
date:       09/01/15
content:    Quantify purifying selection on different subtype entropy classes.
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
def fit_fitness_cost(x, y, mu, VERBOSE=0):
    '''Fit saturation curve for fitness costs
    
    NOTE: as can be seen from the plots below, the fit for l is not very
    sensitive to mu.
    '''
    from scipy.optimize import minimize_scalar

    fun_min_scalar = lambda s: ((y - fun(x, mu/s, mu))**2).sum()
    s = minimize_scalar(fun_min_scalar, bounds=[1e-5, 1e0]).x

    return s


def fit_saturation(data, bins_S, binsc_S, method='group', VERBOSE=0):
    '''Fit saturation curves to the data
    
    Parameters:
       method (str): whether to fit single allele trajectories ('single') or
       time averages ('group'). The fit result is similar, but noise statistics
       differ.
    '''
    if method == 'single':
        dataf = (data
                 .loc[:, ['Sbin', 'mu', 'time', 'af']]
                 .groupby('Sbin'))
    else:
        dataf = (data
                 .loc[:, ['Sbin', 'mut', 'mu', 'time', 'af']]
                 .groupby(['Sbin', 'mut', 'time'])
                 .mean())
        dataf['time'] = dataf.index.get_level_values('time')
        dataf['Sbin'] = dataf.index.get_level_values('Sbin')
        dataf = dataf.groupby('Sbin')


    fits = []
    for iSbin, datum in dataf:
        x = np.array(datum['time'])
        y = np.array(datum['af'])
        mu = np.array(datum['mu'])

        ind = -(np.isnan(x) | np.isnan(y))
        x = x[ind]
        y = y[ind]
        mu = mu[ind]

        try:
            s = fit_fitness_cost(x, y, mu, VERBOSE=VERBOSE)
            if VERBOSE >= 3:
                regions = np.unique(data['region'])
                plot_function_minimization_1d(x, y, s, mu,
                                              title=', '.join(regions)+', iSbin = '+str(iSbin))

        except RuntimeError:
            print 'Fit failed, Sbin = ', iSbin
            continue

        fits.append((iSbin, s))

    fits = pd.DataFrame(data=fits,
                        columns=['iSbin', 's'])
    fits['S'] = binsc_S[fits['iSbin']]
    fits['Smin'] = bins_S[fits['iSbin']]
    fits['Smax'] = bins_S[fits['iSbin'] + 1]
    
    return fits


def plot_function_minimization(x, y, params):
    '''Investigate inconsistencies in fits'''
    fun_min = lambda p: ((y - fun(x, p[0], p[1]))**2).sum()

    p1 = np.logspace(np.log10(params[0]) - 3, np.log10(params[0]) + 3, 10)
    p2 = np.logspace(np.log10(params[1]) - 3, np.log10(params[1]) + 3, 10)

    p1G = np.tile(p1, (len(p2), 1))
    p2G = np.tile(p2, (len(p1), 1)).T
    pG = np.dstack([p1G, p2G])
    z = np.log(np.array([[fun_min(ppp) for ppp in pp] for pp in pG]))

    fig, ax = plt.subplots()
    ax.imshow(z, interpolation='nearest')

    ax.set_xlabel('Log l')
    ax.set_ylabel('Log u')

    plt.ion()
    plt.show()

def plot_function_minimization_1d(x, y, s, mu, title=''):
    '''Investigate inconsistencies in fits'''
    #FIXME: rewrite this function
    fun_min = lambda l, u: ((y - fun(x, l, u))**2).sum()

    p1 = np.logspace(np.log10(l) - 3, np.log10(l) + 3, 100)
    zs = np.log(np.array([[fun_min(pp, u) for pp in p1] for u in us]))

    fig, ax = plt.subplots()

    from itertools import izip
    for i, (z, u) in enumerate(izip(zs, us)):
        ax.plot(p1, z, lw=2, color=cm.jet(1.0 * i / len(us)),
                label='mu = {:1.1e}'.format(u))

    if title:
        ax.set_title(title)
    ax.set_xlabel('Saturation frequency ($\mu / s$)')
    ax.set_xscale('log')
    ax.grid(True)
    ax.legend(loc='upper left')

    plt.ion()
    plt.show()


def plot_fits(fitsreg, title='', VERBOSE=0, mu=5e-6, data=None):
    '''Plot the fits for purifying selection
    
    If data is supplied, the top mutation rate is picked instead of the given one.
    '''
    if data is not None:
        mu = data.loc[:, 'mu'].max()

    ymin = 1e-5

    fig, axs = plt.subplots(1, 2, figsize=(13, 6))
    if title:
        fig.suptitle(title, fontsize=20)
    ax = axs[0]

    # Plot the time-averaged data for one 
    datap = (data.loc[data.loc[:, 'mu'] == mu]
                 .loc[:, ['Sbin', 'time', 'af']]
                 .groupby(['Sbin', 'time'])
                 .mean())
    datap['time'] = datap.index.get_level_values('time')
    datap['Sbin'] = datap.index.get_level_values('Sbin')
    datap = datap.groupby('Sbin')
    for iSbin, datum in datap:
        x = np.array(datum['time'])
        # Add pseudocounts to keep plot tidy
        y = np.array(datum['af']) + 1.1 * ymin
        color = cm.jet(1.0 * iSbin / len(fitsreg))
        ax.scatter(x, y, s=40, color=color)

    # Plot the fits
    xfit = np.logspace(0, 3.5, 1000)
    for _, fit in fitsreg.iterrows():
        iSbin = fit['iSbin']
        Smin = fit['Smin']
        Smax = fit['Smax']
        s = fit['s']
        yfit = fun(xfit, mu/s, mu)
        label = ('S e ['+'{:.1G}'.format(Smin)+', '+'{:.1G}'.format(Smax)+']'+
                 ', s = '+'{:.1G}'.format(s))
        color = cm.jet(1.0 * iSbin / len(fitsreg))
        ax.plot(xfit, yfit, color=color, label=label, lw=2)

    ax.set_xlabel('Time [days from infection]')
    ax.set_ylabel('Allele frequency')
    ax.legend(loc='upper left', title='Entropy:', fontsize=14, ncol=1)
    #ax.text(0.6, 0.93,
    #        ('$f(t) \, = \, \mu / s \, [1 - e^{-st}]$'),
    #        fontsize=20,
    #        horizontalalignment='left',
    #        verticalalignment='center',
    #        transform=ax.transAxes)
    ax.set_xscale('log')
    ax.set_yscale('log')
    ax.set_ylim(ymin, 1)
    ax.grid(True)

    # Plot the estimated fitness value
    ax3 = axs[1]
    
    if 'ds' in fitsreg.columns:
        ax3.errorbar(fitsreg['S'], fitsreg['s'], yerr=fitsreg['ds'], lw=2, c='k')
    else:
        ax3.plot(fitsreg['S'], fitsreg['s'], lw=2, c='k')

    ax3.set_xlabel('Entropy in subtype [bits]')
    ax3.set_ylabel('Fitness cost')
    ax3.set_ylim(1e-5, 1e-1)
    ax3.set_xlim(1e-3, 2)
    ax3.set_xscale('log')
    ax3.set_yscale('log')
    ax3.grid(True, which='both')

    plt.tight_layout(rect=(0, 0, 1, 0.96))



# Script
if __name__ == '__main__':

    # Parse input args
    parser = argparse.ArgumentParser(
        description='Study accumulation of minor alleles for different kinds of mutations',
        formatter_class=argparse.ArgumentDefaultsHelpFormatter)    
    parser.add_argument('--patients', nargs='+', default=pnames,
                        help='Patient to analyze')
    parser.add_argument('--regions', nargs='+', default=regions,
                        help='Regions to analyze (e.g. p17 p24)')
    parser.add_argument('--verbose', type=int, default=2,
                        help='Verbosity level [0-4]')
    parser.add_argument('--plot', action='store_true',
                        help='Plot results')
    parser.add_argument('--method', default='group', choices=['single', 'group'],
                        help='Fit method [group|single]')

    args = parser.parse_args()
    pnames = args.patients
    regions = args.regions
    VERBOSE = args.verbose
    plot = args.plot
    fit_method = args.method

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

    # Bin by subtype entropy using quantiles
    from hivwholeseq.analysis.purifying_selection.joint_model import add_Sbins
    bins_S, binsc_S = add_Sbins(data, bins=5, VERBOSE=VERBOSE)

    # Get mutation rates from Abram 2010
    from hivwholeseq.analysis.mutation_rate.comparison_Abram import get_mu_Abram2010
    # NOTE: we need mut rates PER DAY
    mu = get_mu_Abram2010() / 2
    data['mu'] = np.array(mu.loc[data['mut']])

    # Fit exponential saturation
    fits = fit_saturation(data, bins_S, binsc_S, method=fit_method, VERBOSE=VERBOSE)

    # Bootstrap over patients
    fits_bs = []
    for i in xrange(10):
        if VERBOSE >= 2:
            print 'Bootstrap n.'+str(i+1)
        pcodes_bs = np.array(patients.iloc[np.random.randint(len(pnames), size=len(pnames))]['code'])
        data_bs = pd.concat([data.loc[data['pcode'] == pc] for pc in pcodes_bs])
        fits_tmp = fit_saturation(data_bs, bins_S, binsc_S, method=fit_method, VERBOSE=VERBOSE)
        fits_tmp['bootstrap'] = i
        fits_bs.append(fits_tmp)
    fits_bs = pd.concat(fits_bs)
    fits['ds'] = fits_bs[['iSbin', 's']].groupby('iSbin').std()['s']

    # Store fitness cost to file
    if VERBOSE >= 1:
        print 'Save to file'
    fn_out = get_fitness_cost_entropy_filename('all')
    fits.to_pickle(fn_out)

    if plot:
        plot_fits(fits, title=', '.join(regions), VERBOSE=VERBOSE, data=data)

        plt.ion()
        plt.show()

