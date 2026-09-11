import pandas as pd
import os

base = r"C:\Users\2026\OneDrive\Desktop\sih train"

# Step 1: Load candidates
candidates = pd.read_csv(os.path.join(base, "data", "processed", "train_date_section_candidates.csv"))
print(f"Loaded candidates: {len(candidates)} rows")

# Step 2: Load delay lookup
delay_lookup = pd.read_csv(os.path.join(base, "data", "processed", "delay_lookup.csv"))
print(f"Loaded delay_lookup: {len(delay_lookup)} rows")

# Step 3: Rename delay lookup columns
delay_renamed = delay_lookup.rename(
    columns={
        "station_code": "current_station_code",
        "arrival_delay_min": "current_arrival_delay_min",
    }
)
print(f"Renamed delay lookup columns: {list(delay_renamed.columns)}")

# Step 4: Verify uniqueness in delay_lookup
key_check = delay_renamed.drop_duplicates(subset=["train_number", "date", "current_station_code"])
print(f"\nStep 4 - Uniqueness check (train_number, date, current_station_code):")
print(f"  Original rows: {len(delay_renamed)}")
print(f"  After dedup: {len(key_check)}")
print(f"  Duplicates: {len(delay_renamed) - len(key_check)}")

# Step 5: INNER merge on train_number, date, current_station_code
merged = candidates.merge(
    delay_renamed,
    on=["train_number", "date", "current_station_code"],
    how="inner",
)

print(f"\nStep 5 - INNER merge results:")
print(f"  Candidate rows: {len(candidates)}")
print(f"  Merge key columns: train_number, date, current_station_code")
print(f"  Matched rows: {len(merged)}")

# Step 6: Verify logical key uniqueness
key_check_merged = merged.duplicated(
    subset=["train_number", "date", "current_stn_serial", "next_stn_serial"]
).sum()
print(f"\nStep 6 - Logical key uniqueness (train_number, date, current_stn_serial, next_stn_serial):")
print(f"  Duplicates: {key_check_merged}")

# Step 7: Verify output rows <= 1,224,768
print(f"\nStep 7 - Row count check:")
print(f"  Output rows: {len(merged)}")
print(f"  Max allowed: 1224768")
print(f"  Within limit: {len(merged) <= 1224768}")

# Step 8: Save output
output_path = os.path.join(base, "data", "processed", "current_delay_dataset.csv")
merged.to_csv(output_path, index=False)
print(f"\nStep 8 - Saved to: {output_path}")

# Step 9: Read back and report
read_back = pd.read_csv(output_path)
print(f"\n=== READ BACK VERIFICATION ===")
print(f"  Input rows (candidates): {len(candidates)}")
print(f"  Matched rows (after inner merge): {len(merged)}")
print(f"  Unmatched rows (candidates - matched): {len(candidates) - len(merged)}")
print(f"  Output rows: {len(read_back)}")
print(f"  Duplicate logical keys: {read_back.duplicated(subset=['train_number', 'date', 'current_stn_serial', 'next_stn_serial']).sum()}")
print(f"  Null current_arrival_delay_min: {read_back['current_arrival_delay_min'].isna().sum()}")
print(f"  current_arrival_delay_min stats:")
delay_col = read_back['current_arrival_delay_min']
print(f"    min: {delay_col.min()}")
print(f"    max: {delay_col.max()}")
print(f"    mean: {delay_col.mean():.2f}")
print(f"    median: {delay_col.median():.2f}")

# Leading-zero analysis
print(f"\n=== LEADING-ZERO TRAINS ===")
lz_candidates = merged[merged['train_number'].isin([5046])]
print(f"  Leading-zero train rows in output: {len(lz_candidates)}")

# Special trains
print(f"\n=== SPECIAL TRAINS ===")
t16546 = merged[merged['train_number'] == 16546]
print(f"  16546 rows: {len(t16546)}")

t17029 = merged[merged['train_number'] == 17029]
print(f"  17029 rows: {len(t17029)}")

t17030 = merged[merged['train_number'] == 17030]
print(f"  17030 rows: {len(t17030)}")

print(f"\n=== ALL DONE ===")
print(f"Output path: {output_path}")