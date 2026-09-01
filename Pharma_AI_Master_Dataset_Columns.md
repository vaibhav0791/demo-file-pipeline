# Pharma AI - Master Target Discovery Dataset Schema

**Purpose:** This document lists every column required for the Master Target Discovery Dataset and identifies the source dataset for each column.

## Source Datasets

|     |     |
| --- | --- |
| Dataset | Contributes |
| UniProt | Protein sequence, annotations, molecular properties and localization |
| GEO | Disease-specific differential gene expression |
| STRING DB | Protein-protein interaction network and derived network metrics |
| RCSB PDB | 3D protein structural information |
| Target Label | Known therapeutic target annotation (from curated target databases such as ChEMBL/Open Targets/DrugBank) |

## Final Master Dataset Columns

|     |     |     |     |
| --- | --- | --- | --- |
| Category | Column Name | Source Dataset | Description |
| General | Disease | GEO | Disease name |
| General | UniProt_ID | UniProt | Primary key |
| General | Gene_Symbol | UniProt / GEO | Gene symbol |
| General | Protein_Name | UniProt | Protein name |
| General | Organism | UniProt | Species (Homo sapiens) |
| UniProt | Amino_Acid_Sequence | UniProt | Protein sequence |
| UniProt | Protein_Length | UniProt | Sequence length |
| UniProt | Molecular_Weight | UniProt | Protein molecular weight |
| UniProt | GO_Biological_Process | UniProt | GO biological process |
| UniProt | GO_Molecular_Function | UniProt | GO molecular function |
| UniProt | GO_Cellular_Component | UniProt | GO cellular component |
| UniProt | Subcellular_Location | UniProt | Protein localization |
| GEO | logFC | GEO | Log fold change |
| GEO | adj_P_Value | GEO | Adjusted p-value |
| GEO | Average_Expression | GEO | Average expression |
| GEO | Tissue | GEO | Tissue source |
| GEO | Sample_Size | GEO | Number of samples |
| STRING | STRING_ID | STRING DB | STRING identifier |
| STRING | Interaction_Count | STRING DB | Number of interactions |
| STRING | Average_Interaction_Score | STRING DB | Average interaction confidence |
| STRING | Degree_Centrality | STRING DB (Computed) | Network degree |
| STRING | Betweenness_Centrality | STRING DB (Computed) | Network betweenness |
| STRING | Closeness_Centrality | STRING DB (Computed) | Network closeness |
| STRING | Clustering_Coefficient | STRING DB (Computed) | Local clustering |
| PDB | PDB_ID | RCSB PDB | Structure ID |
| PDB | Experimental_Method | RCSB PDB | X-ray/Cryo-EM/NMR |
| PDB | Resolution | RCSB PDB | Structure resolution |
| PDB | Number_of_Chains | RCSB PDB | Chains in structure |
| PDB | Ligand_Count | RCSB PDB | Bound ligands |
| PDB | Binding_Site_Count | RCSB PDB / Computed | Binding pockets |
| PDB | Structure_Available | RCSB PDB | Structure availability |
| Label | Target_Label | Curated Target Database | 1 = target, 0 = non-target |

## Important Notes

\- Each row represents one Protein × One Disease.  
\- UniProt_ID is the master key used to merge all datasets.  
\- Degree_Centrality, Betweenness_Centrality, Closeness_Centrality and Clustering_Coefficient are computed from STRING interactions.  
\- Binding_Site_Count may require structural analysis if not directly available.  
\- Target_Label is obtained from curated therapeutic target resources.