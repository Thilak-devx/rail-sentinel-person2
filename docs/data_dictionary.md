# RailSentinel SIH26028 — Dataset Dictionary

## Source
- Kaggle dataset: "Indian Railways Schedule-Prices-Availability Data" by bhavyarajdev
- Downloaded and extracted to `data/raw/`

## Files

### schedules.csv
- Rows: 3,292
- Columns: 13
- File size: 16,772,831 bytes

#### Column meanings:
- trainNumber: train identifier (int64)
- trainName: train name (str)
- stationFrom: source station (str)
- stationTo: destination station (str)
- trainRunsOnMon: whether train runs on Monday (str)
- trainRunsOnTue: whether train runs on Tuesday (str)
- trainRunsOnWed: whether train runs on Wednesday (str)
- trainRunsOnThu: whether train runs on Thursday (str)
- trainRunsOnFri: whether train runs on Friday (str)
- trainRunsOnSat: whether train runs on Saturday (str)
- trainRunsOnSun: whether train runs on Sunday (str)
- timeStamp: timestamp of observation (str)
- stationList: per-station details (JSON str)

#### Route/schedule information:
- train identifier (number)
- train name
- source station
- destination station
- timestamp of observation
- per-station details (JSON with station codes, names, times, distances)

#### Per-station details (stationList JSON):
Each row's stationList contains a JSON array with entries having:
- stationCode: station code identifier
- stationName: station name
- arrivalTime: scheduled arrival time (often '--' at terminals)
- departureTime: scheduled departure time (often '--' at terminals)
- distance: section distance in km from origin
- dayCount: day count marker
- stnSerialNumber: station sequence number
- boardingDisabled: whether boarding is disabled

#### Delay-label status:
- NOT PRESENT: No actual arrival/departure time columns found in top-level schema
- Delay labels must come from external source (runningstatus.in)

#### Coordinate status:
- NOT PRESENT: No latitude/longitude columns in this file
- Coordinates must come from external source

#### Distance status:
- AVAILABLE: Distance column(s) present in top-level schema (within stationList JSON entries as section distance in km)

--

### price_data.csv
- Large file (~125MB) - inspected via chunked reading
- Key columns identified from first chunks: train identifiers, route/station identifiers, fare/price fields, class information, availability fields, date fields
- Relevance to ETA prediction: fare/price data not directly useful for ETA, but may contain train/route identifiers that could supplement schedule data

--

## Important Distinction

### ROUTE/SCHEDULE DATA (from schedules.csv)
- Train schedules and station sequences
- Scheduled arrival/departure times
- Station names and routes
- Section distances within station list
- Does NOT contain real delay labels

### REAL DELAY-LABEL DATA (NOT in this dataset)
- Requires observations from runningstatus.in or similar
- Actual arrival times vs scheduled times
- Computed delay = actual - scheduled
- Must be collected separately