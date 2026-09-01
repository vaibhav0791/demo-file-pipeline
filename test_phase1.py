import pprint
from app.connectors.string_connector import map_identifiers_to_string_ids, fetch_interaction_partners

def test_phase_1():
    print("=== Test 1: Mapping Identifiers to STRING IDs ===")
    test_genes = ["TRPV1", "TRPA1", "SCN9A"]
    print(f"Querying genes: {test_genes}")
    
    resolved = map_identifiers_to_string_ids(test_genes)
    
    mapped_ids = {}
    for entry in resolved:
        gene = entry.get("queryItem", "")
        string_id = entry.get("stringId", "")
        if gene and string_id:
            mapped_ids[gene] = string_id
            
    print("\nResolved Mapping:")
    pprint.pprint(mapped_ids)
    print("\n" + "="*50 + "\n")
    
    print("=== Test 2: Fetching Interaction Partners ===")
    for gene, string_id in mapped_ids.items():
        print(f"\nFetching partners for {gene} (ID: {string_id})...")
        interactions = fetch_interaction_partners(string_id, limit=5)
        
        print(f"Found {len(interactions)} interactions (limit was 5).")
        if interactions:
            print("First interaction preview:")
            pprint.pprint({
                "protein_A": interactions[0].get("preferredName_A"),
                "protein_B": interactions[0].get("preferredName_B"),
                "score": interactions[0].get("score")
            })

if __name__ == "__main__":
    test_phase_1()
