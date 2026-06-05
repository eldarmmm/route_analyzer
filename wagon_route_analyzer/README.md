# Wagon Route Analyzer

> Python desktop application that traces railcar journeys between two stations, breaks down dwell time at each intermediate stop, and identifies where delays most frequently occur.

---

## Background

In rail freight operations, knowing *that* a wagon was delayed is not enough — you need to know *where* in the route the delay happened and how often that station is a bottleneck across the entire fleet.

Standard reporting tools show wagon positions and operation logs, but they don't answer questions like:

- Which intermediate stations cause the most delays on a given route?
- How long does a wagon typically spend at each stop between Station A and Station B?
- What is the average transit speed between stations?

This tool was built to answer those questions using raw wagon movement history from an operational SQL database.

---

## What It Does

- **Route tracing** — finds all wagon trips between a selected loading station and unloading station within a date range
- **Intermediate stop breakdown** — for each trip, lists every station visited between origin and destination with arrival/departure timestamps
- **Dwell time calculation** — computes how long each wagon spent at each station (in hours)
- **Delay flagging** — marks stations where dwell time exceeded 24 hours
- **Segment metrics** — calculates distance, travel time, and average speed (km/day) between consecutive stations
- **Bottleneck identification** — aggregated view shows which stations accumulate the most delay hours across all wagons
- **Filters** — filter by wagon manager, wagon type, and date range
- **Excel export** — formatted report with all trip and station data

---

## How the Route Detection Works

The algorithm uses a strict matching approach to avoid false positives:

1. A trip **starts** at a `DEPARTURE` operation where the current station matches the selected loading station
2. The `CodeDestStation` field on that same departure row must match the selected unloading station (if specified)
3. A trip **ends** at the first appearance of the wagon at the target station — preferring an `ARRIVAL` operation, but accepting any operation if no arrival code is present
4. Rows between the departure and arrival are grouped into **station visits** — consecutive rows at the same station (resolved via CodeGroup normalization) are merged into a single visit
5. A guard prevents one trip from merging into the next: if a new departure from the origin station is detected before the target is reached, the current trip is discarded

This approach handles real-world data issues: the same physical station appearing under multiple codes, wagons changing ownership mid-route, and incomplete operation logs.

---

## Features in Detail

| Feature | Description |
|---|---|
| Station normalization | Multiple station codes resolved to a single group via CodeGroup reference |
| Historical passport lookup | Wagon owner, manager, and type fetched as-of the departure date |
| Single-row visit logic | Special handling for stations with only one logged operation (arrival or departure only) |
| Double-visit deduplication | Consecutive rows at the same station merged into one visit |
| Trip deduplication | Same wagon cannot generate two overlapping trips |
| Speed calculation | `distance / travel_hours × 24` — expressed in km/day |

---

## Tech Stack

| Layer | Technology |
|---|---|
| Language | Python 3.10+ |
| Data processing | pandas |
| Database connection | pyodbc (SQL Server) |
| Desktop UI | PyQt5 |
| Excel export | openpyxl |

---

## Project Structure

```
wagon-route-analyzer/
├─ app/
│  ├─ route_report.py     # core route detection and dwell time algorithm
│  ├─ workers.py          # background threads, SQL data loading, Excel export
│  ├─ main_window.py      # main window, filters, results table
│  ├─ widgets.py          # MultiSelectButton — multi-select dropdown component
│  ├─ utils.py            # date formatting, string cleaning, Excel helpers
│  ├─ styles.py           # dark theme QSS stylesheet
│  └─ __init__.py
├─ config.example.json
├─ requirements.txt
└─ main.py
```

---

## Output Columns

Each row in the report represents one station visit within one wagon trip:

| Column | Description |
|---|---|
| ID маршрута | Unique trip identifier (wagon + departure timestamp) |
| Номер вагона | Wagon number |
| Тип вагона | Wagon type (as of departure date) |
| В управлении | Manager (as of departure date) |
| Дата отправления | Departure date from loading station |
| Станция погрузки / выгрузки | Origin and destination stations |
| № станции в маршруте | Stop sequence number |
| Станция | Current stop name |
| Дата первой / последней операции | Timestamps of first and last operation at this stop |
| Операции на станции | Operation codes recorded at this stop |
| Время на станции, ч | Total dwell time in hours |
| Стоянка > 24 ч | Flag: Yes if dwell exceeded 24 hours |
| Следующая станция | Next stop in the route |
| Расстояние до следующей, км | Distance to next stop (km) |
| Время участка, ч | Travel time to next stop (hours) |
| Скорость участка, км/сут | Average speed to next stop (km/day) |

---

## Getting Started

### 1. Clone the repository

```bash
git clone https://github.com/eldarmmm/wagon-route-analyzer.git
cd wagon-route-analyzer
```

### 2. Install dependencies

```bash
pip install -r requirements.txt
```

### 3. Configure the connection

```bash
cp config.example.json config.json
```

Update `config.json` with your SQL Server connection details.

### 4. Run

```bash
python main.py
```

---

## Data Source

Connects to a SQL Server database. Expects tables for:

| Table | Purpose |
|---|---|
| Station reference | Station codes, names, CodeGroup mappings |
| Distance matrix | Distances between station pairs |
| Wagon ownership history | Owner, manager, wagon type with effective dates |
| Operations / movement log | Raw wagon movement records with operation codes and timestamps |

> Table and column names in this repository are placeholders. Update the SQL queries in `app/workers.py` to match your schema.

---

## Notes on the Public Version

This repository is sanitized for portfolio purposes:

- Database connection details removed
- Production table and column names replaced with generic placeholders
- Organization-specific references removed

---

## License

[MIT](LICENSE)

---

*Built to surface operational bottlenecks in rail freight routing — turning raw movement logs into actionable delay analytics.*
