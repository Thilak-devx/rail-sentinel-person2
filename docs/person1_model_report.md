# Person 1 — Data & Prediction Engine

## 1. Data Sources

- **Kaggle railway schedule dataset**: Provides the base train timetable and delay information
- **RSTGCN September 2024 railway delay dataset**: The primary source for delay patterns used in model training

The dataset contains September 2024 railway schedule data with arrival/departure times, train numbers, station codes, and distance measurements.

## 2. Dataset Construction

### Route Sections
- Each train route is decomposed into segments between consecutive stations
- Historical delay statistics are computed per section using prior-day data
- Section features include: average delay, median delay, standard deviation, and observation count

### Current Delay
- `current_arrival_delay_min`: The arrival delay at the current station in minutes
- This is the primary target variable for prediction

### Next-Station Target
- The model predicts `target_next_arrival_delay_min`: the expected delay at the next station
- This is a chronological forecasting problem, not a classification

### Historical Section Delay
- `historical_section_avg_delay`: Mean delay for this section using only strictly earlier dates
- `section_historical_median_delay`: Median delay for this section using only strictly earlier dates
- `section_historical_std_delay`: Standard deviation of section delays using only strictly earlier dates
- `section_historical_count`: Number of historical observations used

### Temporal Features
- `day_of_week`: Integer 0 (Monday) through 6 (Sunday)
- `time_of_day`: Float in hours (0.0-24.0), representing the time of the observed arrival

### Additional Historical Features
- `current_delay_minus_section_avg`: Current delay minus the filled historical section average
- `train_historical_avg_delay`: Average delay across the entire train route, filled with training-only fallback

### Why Coordinates/Haversine Were Not Included
- No station coordinate data was available in the project dataset
- The model features rely on section-based historical statistics rather than geographical distance
- Haversine distance was evaluated but no station lat/lon fields existed in the processed data

## 3. Leakage Prevention

### Chronological Split
- **Train**: 2024-09-01 to 2024-09-21 (855,486 rows)
- **Validation**: 2024-09-22 to 2024-09-25 (163,236 rows)
- **Test**: 2024-09-26 to 2024-09-30 (206,046 rows)
- No random splitting or shuffling is used — all splits are strictly date-based

### Historical Features Using Strictly Earlier Dates
- All historical features (section averages, medians, std dev) are computed using only data from before the prediction row
- Training-only missing-value fallbacks are used:
  - `historical_section_avg_delay`: 15.0 minutes
  - `section_historical_median_delay`: 9.0 minutes
  - `section_historical_std_delay`: 13.399174556213485 minutes
  - `train_historical_avg_delay`: 26.0 minutes
- Validation and test sets use the same fallbacks derived from training data only — no peeking at future data

### No Target Leakage
- Features like `current_delay_minus_section_avg` are constructed from the current delay and filled historical average only
- No future information (weather, coordinates, later-day delays) is included
- The chronological split ensures training data always precedes validation/test data

## 4. Models

| Model | TEST MAE (minutes) | Improvement over Naive |
|-------|--------------------|----------------------|
| Naive baseline | 9.8544 | — |
| XGBoost v1 | 10.7226 | -8.7% (worse than naive) |
| XGBoost v2 | 9.3003 | 5.6% improvement |
| LightGBM v1 | 9.2938 | 5.7% improvement |
| **LightGBM Quantile P50** | **7.8776** | **20.06% improvement** |

### LightGBM Quantile Model (Current Primary)
- Three separate models trained for P10, P50, and P90 quantiles
- `objective: 'quantile'` with `alpha` values of 0.10, 0.50, and 0.90
- 500 estimators, learning rate 0.05, 31 leaves, subsample 0.8, colsample 0.8
- Features: 10 leakage-safe features with training-only fallbacks
- Models saved as: `lightgbm_eta_p10.txt`, `lightgbm_eta_p50.txt`, `lightgbm_eta_p90.txt`

### P10-P90 Prediction Interval
- P10 (lower bound): 10th percentile prediction
- P50 (primary prediction): 50th percentile (median) prediction
- P90 (upper bound): 90th percentile prediction
- enforced ordering: P10 <= P50 <= P90 via sorting of the three model outputs
- Test coverage: 80.51% (approximately 80% of test targets fall within the P10-P90 interval)
- Average interval width: 25.5464 minutes

## 5. Final Model

**LightGBM Quantile P50 Model** is the current primary prediction model.

- **TEST MAE**: 7.8776 minutes
- **Improvement over naive baseline**: 20.06%
- Model files: `models/lightgbm_eta_p10.txt`, `models/lightgbm_eta_p50.txt`, `models/lightgbm_eta_p90.txt`
- Primary output: `predicted_delay_min` (the P50 quantile)

## 6. Uncertainty

### P10-P90 Prediction Interval

This is an **empirical 80% prediction interval**, NOT a guaranteed confidence interval.

- **P10** (`confidence_low_min`): Lower bound prediction — 10th percentile
- **P50** (`predicted_delay_min`): Primary prediction — 50th percentile (median)
- **P90** (`confidence_high_min`): Upper bound prediction — 90th percentile
- **Test coverage**: 80.51% of test targets fall within the P10-P90 interval
- **Average interval width**: 25.5464 minutes

The interval reflects the model's uncertainty quantification based on the quantile regression objective, but should not be interpreted as a guaranteed coverage guarantee on future data.

### Limitations
- September 2024 delay data only — quality depends on available historical patterns
- No station coordinates available in the project
- No weather feature currently included
- Model has not been validated on a future period beyond the available dataset

## 7. API

### POST /predict-eta

**Response fields:**

| Field | Type | Description |
|-------|------|-------------|
| `predicted_delay_min` | float | Primary predicted delay in minutes (P50 quantile) |
| `confidence_low_min` | float | Lower bound of 801h