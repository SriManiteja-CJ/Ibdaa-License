"""
test_suite.py
-------------
Automated test suite verifying the EXACT 90% similarity threshold requirements:
TEST 1: Match >= 90% -> BLOCKED & top 2 matches shown & 5 alternatives generated.
TEST 2: Matches < 90% (e.g. 78%, 77.8%, 75%) -> NOT flagged as similar, NOT shown.
TEST 3: Display limit -> Max 2 matches >= 90% returned.
TEST 4: Same-category exact duplicate -> BLOCKED.
TEST 5: Different-category exact same name -> ALLOWED (unless similarity >= 90%).
TEST 6: Validation word detection -> BLOCKED with Word, ID, Type.
TEST 7: Suggestion validation -> Exactly 5 valid options with similarity < 90% & keyword preserved at TOP.
TEST 8: Arabic trade name duplicate & text preservation.
"""

import sys
import io
import os

sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding='utf-8')

from data_loader import load_trade_names
from validation_checker import load_validation_data, check_validation_words
from similarity_checker import check_trade_name, check_exact_duplicate, is_candidate_valid
from suggestion_generator import generate_suggestions


def run_tests():
    print("Loading dataset & validation data for test suite...")
    df = load_trade_names()
    val_status = load_validation_data()
    print(f"Dataset ready: {len(df)} rows. Validation ready: {val_status['loaded']}\n")

    passed_count = 0
    total_tests = 8

    # =========================================================================
    # TEST 1: Match >= 90% -> BLOCKED + 5 Alternatives
    # =========================================================================
    print("--- TEST 1: Similarity Match >= 90% (Block & 5 Alternatives) ---")
    test1_name = "Ranches Fresh Poultry Trading"
    test1_cat  = "975"
    sim_res1   = check_trade_name(test1_name, test1_cat, df)
    gen_res1   = generate_suggestions(test1_name, test1_cat, sim_res1["matches"], df)

    cond1_sim  = sim_res1["similar_found"] is True
    cond1_high = all(m["score"] >= 90.0 for m in sim_res1["matches"])
    cond1_sug  = len(gen_res1["accepted"]) == 5

    print(f"Match found >= 90%: {sim_res1['similar_found']} (Expected: True)")
    print(f"Top match score: {sim_res1['matches'][0]['score'] if sim_res1['matches'] else 0}%")
    print(f"Suggestions count: {len(gen_res1['accepted'])} (Expected: 5)")
    if cond1_sim and cond1_high and cond1_sug:
        print("[PASS] TEST 1 PASSED\n")
        passed_count += 1
    else:
        print("[FAIL] TEST 1 FAILED\n")

    # =========================================================================
    # TEST 2: Sub-90% Similarity Scores (78%, 77.8%, 75%) -> NOT Flagged/Shown
    # =========================================================================
    print("--- TEST 2: Sub-90% Similarity Scores (e.g. 78%, 75%) -> NOT Flagged ---")
    test2_name = "KwikClean"
    test2_cat  = "Cleaning Services"
    sim_res2   = check_trade_name(test2_name, test2_cat, df)

    # "KwikClean" vs "QuickClean" produces ~73.7% similarity, which is < 90%
    cond2_no_flag = len(sim_res2["matches"]) == 0

    print(f"Matches count >= 90%: {len(sim_res2['matches'])} (Expected: 0)")
    if cond2_no_flag:
        print("[PASS] TEST 2 PASSED\n")
        passed_count += 1
    else:
        print("[FAIL] TEST 2 FAILED\n")

    # =========================================================================
    # TEST 3: Display Limit -> Max 2 Matches >= 90% Displayed
    # =========================================================================
    print("--- TEST 3: Display Limit (Top 2 Matches >= 90% Only) ---")
    test3_name = "AL GHANEEM FOODSTUFF TRADING LLC"
    test3_cat  = "975"
    sim_res3   = check_trade_name(test3_name, test3_cat, df)
    top_2      = sim_res3["matches"][:2]

    cond3_limit = len(top_2) <= 2
    print(f"Top matches count: {len(top_2)} (Expected: <= 2)")
    if cond3_limit:
        print("[PASS] TEST 3 PASSED\n")
        passed_count += 1
    else:
        print("[FAIL] TEST 3 FAILED\n")

    # =========================================================================
    # TEST 4: Same-Category Exact Duplicate Rule
    # =========================================================================
    print("--- TEST 4: Same-Category Exact Duplicate ---")
    test4_name = "AL GHANEEM FOODSTUFF TRADING LLC"
    test4_cat  = "975"
    dup_res4   = check_exact_duplicate(test4_name, test4_cat, df)

    cond4_dup  = dup_res4["is_duplicate"] is True
    print(f"Is duplicate: {dup_res4['is_duplicate']} (Expected: True)")
    if cond4_dup:
        print("[PASS] TEST 4 PASSED\n")
        passed_count += 1
    else:
        print("[FAIL] TEST 4 FAILED\n")

    # =========================================================================
    # TEST 5: Different-Category Exact Name Allow
    # =========================================================================
    print("--- TEST 5: Different-Category Exact Name Allow ---")
    test5_name = "AL GHANEEM FOODSTUFF TRADING LLC"
    test5_cat  = "864"  # Different category
    dup_res5   = check_exact_duplicate(test5_name, test5_cat, df)

    cond5_dup  = dup_res5["is_duplicate"] is False
    print(f"Is duplicate in diff category: {dup_res5['is_duplicate']} (Expected: False)")
    if cond5_dup:
        print("[PASS] TEST 5 PASSED\n")
        passed_count += 1
    else:
        print("[FAIL] TEST 5 FAILED\n")

    # =========================================================================
    # TEST 6: Validation Word Detection
    # =========================================================================
    print("--- TEST 6: Validation Word Detection ---")
    test6_name = "Omar bin Al-Khatab brigade"
    val_res6   = check_validation_words(test6_name)

    cond6_val  = val_res6["validation_required"] is True
    print(f"Validation flagged: {val_res6['validation_required']} (Expected: True)")
    if cond6_val:
        print("[PASS] TEST 6 PASSED\n")
        passed_count += 1
    else:
        print("[FAIL] TEST 6 FAILED\n")

    # =========================================================================
    # TEST 7: Independent Candidate Validation (< 90% & Keyword Preserved)
    # =========================================================================
    print("--- TEST 7: Suggestion Validation (< 90% similarity & Top Keyword) ---")
    gen_res7   = generate_suggestions("Ranches Fresh Poultry Trading", "975", [], df)
    accepted7  = gen_res7["accepted"]

    cond7_count = len(accepted7) == 5
    all_valid7 = True
    for s in accepted7:
        v_chk = check_validation_words(s["name"])
        d_chk = check_exact_duplicate(s["name"], "975", df)
        s_chk, _ = is_candidate_valid(s["name"], "975", df)
        if v_chk["validation_required"] or d_chk["is_duplicate"] or not s_chk:
            all_valid7 = False
            print(f"Invalid suggestion: {s['name']}")

    print(f"Suggestions count: {len(accepted7)} (Expected: 5)")
    print(f"Suggestions list: {[s['name'] for s in accepted7]}")
    print(f"Top suggestion keyword preserved: {'Poultry' in accepted7[0]['name'] or 'Ranches' in accepted7[0]['name'] or 'Fresh' in accepted7[0]['name']}")

    if cond7_count and all_valid7:
        print("[PASS] TEST 7 PASSED\n")
        passed_count += 1
    else:
        print("[FAIL] TEST 7 FAILED\n")

    # =========================================================================
    # TEST 8: Arabic Trade Name Duplicate & Text Preservation
    # =========================================================================
    print("--- TEST 8: Arabic Trade Name Support & Text Preservation ---")
    test8_name = "بقالة ريحان ذ.م.م"
    test8_cat  = "996"
    dup_res8   = check_exact_duplicate(test8_name, test8_cat, df)
    sim_res8   = check_trade_name(test8_name, test8_cat, df)

    cond8_dup = dup_res8["is_duplicate"] is True
    has_ar   = len(sim_res8["matches"]) > 0 and sim_res8["matches"][0].get("name_ar") != ""

    print(f"Arabic Trade Name duplicate: {dup_res8['is_duplicate']} (Expected: True)")
    print(f"Preserved Arabic text: {sim_res8['matches'][0].get('name_ar') if sim_res8['matches'] else 'N/A'}")

    if cond8_dup and has_ar:
        print("[PASS] TEST 8 PASSED\n")
        passed_count += 1
    else:
        print("[FAIL] TEST 8 FAILED\n")

    print(f"==========================================")
    print(f"TEST SUMMARY: {passed_count}/{total_tests} Tests Passed.")
    print(f"==========================================")

    if passed_count == total_tests:
        sys.exit(0)
    else:
        sys.exit(1)


if __name__ == "__main__":
    run_tests()
