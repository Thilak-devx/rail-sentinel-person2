Task 17E Route Sections Correction Report
==================================================

Raw route rows: 85055
Unique trains: 3892

Task 13 cleanup applied:
- Train 16546: removed stnSerialNumber 41-80 (40 rows removed)
- Train 16546 retained: serials 1-40
- Train 17029: HG at serials 11 and 14 preserved
- Train 17030: HG at serials 18 and 20 preserved

Cleaned route rows: 85015

Route sections created: 81123

Distance classification:
- Valid (distance_to_next >= 0): 77230
- Missing current distance: 0
- Missing next distance: 3892
- Negative distance (dist < 0): 1

16546 result:
- Route rows: 40
- Sections: 0
- current_stn_serial notna: 0
- next_stn_serial notna: 0

17029 result:
- HG at serial 11: preserved
- HG at serial 14: preserved

17030 result:
- HG at serial 18: preserved
- HG at serial 20: preserved

Sequence validation:
- current_stn_serial >= next_stn_serial: 1
- current_station_code == next_station_code: 0

Duplicate section keys (train_number, current_stn_serial, next_stn_serial): {dup_keys}

Output files:
- data/processed/route_sections_corrected.csv
- docs/route_sections_corrected_report.md
