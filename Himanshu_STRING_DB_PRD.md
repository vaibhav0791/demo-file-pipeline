# Product Requirements Document (PRD): STRING DB Pipeline (Himanshu)

## 1. Project Overview & Scope
As part of the **Pharma AI Target Discovery** project, this document strictly focuses on the **STRING DB** pipeline being developed by **Himanshu**. The overarching goal of the STRING DB pipeline is to retrieve, process, and canonically format Protein-Protein Interaction (PPI) datasets for specific target proteins to contribute to the Master Target Discovery dataset. This data will be merged with the UniProt, RCSB PDB, and GEO pipelines.

## 2. Strict Pipeline Constraints (`pipeline requirement.txt`)
All implementations within the STRING DB connector and service must strictly adhere to the following data constraints:
1. **Data Repetition**: Data must be completely unique every time it is fetched. Under no circumstances should data be repeated throughout the entire pipeline run.
2. **Data Duplication**: The STRING DB dataset must contain unique variations and target interactions for every target protein to ensure diversity in AI training.
3. **Data Hallucination**: No random or fabricated data entries are permitted. All network interactions, counts, and metrics must be strictly computed from or queried directly via the STRING DB source.
4. **Batch Limits**: The pipeline must fetch a maximum of **80 target proteins** per batch run.
5. **Data Volume per Target**: Each queried target protein must result in **at least 25 rows** of fully sanitized, valid data (e.g., 25 unique interaction vectors/variants per primary UniProt_ID).

## 3. Output Schema Mapping (STRING DB)
Based strictly on the final merged `Master_Target_Discovery_Pain.csv` format, the pipeline must canonicalize the STRING data to Output accurately into these specific columns:

| Column Name | Description | Source / Computation |
| --- | --- | --- |
| **STRING_ID** | STRING identifier (e.g., `9606.0`) | Directly from STRING DB |
| **Interaction_Count** | Number of protein interactions | Fetched/Computed from network |
| **Average_Interaction_Score**| Average confidence score of interactions | Computed from returned interactions |
| **Degree_Centrality** | Network degree metric | Computed (e.g., using `networkx`) |
| **Betweenness_Centrality** | Network betweenness metric | Computed |
| **Closeness_Centrality** | Network closeness metric | Computed |
| **Clustering_Coefficient** | Local clustering metric | Computed |

## 4. Architecture & Pipeline Structure
The codebase must mirror the structured standard utilized across the `demo-file-pipeline` (e.g., matching the UniProt ingestion scripts).

### 4.1. Connector (`app/connectors/string_connector.py`)
- **API Integration**: Integrate with the `https://string-db.org/` REST API to fetch network interactions.
- **Batching**: Implement strict bounds to only request an absolute maximum of 80 proteins per execution. 
- **Pagination & Retries**: Ensure resilient HTTP calls (via `httpx` or `requests`) with retries.

### 4.2. Service (`app/services/ingest_string.py`)
- **Canonicalization**: Transform raw STRING DB API responses into the structured schema output expected in the CSV.
- **Metric Computation logic**: Utilize graph libraries (such as `networkx` in Python) to compute necessary centrality and clustering metadata parameters.
- **Constraints Enforcement**: Before committing to the Database, the script must validate that the output produced strictly meets the "at least 25 rows per protein" constraint. It must also perform anti-repetition hashing (similar to `sha256_hash` used in UniProt service).

### 4.3. Models (`app/models/string_models.py`)
- Define the SQLModel/SQLAlchemy definitions covering the `STRING_ID`, `Interaction_Count`, `Average_Interaction_Score`, and node computation columns.
- Enforce unique constraints and hash comparisons down to the Database architecture to prevent violations of Data Duplication or Data Repetition.

## 5. Integration Validation
The STRING DB pipeline is expected to use the `UniProt_ID` (or `Gene_Symbol` mapping back to STRING taxonomy matching) as a primary alignment key to ensure seamless 1:1 row alignment to the Master AI dataset. Each execution must output deterministic, highly validated rows.

## 6. Implementation Phases (Rate Limit & Development Strategy)
To avoid hitting STRING DB API rate limits and to allow for iterative testing, development will be broken into the following distinct phases:

### Phase 1: Basic Connector & Request Optimization
- **Goal**: Establish the `string_connector.py` layout.
- **Action**: Implement the API requests with forced rate-limiting (e.g., `time.sleep()`), exponential backoff, and pagination logic to handle chunks strictly up to the 80-protein limit.
- **Validation**: Test by fetching a small, mock batch (e.g., 5 proteins) to ensure no rate-limiting HTTP 429 errors occur.

### Phase 2: Schema & Canonicalization Logic
- **Goal**: Transform the raw JSON from Phase 1 into the structured CSV requirements.
- **Action**: Create `app/services/ingest_string.py` and implement the canonicalization function. Extract basic attributes (Counts, Scores).
- **Validation**: Verify that the parser outputs standard dictionaries successfully without triggering network requests (using mocked Phase 1 data). 

### Phase 3: Network Metric Computations (`networkx`)
- **Goal**: Implement graph logic to satisfy centrality components.
- **Action**: In `ingest_string.py`, add networkx to build a graph from interactions and calculate `Degree`, `Betweenness`, `Closeness`, and `Clustering`.
- **Validation**: Compare outputs locally on the 5-protein mock batch against the expected formats in `Master_Target_Discovery_Pain.csv`. Ensure minimum 25 variants are derived properly.

### Phase 4: Database Logic & Constraint Enforcement
- **Goal**: Hook into `app/models/string_models.py` and save data robustly.
- **Action**: Add `sha256_hash` repetition checks and commit logic.
- **Validation**: Run the 5-batch mock 3 times. Verify exactly 0 new records are inserted on the 2nd and 3rd runs (Enforcing the Data Repetition constraint).

### Phase 5: Full Integration & 80-Batch Pipeline Runs
- **Goal**: Combine all phases and scale up to the requirement limits.
- **Action**: Execute batch jobs of 80 proteins sequentially using a local queue or chron module, respecting rate limits.
- **Validation**: Confirm deterministic end-to-end operation, resulting in exactly unique data (no hallucinations) scaling securely up to Master requirements.
