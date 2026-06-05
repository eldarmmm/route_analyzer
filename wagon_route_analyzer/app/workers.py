"""Background threads: reference data loading and route report calculation."""

from datetime import datetime
import pandas as pd
import pyodbc
from PyQt5.QtCore import QThread, pyqtSignal

from .route_report import build_route_report
from .utils import clean_station_name, safe_str


class InitWorker(QThread):
    """Loads reference lists (managers, wagon types, stations) on startup."""

    companies_loaded = pyqtSignal(list)
    types_loaded     = pyqtSignal(list)
    stations_loaded  = pyqtSignal(list)
    error            = pyqtSignal(str)

    def __init__(self, conn_str):
        super().__init__()
        self.conn_str = conn_str

    def run(self):
        try:
            conn = pyodbc.connect(self.conn_str)

            # --- Managers ---
            # Update the query below to match your schema.
            # Expected result column: manager_name (VARCHAR)
            df_comp = pd.read_sql("""
                SELECT DISTINCT manager_name
                FROM your_ownership_history_table
                WHERE manager_name IS NOT NULL AND manager_name <> ''
                ORDER BY manager_name
            """, conn)
            self.companies_loaded.emit(
                sorted(df_comp['manager_name'].dropna().astype(str).tolist()))

            # --- Wagon types ---
            # Update the query below to match your schema.
            # Expected result column: type_name (VARCHAR)
            try:
                df_types = pd.read_sql("""
                    SELECT DISTINCT type_name
                    FROM your_wagon_type_table
                    WHERE type_name IS NOT NULL AND type_name <> ''
                    ORDER BY type_name
                """, conn)
                self.types_loaded.emit(
                    sorted(df_types['type_name'].dropna().astype(str).tolist()))
            except Exception:
                # Fallback: load wagon types from the operations cache table
                df_types = pd.read_sql("""
                    SELECT DISTINCT wagon_type_name AS type_name
                    FROM your_wagon_cache_table
                    WHERE wagon_type_name IS NOT NULL AND wagon_type_name <> ''
                    ORDER BY wagon_type_name
                """, conn)
                self.types_loaded.emit(
                    sorted(df_types['type_name'].dropna().astype(str).tolist()))

            # --- Stations ---
            # Update the query below to match your schema.
            # Expected result column: station_name (VARCHAR)
            st_df = pd.read_sql("""
                SELECT DISTINCT station_name
                FROM your_station_reference_table
                WHERE station_name IS NOT NULL AND station_name <> ''
                ORDER BY station_name
            """, conn)
            stations = sorted({
                clean_station_name(x)
                for x in st_df['station_name'].dropna().astype(str)
                if clean_station_name(x)
            })
            self.stations_loaded.emit(stations)
            conn.close()

        except Exception as e:
            self.error.emit(str(e))


class RouteReportWorker(QThread):
    """Builds the full route report in a background thread."""

    progress = pyqtSignal(int, str)
    finished = pyqtSignal(pd.DataFrame)
    error    = pyqtSignal(str)
    log      = pyqtSignal(str)

    def __init__(self, conn_str, date_from, date_to,
                 load_station='All', unload_station='All',
                 manager='All', wagon_types=None):
        super().__init__()
        self.conn_str      = conn_str
        self.date_from     = date_from
        self.date_to       = date_to
        self.load_station  = load_station  or 'All'
        self.unload_station = unload_station or 'All'
        self.manager       = manager       or 'All'
        self.wagon_types   = set(wagon_types or [])

    def emit_log(self, msg):
        ts = datetime.now().strftime('%H:%M:%S')
        self.log.emit(f'[{ts}] {msg}')

    def _station_name_to_groups(self, station_text, st_df):
        """Resolves a display station name to a set of CodeGroup values."""
        if not station_text or station_text == 'All':
            return set()
        target = clean_station_name(station_text).upper()
        groups = set()
        for _, r in st_df.iterrows():
            name = clean_station_name(r['station_name']).upper()
            if name == target:
                c  = safe_str(r['station_code'])
                cg = safe_str(r['code_group'])
                groups.add(cg if cg and cg not in ('nan', 'None') else c)
        return groups

    def run(self):
        try:
            self.progress.emit(2, 'Connecting to database...')
            self.emit_log('Connecting to database...')
            conn = pyodbc.connect(self.conn_str)
            self.emit_log('Connected!')

            # ----------------------------------------------------------
            # 1. Station reference
            # ----------------------------------------------------------
            # Update column names to match your schema:
            #   station_code  — the primary station code used in operations
            #   code6         — optional 6-digit code (used for legacy matching)
            #   station_name  — human-readable station name
            #   station_id    — numeric ID for distance lookups
            #   code_group    — normalization group (multiple codes → one group)
            self.progress.emit(6, 'Loading station reference...')
            st_df = pd.read_sql("""
                SELECT station_code, code6, station_name, station_id, code_group
                FROM your_station_reference_table
                WHERE station_code IS NOT NULL AND station_name IS NOT NULL
            """, conn)
            st_df['station_code'] = st_df['station_code'].astype(str).str.strip()
            st_df['station_name'] = st_df['station_name'].astype(str).str.strip()
            st_df['code_group']   = st_df['code_group'].astype(str).str.strip()
            st_df['station_id']   = pd.to_numeric(st_df['station_id'], errors='coerce').astype('Int64')

            code_to_group = {}
            for _, r in st_df.iterrows():
                c  = safe_str(r['station_code'])
                cg = safe_str(r['code_group'])
                code_to_group[c] = cg if cg and cg not in ('', 'nan', 'None') else c

            load_groups   = self._station_name_to_groups(self.load_station,   st_df)
            unload_groups = self._station_name_to_groups(self.unload_station,  st_df)
            self.emit_log(f"Stations in reference: {len(st_df):,}")
            self.emit_log(f"Load filter: {self.load_station}; groups: {len(load_groups) or 'all'}")
            self.emit_log(f"Unload filter: {self.unload_station}; groups: {len(unload_groups) or 'from departure row'}")

            # ----------------------------------------------------------
            # 2. Distance matrix
            # ----------------------------------------------------------
            # Update column names to match your schema:
            #   from_station_id, to_station_id — numeric station IDs
            #   distance_km                    — distance in kilometres
            self.progress.emit(10, 'Loading distance matrix...')
            dist_df = pd.read_sql("""
                SELECT from_station_id, to_station_id, distance_km
                FROM your_distance_table
                WHERE distance_km > 0
                  AND from_station_id IS NOT NULL
                  AND to_station_id IS NOT NULL
            """, conn)
            dist_df['from_station_id'] = pd.to_numeric(dist_df['from_station_id'], errors='coerce').astype('Int64')
            dist_df['to_station_id']   = pd.to_numeric(dist_df['to_station_id'],   errors='coerce').astype('Int64')
            dist_df = dist_df.dropna(subset=['from_station_id', 'to_station_id'])
            distance_dict = {}
            for _, r in dist_df.iterrows():
                fr, to = int(r['from_station_id']), int(r['to_station_id'])
                distance_dict[(fr, to)] = r['distance_km']
                distance_dict[(to, fr)] = r['distance_km']
            self.emit_log(f"Distance pairs: {len(distance_dict):,}")

            # ----------------------------------------------------------
            # 3. Wagon type cache (fast fallback)
            # ----------------------------------------------------------
            # Update column names to match your schema:
            #   wagon_number   — wagon identifier
            #   wagon_type     — type name string
            self.progress.emit(15, 'Loading wagon type cache...')
            try:
                vt_df = pd.read_sql("""
                    SELECT DISTINCT wagon_number, wagon_type
                    FROM your_wagon_cache_table
                    WHERE wagon_number IS NOT NULL AND wagon_type IS NOT NULL
                """, conn)
                vt_df['wagon_number'] = vt_df['wagon_number'].astype(str).str.strip()
                vt_df = vt_df.drop_duplicates(subset=['wagon_number'])
                vagon_type_dict = dict(zip(vt_df['wagon_number'], vt_df['wagon_type']))
            except Exception as e:
                vagon_type_dict = {}
                self.emit_log(f'Wagon type cache unavailable: {e}')

            # ----------------------------------------------------------
            # 4. Ownership history (for historical passport lookup)
            # ----------------------------------------------------------
            # Update column names to match your schema:
            #   wagon_number   — wagon identifier
            #   owner_name     — legal owner
            #   manager_name   — operational manager
            #   effective_date — date from which this record is valid
            #   wagon_type     — wagon type as of this date
            self.progress.emit(20, 'Loading ownership history...')
            try:
                pp_df = pd.read_sql("""
                    SELECT
                        wagon_number,
                        owner_name,
                        manager_name,
                        effective_date,
                        wagon_type
                    FROM your_ownership_history_table
                    WHERE wagon_number IS NOT NULL
                """, conn)
                pp_df['wagon_number']  = pp_df['wagon_number'].astype(str).str.strip()
                pp_df['effective_date'] = pd.to_datetime(pp_df['effective_date'], errors='coerce')
                pp_df = pp_df.dropna(subset=['wagon_number', 'effective_date'])
                pp_df = pp_df.sort_values(['wagon_number', 'effective_date'])
                passport_dict = {}
                for _, r in pp_df.iterrows():
                    cn = r['wagon_number']
                    passport_dict.setdefault(cn, []).append((
                        r['effective_date'],
                        str(r['owner_name'])   if pd.notna(r['owner_name'])   else '-',
                        str(r['manager_name']) if pd.notna(r['manager_name']) else '-',
                        str(r['wagon_type'])   if pd.notna(r['wagon_type'])   else '-',
                    ))
                self.emit_log(f"Ownership history records: {len(pp_df):,}")
            except Exception as e:
                passport_dict = {}
                self.emit_log(f'Ownership history unavailable: {e}')

            # ----------------------------------------------------------
            # 5. Candidate wagon selection
            # ----------------------------------------------------------
            # Update column names to match your schema:
            #   wagon_number      — wagon identifier
            #   operation_date    — date/time of the operation
            #   operation_code    — operation type (2 = departure, 1 = arrival)
            #   current_station_code  — station where the operation occurred
            #   dest_station_code     — destination station code from this departure
            self.progress.emit(35, 'Finding candidate wagons...')

            def sql_list(values):
                vals = [str(v).replace("'", "''") for v in values if str(v).strip()]
                return ','.join(f"'{v}'" for v in vals)

            load_code_filter = ''
            if load_groups:
                load_codes = [c for c, g in code_to_group.items() if g in load_groups]
                if load_codes:
                    load_code_filter = (
                        f" AND CAST(current_station_code AS varchar(30)) IN ({sql_list(load_codes)})")

            unload_code_filter = ''
            if unload_groups:
                unload_codes = [c for c, g in code_to_group.items() if g in unload_groups]
                if unload_codes:
                    unload_code_filter = (
                        f" AND CAST(dest_station_code AS varchar(30)) IN ({sql_list(unload_codes)})")

            candidate_sql = f"""
                SELECT DISTINCT wagon_number
                FROM your_operations_table WITH (NOLOCK)
                WHERE operation_date >= '{self.date_from}'
                  AND operation_date < DATEADD(day, 1, '{self.date_to}')
                  AND wagon_number IS NOT NULL
                  AND operation_code = 2
                  {load_code_filter}
                  {unload_code_filter}
            """
            cand_df = pd.read_sql(candidate_sql, conn)
            candidate_cars = (
                cand_df['wagon_number'].dropna().astype(str).str.strip().unique().tolist())
            self.emit_log(f"Candidate wagons (strict departure match): {len(candidate_cars):,}")

            if not candidate_cars:
                conn.close()
                self.finished.emit(pd.DataFrame())
                return

            # ----------------------------------------------------------
            # 6. Load full operation history for candidate wagons
            # ----------------------------------------------------------
            # Update the SELECT column aliases to match route_report.py expectations:
            #   Номер_вагона, Дата_операции, Код_операции,
            #   Код_текущей_станции, Станция_текущая, id_текущей_станции,
            #   Код_станции_назначения, Станция_назначения, id_станции_назначения,
            #   Накладная, Код_груза, Вес, IsFull
            self.progress.emit(40, 'Loading operations for candidate wagons...')
            frames     = []
            chunk_size = 400
            total_chunks = (len(candidate_cars) + chunk_size - 1) // chunk_size

            for chunk_no, start in enumerate(
                    range(0, len(candidate_cars), chunk_size), start=1):
                chunk   = candidate_cars[start:start + chunk_size]
                cars_in = sql_list(chunk)
                pct     = 40 + int(20 * chunk_no / max(total_chunks, 1))
                self.progress.emit(pct, f'Loading operations: batch {chunk_no}/{total_chunks}')
                self.emit_log(f"Batch {chunk_no}/{total_chunks}: {len(chunk):,} wagons")

                part = pd.read_sql(f"""
                    SELECT
                        ops.wagon_number            AS Номер_вагона,
                        ops.operation_date          AS Дата_операции,
                        ops.operation_code          AS Код_операции,
                        ops.current_station_code    AS Код_текущей_станции,
                        st_cur.station_name         AS Станция_текущая,
                        st_cur.station_id           AS id_текущей_станции,
                        ops.dest_station_code       AS Код_станции_назначения,
                        st_dest.station_name        AS Станция_назначения,
                        st_dest.station_id          AS id_станции_назначения,
                        ops.waybill_number          AS Накладная,
                        ops.cargo_code              AS Код_груза,
                        ops.weight                  AS Вес,
                        ops.is_loaded               AS IsFull
                    FROM your_operations_table ops WITH (NOLOCK)
                    LEFT JOIN your_station_reference_table st_cur
                        ON ops.current_station_code = st_cur.station_code
                    LEFT JOIN your_station_reference_table st_dest
                        ON ops.dest_station_code = st_dest.station_code
                    WHERE ops.operation_date >= '{self.date_from}'
                      AND ops.operation_date < DATEADD(day, 46, '{self.date_to}')
                      AND ops.wagon_number IN ({cars_in})
                      AND ops.wagon_number IS NOT NULL
                    ORDER BY ops.wagon_number, ops.operation_date
                """, conn)
                frames.append(part)

            conn.close()
            df = pd.concat(frames, ignore_index=True) if frames else pd.DataFrame()
            self.emit_log(f"Operations loaded: {len(df):,}")

            # ----------------------------------------------------------
            # 7. Type casting and cleanup
            # ----------------------------------------------------------
            self.progress.emit(55, 'Preparing data...')
            if df.empty:
                self.finished.emit(pd.DataFrame())
                return

            df['Дата_операции']         = pd.to_datetime(df['Дата_операции'],         errors='coerce')
            df['Код_операции']          = pd.to_numeric(df['Код_операции'],           errors='coerce').astype('Int64')
            df['Код_груза']             = pd.to_numeric(df['Код_груза'],              errors='coerce').astype('Int64')
            df['Вес']                   = pd.to_numeric(df['Вес'],                    errors='coerce').fillna(0)
            df['id_текущей_станции']    = pd.to_numeric(df['id_текущей_станции'],     errors='coerce').astype('Int64')
            df['id_станции_назначения'] = pd.to_numeric(df['id_станции_назначения'],  errors='coerce').astype('Int64')
            df['IsFull']                = pd.to_numeric(df['IsFull'],                 errors='coerce')
            df['Номер_вагона']          = df['Номер_вагона'].astype(str).str.strip()
            df['Код_текущей_станции']   = df['Код_текущей_станции'].astype(str).str.strip()
            df['Код_станции_назначения'] = df['Код_станции_назначения'].astype(str).str.strip()
            df['Станция_текущая']       = df['Станция_текущая'].fillna('').astype(str).str.strip()
            df = df.dropna(subset=['Дата_операции', 'Код_операции', 'Номер_вагона'])
            df['IsFull'] = df['IsFull'].fillna(-1).astype(int)
            df = df.sort_values(['Номер_вагона', 'Дата_операции'])

            # ----------------------------------------------------------
            # 8. Build route report
            # ----------------------------------------------------------
            self.progress.emit(70, 'Building routes...')
            result_df = build_route_report(
                df,
                distance_dict=distance_dict,
                passport_dict=passport_dict,
                code_to_group=code_to_group,
                load_station_groups=load_groups,
                unload_station_groups=unload_groups,
                manager_filter=None if self.manager == 'All' else self.manager,
                wagon_types_filter=self.wagon_types,
                fallback_type_dict=vagon_type_dict,
                dep_date_from=self.date_from,
                dep_date_to=self.date_to,
            )

            self.emit_log(f"Done! Report rows: {len(result_df):,}")
            self.progress.emit(100, 'Done!')
            self.finished.emit(result_df)

        except Exception:
            import traceback
            self.error.emit(traceback.format_exc())
