"""Бизнес-логика маршрутного отчёта без расчёта оборотов."""

from collections import Counter
import pandas as pd

from .utils import clean_station_name, hours_between, safe_str

ARRIVAL_CODES = {1, 10}      # обычно ПРИБ; 10 оставлен как запасной вариант
DEPARTURE_CODES = {2, 20}    # обычно ОТПР; 20 оставлен как запасной вариант


def _oper_name(code):
    try:
        c = int(code)
    except Exception:
        return safe_str(code)
    if c in ARRIVAL_CODES:
        return 'ПРИБ'
    if c in DEPARTURE_CODES:
        return 'ОТПР'
    return str(c)


def _to_int_or_none(v):
    try:
        if pd.notna(v):
            return int(v)
    except Exception:
        pass
    return None


def _distance(distance_dict, a, b):
    ia = _to_int_or_none(a)
    ib = _to_int_or_none(b)
    if ia is None or ib is None:
        return 0
    return float(distance_dict.get((ia, ib), distance_dict.get((ib, ia), 0)) or 0)


def _get_passport(passport_dict, wagon, date_value, fallback_type='-'):
    entries = passport_dict.get(str(wagon).strip(), []) if passport_dict else []
    dep_ts = pd.Timestamp(date_value).tz_localize(None) if pd.notna(date_value) else None
    best = None
    for dt, sobst, uprav, tip in entries:
        try:
            dt_ts = pd.Timestamp(dt).tz_localize(None)
        except Exception:
            continue
        if dep_ts is None or dt_ts <= dep_ts:
            best = (sobst, uprav, tip)
    if best:
        return best
    return '-', '-', fallback_type or '-'


def _station_group(code, code_to_group):
    c = safe_str(code)
    return code_to_group.get(c, c)


def _matches_station(group_code, station_filter_groups):
    if not station_filter_groups:
        return True
    return group_code in station_filter_groups


def _visit_ranges(route_rows, code_to_group):
    """Группирует подряд идущие строки одной станции в один визит."""
    visits = []
    if route_rows.empty:
        return visits

    start = 0
    prev_group = _station_group(route_rows.iloc[0]['Код_текущей_станции'], code_to_group)
    for pos in range(1, len(route_rows)):
        cur_group = _station_group(route_rows.iloc[pos]['Код_текущей_станции'], code_to_group)
        if cur_group != prev_group:
            visits.append((start, pos - 1))
            start = pos
            prev_group = cur_group
    visits.append((start, len(route_rows) - 1))
    return visits


def _single_row_station_hours(route_rows, pos):
    """Правило пользователя для станции, где в маршруте только одна строка.

    Если единственная строка станции — ОТПР, берём время от предыдущей строки до этой.
    Если ПРИБ — от этой строки до следующей.
    Для прочих операций используем следующий интервал, иначе предыдущий.
    """
    row = route_rows.iloc[pos]
    code = _to_int_or_none(row['Код_операции'])
    cur_dt = row['Дата_операции']

    if code in DEPARTURE_CODES and pos > 0:
        return hours_between(route_rows.iloc[pos - 1]['Дата_операции'], cur_dt)
    if code in ARRIVAL_CODES and pos + 1 < len(route_rows):
        return hours_between(cur_dt, route_rows.iloc[pos + 1]['Дата_операции'])
    if pos + 1 < len(route_rows):
        return hours_between(cur_dt, route_rows.iloc[pos + 1]['Дата_операции'])
    if pos > 0:
        return hours_between(route_rows.iloc[pos - 1]['Дата_операции'], cur_dt)
    return 0


def build_route_report_for_wagon(group, distance_dict, passport_dict, code_to_group,
                                 load_station_groups=None, unload_station_groups=None,
                                 manager_filter=None, wagon_types_filter=None,
                                 fallback_type_dict=None,
                                 dep_date_from=None, dep_date_to=None):
    """Строит строки отчёта по одному вагону в СТРОГОМ режиме.

    Новый принцип:
    1) старт маршрута = строка ОТПР, где текущая станция = выбранная станция погрузки;
    2) если выбрана станция выгрузки, CodeDestStation в этой же строке должен быть именно этой станцией;
    3) конец маршрута = первое появление вагона на выбранной/целевой станции назначения;
    4) в отчёт попадает только интервал от строки отправления до строки прибытия/появления
       на целевой станции. Операции до отправления и после прибытия не включаются.

    IsFull больше не является главным условием поиска рейса. Он может быть в данных,
    но маршрут определяется по CodeStation + CodeDestStation + датам операции.
    """
    if fallback_type_dict is None:
        fallback_type_dict = {}

    rows = group.sort_values('Дата_операции').reset_index(drop=True).copy()
    if rows.empty:
        return []

    period_from = pd.Timestamp(dep_date_from) if dep_date_from else None
    # date_to приходит как yyyyMMdd, поэтому верхняя граница включительно до конца дня
    period_to_excl = (pd.Timestamp(dep_date_to) + pd.Timedelta(days=1)) if dep_date_to else None

    wagon = safe_str(rows['Номер_вагона'].iloc[0])
    results = []
    n = len(rows)
    i = 0

    while i < n:
        row = rows.iloc[i]
        code_oper = _to_int_or_none(row['Код_операции'])
        if code_oper not in DEPARTURE_CODES:
            i += 1
            continue

        dep_date = row['Дата_операции']
        if period_from is not None and pd.Timestamp(dep_date) < period_from:
            i += 1
            continue
        if period_to_excl is not None and pd.Timestamp(dep_date) >= period_to_excl:
            i += 1
            continue

        load_group = _station_group(row['Код_текущей_станции'], code_to_group)
        if not _matches_station(load_group, load_station_groups):
            i += 1
            continue

        # Целевая станция берётся строго из выбранной станции выгрузки.
        # Если выгрузка не выбрана, используем CodeDestStation строки отправления.
        dest_group_from_row = _station_group(row['Код_станции_назначения'], code_to_group)
        if unload_station_groups:
            # ВАЖНО: именно здесь отсекаются рейсы Карабатано -> НЕ Вышестеблиевская.
            # Раньше программа могла взять любой ОТПР с Карабатано и потом найти
            # Вышестеблиевскую где-то дальше в истории вагона.
            if dest_group_from_row not in unload_station_groups:
                i += 1
                continue
            target_groups = set(unload_station_groups)
        else:
            if not dest_group_from_row:
                i += 1
                continue
            target_groups = {dest_group_from_row}

        fallback_type = fallback_type_dict.get(wagon, '-')
        sobstvennik, manager, wagon_type = _get_passport(passport_dict, wagon, dep_date, fallback_type)

        if manager_filter and manager_filter != 'Все' and safe_str(manager) != safe_str(manager_filter):
            i += 1
            continue
        if wagon_types_filter and safe_str(wagon_type) not in wagon_types_filter:
            i += 1
            continue

        # Ищем первое достижение станции назначения после отправления.
        # Желательно ПРИБ, но если в данных нет кода ПРИБ, берём первое появление
        # текущей станции = целевая станция.
        end_i = None
        first_target_i = None
        for j in range(i + 1, n):
            cur_group = _station_group(rows.iloc[j]['Код_текущей_станции'], code_to_group)
            if cur_group in target_groups:
                if first_target_i is None:
                    first_target_i = j
                j_oper = _to_int_or_none(rows.iloc[j]['Код_операции'])
                if j_oper in ARRIVAL_CODES:
                    end_i = j
                    break
                # Если первой строкой на станции назначения стоит не ПРИБ, всё равно
                # считаем, что вагон дошёл до назначения, но продолжаем поиск ПРИБ
                # только внутри этого же визита станции.
                if j + 1 >= n or _station_group(rows.iloc[j + 1]['Код_текущей_станции'], code_to_group) not in target_groups:
                    end_i = first_target_i
                    break

            # Защита от склейки разных рейсов: если до достижения назначения снова
            # встретили ОТПР с исходной станции, текущий маршрут считаем некорректным.
            if j > i + 1:
                j_oper = _to_int_or_none(rows.iloc[j]['Код_операции'])
                j_group = _station_group(rows.iloc[j]['Код_текущей_станции'], code_to_group)
                if j_oper in DEPARTURE_CODES and j_group == load_group and first_target_i is None:
                    break

        if end_i is None:
            i += 1
            continue

        unload_row = rows.iloc[end_i]
        route_rows = rows.iloc[i:end_i + 1].copy().reset_index(drop=True)
        visits = _visit_ranges(route_rows, code_to_group)
        route_id = f"{wagon}_{pd.Timestamp(dep_date).strftime('%Y%m%d%H%M%S')}"
        load_station_name = clean_station_name(row['Станция_текущая'])
        unload_station_name = clean_station_name(unload_row['Станция_текущая'])

        for num, (a, b) in enumerate(visits, start=1):
            first = route_rows.iloc[a]
            last = route_rows.iloc[b]
            station_name = clean_station_name(first['Станция_текущая'])
            first_dt = first['Дата_операции']
            last_dt = last['Дата_операции']
            ops = ', '.join(_oper_name(v) for v in route_rows.iloc[a:b + 1]['Код_операции'].tolist())

            if a == b:
                station_hours = _single_row_station_hours(route_rows, a)
            else:
                station_hours = hours_between(first_dt, last_dt)

            next_station = ''
            segment_distance = 0
            segment_hours = 0
            segment_speed = 0
            if num < len(visits):
                next_a, _ = visits[num]
                next_first = route_rows.iloc[next_a]
                next_station = clean_station_name(next_first['Станция_текущая'])
                segment_distance = _distance(distance_dict, last['id_текущей_станции'], next_first['id_текущей_станции'])
                segment_hours = hours_between(last_dt, next_first['Дата_операции'])
                if segment_distance > 0 and segment_hours > 0:
                    segment_speed = round(segment_distance / segment_hours * 24, 2)

            results.append({
                'ID маршрута': route_id,
                'Номер вагона': wagon,
                'Тип вагона': wagon_type,
                'В управлении': manager,
                'Собственник': sobstvennik,
                'Дата отправления': dep_date,
                'Станция погрузки': load_station_name,
                'Станция выгрузки': unload_station_name,
                '№ станции в маршруте': num,
                'Станция': station_name,
                'Дата первой операции на станции': first_dt,
                'Дата последней операции на станции': last_dt,
                'Операции на станции': ops,
                'Время на станции, ч': round(station_hours, 2),
                'Стоянка > 24 ч': 'Да' if station_hours > 24 else 'Нет',
                'Следующая станция': next_station,
                'Расстояние до следующей, км': round(segment_distance, 2),
                'Время участка, ч': round(segment_hours, 2),
                'Скорость участка, км/сут': round(segment_speed, 2),
            })

        # Не даём одному и тому же маршруту задублироваться внутри найденного интервала.
        i = max(i + 1, end_i + 1)

    return results

def build_route_report(df, distance_dict, passport_dict, code_to_group, **kwargs):
    all_rows = []
    groups = list(df.groupby('Номер_вагона'))
    for _, group in groups:
        all_rows.extend(build_route_report_for_wagon(
            group, distance_dict, passport_dict, code_to_group, **kwargs))
    return pd.DataFrame(all_rows)
