#!/usr/bin/env python3

import os
import sys
import re
import pandas as pd

from impress_md import interface_functions


# ------------------------------------------------------------------------------
#
if __name__ == '__main__':

    assert('OE_LICENSE' in os.environ)

    smiles_files = pd.read_csv(sys.argv[1], sep=' ', header=None)
    target_filoe = sys.argv[2]
    start_idx    = int(sys.argv[3])
    n_smiles     = int(sys.argv[4])
    dbase_name   = 'test'
    target_name  = 'pl_pro'
    pdb_name = re.sub("_receptor.oeb", "", target_filoe).split("/")[-1]


    docker, receptor = interface_functions.get_receptr(target_filoe)

    for pos in range(start_idx, start_idx + n_smiles):

        smiles      = smiles_files.iloc[pos, 0]
        ligand_name = smiles_files.iloc[pos, 1]
        score, res  = interface_functions.RunDocking_(
                smiles, docker, pos=pos, name=ligand_name, target_name=pdb_name)
        print(pos, res, end='')


# ------------------------------------------------------------------------------

