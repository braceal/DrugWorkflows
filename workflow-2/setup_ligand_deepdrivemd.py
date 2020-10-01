base_path = '/gpfs/alpine/med110/scratch/atrifan2/PLPro_ligands/gb_plpro/DrugWorkflows/workflow-2/'

top_dir = os.path.join(base_path, '/top_dir/')
pdb_dir = os.path.join(base_path, '/Outlier_search/outlier_pdbs/')
restart_points_path = os.path.join(base_path, '/Outlier_search/restart_points.json')


good_ligands = ['l15', 'l19', 'l38', 'l41', 'l68', 'l71', 'l78', 'l111', 'l143', 'l189', 'l217', 'l285', 'l309', 'l311', 'l357', 'l393', 'l444', 'l478', 'l479', 'l480', 'l507', 'l515', 'l532', 'l569', 'l593', 'l610', 'l616', 'l798', 'l801', 'l884', 'l892', 'l989', 'l998', 'l1179', 'l1231', 'l1250', 'l1344', 'l1387', 'l1395', 'l1418', 'l1510', 'l1521', 'l1607', 'l1612', 'l1618', 'l1619', 'l1693', 'l1794', 'l1833', 'l1906', 'l2053', 'l2057', 'l2080', 'l2086', 'l2105', 'l2147', 'l2150', 'l2348', 'l2374', 'l2387', 'l2393', 'l2518', 'l2541', 'l2560', 'l2585', 'l2587', 'l2685', 'l2710', 'l2840', 'l2921', 'l3226', 'l3229', 'l3296', 'l3616', 'l3732', 'l3879', 'l3886', 'l3906', 'l3916', 'l3986', 'l4001', 'l4044', 'l4278', 'l4313', 'l4334', 'l4368', 'l4400', 'l4464', 'l4564', 'l4594', 'l4683', 'l4791', 'l4930', 'l5085', 'l5216', 'l5276', 'l5308', 'l5314', 'l5418', 'l5536', 'l5603', 'l5836', 'l5932', 'l6022', 'l6037', 'l6090', 'l6138', 'l6181', 'l6279', 'l6377', 
'l6447', 'l6566', 'l6597', 'l6642', 'l6710', 'l6890', 'l6939', 'l6967', 'l7202', 'l7213', 'l7243', 'l7386', 'l7609', 'l7822', 'l8162', 'l8682', 'l8768', 'l8949', 'l9153', 'l9241', 'l9282', 'l9500', 'l9607', 'l9916']

from shutil import copyfile

pdb_files = []

for ligid in good_ligands:

	lig_num = int(ligid[1:])

	if lig_num < 6000:
		pdb_path = f'/gpfs/alpine/scratch/atrifan2/med110/PLPro_ligands/output_6w9c/pdbs/sys_{lig_num}.pdb'
		top_path = f'/gpfs/alpine/world-shared/chm155/dario/6w9c/{ligid}/fe/build/com-wat3.top'
	else:
		pdb_path = f'/gpfs/alpine/scratch/atrifan2/med110/PLPro_ligands/output_6w9c_new/pdbs/sys_{lig_num}.pdb'
		top_path = f'/gpfs/alpine/scratch/atrifan2/med110/PLPro_ligands/6w9c/{ligid}/fe/build/com-wat3.top'

	new_pdb_path = os.path.join(pdb_dir, f'system_{ligid}.pdb')
	new_top_path = os.path.join(top_dir, f'topology_{ligid}.top')

	copyfile(pdb_path, new_pdb_path)

	copyfile(top_path, new_top_path)

	pdb_files.append(new_pdb_path)

with open(restart_points_path, 'w') as restart_file:
    json.dump(pdb_files, restart_file)

