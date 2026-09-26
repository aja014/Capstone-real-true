# Validation report

Generated with seed 20260926, today = 2026-09-26. **40 of 40 checks passed.**

## File row counts

| File | Rows |
| --- | --- |
| 1_customer_information | 1129 |
| 2_fire_surveys | 481 |
| 3_motor_quotations | 1450 |
| 4_fire_quotations | 1032 |
| 5_fire_policies | 876 |
| 6_motor_policies | 1139 |
| 7_motor_claims | 351 |
| 8_fire_property_claims | 90 |

## Checks

| Check | Result | Detail |
| --- | --- | --- |
| Headers exactly as the importer expects: 1_customer_information | PASS |  |
| Headers exactly as the importer expects: 2_fire_surveys | PASS |  |
| Headers exactly as the importer expects: 3_motor_quotations | PASS |  |
| Headers exactly as the importer expects: 4_fire_quotations | PASS |  |
| Headers exactly as the importer expects: 5_fire_policies | PASS |  |
| Headers exactly as the importer expects: 6_motor_policies | PASS |  |
| Headers exactly as the importer expects: 7_motor_claims | PASS |  |
| Headers exactly as the importer expects: 8_fire_property_claims | PASS |  |
| No None/NA/N/A/null cell outside Protection Facilities | PASS | [] |
| Survey Occupancy parts add up exactly to Occupancy - Total (= sum insured) | PASS |  |
| Spouse name filled for married clients only | PASS |  |
| Motor policies with a counted loss about 20% (17-24%) | PASS | 20.6% of 830 ended motor policies |
| Fire policies with a counted loss about 9% (7-12%) | PASS | 9.2% of 621 ended fire policies |
| Fraud about 12% of investigated paid claims (10-15%) | PASS | 12.0% (41 of 342) |
| Renewal rate about 70% (62-78%) | PASS | 71.4% |
| CNC share of motor claim rows about 10% (7-16%) | PASS | 9.4% |
| Claims without a label yet about 8% or less | PASS | 6.3% |
| All date rules hold (quote/issue/period, renewals, claim chain, nothing after today) | PASS | [] |
| Policy numbers unique | PASS |  |
| Accuterm numbers unique per accident (third party rows share their accident's number) | PASS |  |
| LOA numbers unique | PASS |  |
| Vehicle plate numbers unique and contain letters | PASS |  |
| Vehicle engine numbers unique and contain letters | PASS |  |
| Vehicle chassis numbers unique and contain letters | PASS |  |
| Every claim points to an existing policy | PASS |  |
| Every policy has its quotation | PASS |  |
| Every renewal points to the same person's earlier policy on the same vehicle/property | PASS |  |
| Importer linking simulation: every policy links to its own quotation | PASS | 0 problems |
| Client full names unique | PASS |  |
| No two clients look alike to the importers (name similarity below 70) | PASS | highest pair = 69.8 |
| Owners with two properties: the two locations are clearly different (below 85) | PASS | highest = 69.3; owners with 2 properties = 28 |
| Every address comes from the verified pool | PASS |  |
| Claim amounts: LOA within estimate, Net = LOA - deductible, all positive | PASS | [] |
| Policy amount equals its quotation amount | PASS |  |
| Final Status always agrees with Claim Investigation Result | PASS | [] |
| Pattern: High-flood motor policies claim more than no-hazard ones | PASS | {'High': (23.6, 250), 'Low': (17.8, 118), 'Medium': (23.3, 227), 'none': (16.2, 235)} |
| Pattern: Commercial vehicles claim more than Private | PASS | {'Commercial': (33.0, 200), 'Private': (16.7, 630)} |
| Pattern: High-flood fire properties claim more than no-hazard ones | PASS | {'High': (13.6, 176), 'Low': (5.6, 107), 'Medium': (8.5, 165), 'none': (7.5, 173)} |
| Pattern: class b buildings claim more than class a | PASS | {'a': (6.0, 397), 'b': (14.7, 224)} |
| Pattern: fraud share rises with red-flag points | PASS | {0: (1.7, 118), 1: (9.1, 88), 2: (2.8, 36), 3: (18.4, 38), 4: (28.0, 25), 5: (22.2, 9), 6: (41.7, 12), 7: (56.2, 16)} |

## Planted patterns (claim rate %, number of ended policies)

- **Motor by flood category:** {'High': (23.6, 250), 'Low': (17.8, 118), 'Medium': (23.3, 227), 'none': (16.2, 235)}
- **Motor by classification:** {'Commercial': (33.0, 200), 'Private': (16.7, 630)}
- **Motor by color (should be flat):** {'Black': (27.3, 143), 'Blue': (15.8, 57), 'Brown': (6.9, 29), 'Gray': (23.2, 125), 'Green': (25.0, 16), 'Orange': (29.4, 17), 'Red': (19.7, 71), 'Silver': (18.6, 145), 'White': (18.5, 227)}
- **Motor renews a policy with a loss:** {False: (19.0, 762), True: (38.2, 68)}
- **Fire by flood category:** {'High': (13.6, 176), 'Low': (5.6, 107), 'Medium': (8.5, 165), 'none': (7.5, 173)}
- **Fire by construction class:** {'a': (6.0, 397), 'b': (14.7, 224)}
- **Fire by protection:** {'not protected': (11.6, 387), 'protected': (5.1, 234)}
- **Fraud share % by red-flag points (points: %, claims):** {0: (1.7, 118), 1: (9.1, 88), 2: (2.8, 36), 3: (18.4, 38), 4: (28.0, 25), 5: (22.2, 9), 6: (41.7, 12), 7: (56.2, 16)}

## Other figures

- Clients 1129, vehicles 743, properties 481
- Motor claim rows 351 (third party rows 43, CNC rows 33), fire claim rows 90
- Final status mix (paid claims): {'Hold per Client': 7, 'Closed Claim': 273, 'Not Push Through': 20, 'Denied Claim': 22, 'With Lacking Docs': 13, 'No Docs. Submitted': 7, 'Waiting for Claim Check': 11, 'Waiting for Billing': 5, 'Waiting for LOA': 4, 'Waiting for Evaluation': 3}
- Labels: {'Suspected Fraud': 23, 'Legitimate': 301, 'Confirmed Fraud': 18, None: 23}