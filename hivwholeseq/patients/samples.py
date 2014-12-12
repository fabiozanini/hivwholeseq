# vim: fdm=marker
'''
author:     Fabio Zanini
date:       07/10/14
content:    Description module for HIV patient samples.
'''
# Modules
import numpy as np
import pandas as pd

from hivwholeseq.sequencing.filenames import table_filename



# Classes
class SamplePat(pd.Series):
    '''Patient sample'''
    _sequenced_samples = None

    def __init__(self, *args, **kwargs):
        '''Initialize a patient sample'''
        super(SamplePat, self).__init__(*args, **kwargs)


    @property
    def _constructor(self):
        return SamplePat


    def get_n_templates_dilutions(self):
        '''Get the time course of the number of templates to PCR, limiting depth'''
        from hivwholeseq.patients.get_template_number import get_template_number
        return get_template_number(self.dilutions)


    def get_foldername(self, PCR=1):
        '''Get the name of the folder with the data for this sample'''
        from hivwholeseq.patients.filenames import get_sample_foldername
        return get_sample_foldername(self.patient, self.name, PCR=PCR)


    def get_mapped_filtered_filename(self, fragment, PCR=1, **kwargs):
        '''Get filename(s) of mapped and filtered reads'''
        from hivwholeseq.patients.filenames import get_mapped_filtered_filename
        return get_mapped_filtered_filename(self.patient, self.name, fragment,
                                            PCR=PCR, **kwargs)


    def get_mapped_filenames(self, fragment, PCR=1):
        '''Get filename(s) of mapped and filtered reads'''
        # TODO: optimize this call
        from hivwholeseq.patients.filenames import get_mapped_to_initial_filename
        from hivwholeseq.sequencing.samples import load_samples_sequenced as lss
        samples_seq = lss()
        samples_seq = samples_seq.loc[samples_seq['patient sample'] == self.name]

        fns = [get_mapped_to_initial_filename(self.patient, self.name, samplename,
                                              PCR=PCR)
               for samplename, sample in samples_seq.iterrows()]
        return fns


    def get_allele_counts_filename(self, fragment, PCR=1, qual_min=30):
        '''Get the filename of the allele counts'''
        from hivwholeseq.patients.filenames import get_allele_counts_filename
        return get_allele_counts_filename(self.patient, self.name, fragment,
                                          PCR=PCR, qual_min=qual_min)


    def get_allele_cocounts_filename(self, fragment, PCR=1, qual_min=30):
        '''Get the filename of the allele counts'''
        from hivwholeseq.patients.filenames import get_allele_cocounts_filename
        return get_allele_cocounts_filename(self.patient, self.name, fragment,
                                            PCR=PCR, qual_min=qual_min)


    def get_consensus_filename(self, fragment, PCR=1):
        '''Get the filename of the consensus of this sample'''
        from hivwholeseq.patients.filenames import get_consensus_filename
        return get_consensus_filename(self.patient, self.name, fragment, PCR=PCR)


    def get_consensus(self, fragment, PCR=1):
        '''Get consensu for this sample'''
        from Bio import SeqIO
        return SeqIO.read(self.get_consensus_filename(fragment, PCR=PCR), 'fasta')


    def get_reference_filename(self, fragment, format='fasta'):
        '''Get filename of the reference for mapping'''
        from hivwholeseq.patients.filenames import get_initial_reference_filename
        return get_initial_reference_filename(self.patient, fragment, format)


    def get_reference(self, fragment, format='fasta'):
        '''Get the reference for a fragment'''
        from Bio import SeqIO
        refseq = SeqIO.read(self.get_reference_filename(fragment, format=format), format)
        if format in ('gb', 'genbank'):
            from hivwholeseq.sequence_utils import correct_genbank_features_load
            correct_genbank_features_load(refseq)
        return refseq


    def get_allele_counts(self, fragment, PCR=1, qual_min=30, merge_read_types=True):
        '''Get the allele counts'''
        import numpy as np
        ac = np.load(self.get_allele_counts_filename(fragment, PCR=PCR, qual_min=qual_min))
        if merge_read_types:
            ac = ac.sum(axis=0)
        return ac


    def get_allele_cocounts(self, fragment, PCR=1, qual_min=30):
        '''Get the allele cocounts'''
        import numpy as np
        acc = np.load(self.get_allele_cocounts_filename(fragment, PCR=PCR, qual_min=qual_min))
        return acc


    def get_coverage(self, fragment, PCR=1, qual_min=30, merge_read_types=True):
        '''Get the coverage'''
        ac = self.get_allele_counts(fragment, PCR=PCR, qual_min=qual_min,
                                    merge_read_types=merge_read_types)
        cov = ac.sum(axis=-2)
        return cov


    def get_sequenced_samples(self):
        '''Get the sequencing samples'''
        if self._sequenced_samples is not None:
            return self._sequenced_samples
        
        from hivwholeseq.sequencing.samples import load_samples_sequenced as lss
        samples = lss()
        samples = samples.loc[samples['patient sample'] == self.name].copy()
        self._sequenced_samples = samples
        return self._sequenced_samples


    def get_local_haplotypes(self, fragment, start, end,
                             VERBOSE=0, maxreads=-1, filters=None, PCR=1):
        '''Get local haplotypes'''
        from hivwholeseq.patients.get_local_haplotypes import get_local_haplotypes
        bamfilename = self.get_mapped_filtered_filename(fragment, PCR=PCR)
        haplo = get_local_haplotypes(bamfilename,
                                     start, end,
                                     VERBOSE=VERBOSE,
                                     maxreads=maxreads)

        if filters is not None:
            if 'noN' in filters:
                hnames = [hname for hname in haplo.iterkeys() if 'N' in hname]
                for hname in hnames:
                    del haplo[hname]
            
            if 'nosingletons' in filters:
                hnames = [hname for hname, c in haplo.iteritems() if c <= 1]
                for hname in hnames:
                    del haplo[hname]

        return haplo



# Functions
def load_samples_sequenced(patients=None, include_wrong=False):
    '''Load patient samples sequenced from general table'''
    sample_table = pd.read_excel(table_filename, 'Samples timeline sequenced',
                                 index_col=0)

    sample_table.index = pd.Index(map(str, sample_table.index))
    sample_table.loc[:, 'patient'] = map(str, sample_table.loc[:, 'patient'])
    # FIXME: the number of molecules to PCR depends on the number of
    # fragments for that particular experiment... integrate Lina's table!
    # Note: this refers to the TOTAL # of templates, i.e. the factor 2x for
    # the two parallel RT-PCR reactions
    sample_table['n templates'] = sample_table['viral load'] * 0.4 / 12 * 2

    if not include_wrong:
        sample_table = sample_table.loc[sample_table.loc[:, 'wrong'] != 'x']
        del sample_table['wrong']

    if patients is not None:
        sample_table = sample_table.loc[sample_table.loc[:, 'patient'].isin(patients)]

    return sample_table


def load_sample_sequenced(samplename):
    '''Load one patient sample'''
    return SamplePat(load_samples_sequenced().loc[samplename])

