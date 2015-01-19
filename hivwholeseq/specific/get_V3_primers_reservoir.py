# vim: fdm=marker
'''
author:     Fabio Zanini
date:       08/01/15
content:    Get the patient-specific primer sequencing for the reservoir cell
            samples.
'''
# Modules
import numpy as np
from seqanpy import align_overlap

from hivwholeseq.patients.patients import load_patients, Patient
from hivwholeseq.sequence_utils import reduce_ambiguous_seqs


# Globals
fwd1 = 'TATCYTTTGAGCCAATTCCYATACA'
fwd2 = 'ACAATGYACACATGGAATTARGCCA'
rev1 = 'GAATTTTTCTAYTGYAATACATCAC'
rev2 = 'TTTAATTGTRGAGGRGAATTTTTCT'
primers_default = {'fwd1': fwd1,
                   'fwd2': fwd2,
                   'rev1': rev1,
                   'rev2': rev2}


# Script
if __name__ == '__main__':

    fragment = 'F5'
    primers = {}
    primers_ambiguous = {}

    patients = load_patients()
    for pname, patient in patients.iterrows():
        patient = Patient(patient)

        ref = patient.get_reference(fragment)

        for prname, primer in primers_default.iteritems():
            print pname, prname

            (score, ali1, ali2) = align_overlap(ref, primer, score_gapopen=-20)

            start = len(ali2) - len(ali2.lstrip('-'))
            end = len(ali2.rstrip('-'))

            data = patient.get_local_haplotype_count_trajectories(fragment, start, end,
                                                                  VERBOSE=2)
            htc, ind, htseqs = data

            htf = (1.0 * htc.T / htc.sum(axis=1)).T
            prset = set(htseqs[(htf > 0.1).any(axis=0)])

            primers[(pname, prname)] = prset
            primers_ambiguous[(pname, prname)] = reduce_ambiguous_seqs(prset)

    from collections import defaultdict
    primers_dicts = {}
    for prname in primers_default:
        prset = defaultdict(list)
        for (pname, prname2), seq in primers_ambiguous.iteritems():
            if prname == prname2:
                prset[seq].append(pname)
        primers_dicts[prname] = dict(prset)

    lines = ['#Primers for V3 cell samples']
    for prname, prset in primers_dicts.iteritems():
        lines.append(prname)
        for seq, pnames in prset.iteritems():
            line = seq+'\t'+' '.join(pnames)
            lines.append(line)
        lines.append('')

    fn = '/ebio/ag-neher/home/fzanini/tmp/V3_primers_minor.txt'
    with open(fn, 'w') as f:
        f.write('\n'.join(lines))