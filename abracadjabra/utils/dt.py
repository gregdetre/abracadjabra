import re
from calendar import monthrange
from datetime import datetime, date, timedelta

from django.contrib.humanize.templatetags.humanize import naturalday
from django.utils import timezone

def serialize_datetimes(d, level=0):
    """
    Recursively walks through a dictionary, serializing datetime objects
    into ISO 8601 formatted strings. 

    Set a (somewhat arbitrary) maximum of 20 levels of dictionaries. We
    should never get to more than that, but if we do, it will just stop
    serializing datetimes.
    """
    if level > 20:
        raise ValueError('Too many levels trying to serialize datetimes')

    for k in d.keys():
        if type(d[k]) == datetime:
            d[k] = d[k].isoformat()
        elif type(d[k]) == dict:
            d[k] = serialize_datetimes(d[k], level + 1)
        else:
            pass
    return d

def datetime_to_date(dt):
    return date(year=dt.year, month=dt.month, day=dt.day)

def date_to_datetime(dt):
    if isinstance(dt, datetime):
        return dt
    return datetime(year=dt.year, month=dt.month, day=dt.day)

def month_name(dt):
    return datetime.strftime(dt, '%B')


def near_in_time(dt1, dt2=None):
    """
    Compares two datetime and ensures that they're within 1s
    of each other. Doesn't care which came first. Useful for unit tests.
    """
    if dt2 is None:
        dt2 = timezone.now()
    dt_diff = abs(dt1 - dt2)
    return dt_diff.days == 0 and dt_diff.seconds < 1


def timedelta_float(td, units='days'):
    """
    Returns a float of timedelta TD in UNITS
    (either 'days' or 'seconds').

    Can be negative for things in the past.
    
    timedelta returns the number of
    days and the number of seconds, but you have to combine
    them to get a float timedelta.

    e.g. timedelta_float(now() - dt_last_week) == c. 7.0
    """
    # 86400 = number of seconds in a day
    if units == 'days':
        return td.days + td.seconds / 86400.0
    elif units == 'seconds':
        return td.days*86400.0 + td.seconds
    else:
        raise Exception('Unknown units %s' % units)


def pp_date(dt):
    """
    Human-readable (i.e. pretty-print) dates, e.g. for spreadsheets:

    See http://docs.python.org/tutorial/stdlib.html

    e.g. 31-Oct-2011
    """
    d = date_to_datetime(dt)
    return d.strftime('%d-%b-%Y')


def dt_str(dt=None, hoursmins=True, seconds=True):
    """
    Returns the current date/time as a yymmdd_HHMM_S string,
    e.g. 091016_1916_21 for 16th Oct, 2009, at 7.16pm in the
    evening.

    By default, returns for NOW, unless you feed in DT.
    """
    if dt is None:
        dt = timezone.now()
    fmt = '%y%m%d'
    if hoursmins:
        fmt += '_%H%M'
    if seconds:
        fmt += '_%S'
    return dt.strftime(fmt)


def str_dt(str):
    """
    Returns the current date/time as a DATETIME object, when
    fed in a yymmdd_HHMM_S string. See DT_STR.
    """
    return timezone.now().strptime(str, '%y%m%d_%H%M_%S')


def alltime():
    # return YourModel.happened.order_by('dt')[0].dt
    #
    # hardcode to avoid the query
    return datetime(year=2009, month=10, day=31, hour=22, minute=34, second=6)

def first_last_day_of_month(dt):
    """
    Returns two DATETIMES, one for the first and one for the
    last day of the month of DT.
    """
    first_day = datetime(year=dt.year, month=dt.month, day=1)
    nDays = monthrange(dt.year, dt.month)[1]
    last_day = datetime(year=dt.year, month=dt.month, day=nDays)
    return first_day, last_day
    

def recent_hour(nHours=1, dt=None):
    """
    Returns the DT for 1 hour (i.e. 3600 seconds) ago.
    """
    seconds = nHours * 3600
    dt = dt or timezone.now()
    return dt - timedelta(seconds=seconds)


def recent_day(nDays=1, dt=None):
    """
    Returns the DT for 1 day (i.e. 24 hours) ago.

    If NDAYS == 24 hours * NDAYS.
    """
    dt = dt or timezone.now()
    return dt - timedelta(days=nDays)

def start_of_day(dt=None):
    """
    Returns the Datetime for DT at midnight, i.e. the start of the day.
    """
    dt = dt or timezone.now()
    return datetime(year=dt.year, month=dt.month, day=dt.day)

def end_of_day(dt=None):
    dt = dt or timezone.now()
    return datetime(year=dt.year, month=dt.month, day=dt.day, hour=23, minute=59, second=59)

def start_of_week(dt=None):
    """
    Returns the DT for the beginning of the week (i.e. the most recent Monday at 00:01.
    """
    # weekday(): Monday = 0. http://docs.python.org/library/datetime.html
    dt = dt or timezone.now()
    # subtract however many days since Monday from today to get to Monday
    return start_of_day(dt - timedelta(days=dt.weekday()))

def end_of_week(dt=None):
    dt = dt or timezone.now()
    return end_of_day(dt + timedelta(days=(6 - dt.weekday())))

def start_of_month(dt=None):
    dt = dt or timezone.now()
    # xxx - we could have also used:
    # start_of_day(now - timedelta(days=now.day))
    return first_last_day_of_month(dt)[0]

def end_of_month(dt=None):
    dt = dt or timezone.now()
    return first_last_day_of_month(dt)[1] + timedelta(hours=23, minutes=59, seconds=59)

def day_containing(dt=None):
    """Return the half-open day interval containing dt.

    i.e. if dt is Today 12:26, return (Today 00:00, Tomorrow 00:00).
    This can be used for a half-open comparison:

        p, n = day_containing()
        if x >= p and x < n:
            # Do something because x is today.
    """

    p = start_of_day(dt)
    n = p + timedelta(days=1)

    return p, n

def daily_iter(start, end):
    """Iterate over half-open day intervals pairwise until the end of the range falls after end."""

    p = start
    n = start + timedelta(days=1)

    while n < end:
        yield p, n
        p = n
        n = n + timedelta(days=1)

def week_containing(dt=None):
    """Returns a half-open interval of the week containing dt, starting on Sunday."""

    p = start_of_week(dt)
    n = p + timedelta(days=7)
    return p, n

def weekly_iter(start, end):
    """Iterate over weeks pairwise until the end of the range falls after end."""

    p = start
    n = start + timedelta(days=7)

    while n < end:
        yield p, n
        p = n
        n = n + timedelta(days=7)

def month_containing(dt=None):
    """Returns a half-open interval of the month containing dt."""

    m = start_of_month(dt)
    p, n = first_last_day_of_month(m)
    n = n + timedelta(days=1)

    return p, n

def all_time_containing(dt=None):
    """Returns a half-open interval of all time."""

    return datetime(year=1900, month=1, day=1), datetime.max

def recent_week(dt=None):
    """
    Returns the DT for 7 days ago.
    """
    dt = dt or timezone.now()
    return dt - timedelta(days=7)

def recent_month(dt=None):
    """
    Returns the DT for 30 days ago. If you care about
    first/last day of the month, see
    first_last_day_of_month().
    """
    dt = dt or timezone.now()
    return dt - timedelta(days=30)

def recent_3months(dt=None):
    dt = dt or timezone.now()
    return dt - timedelta(days=90)

def recent_year(dt=None):
    dt = dt or timezone.now()
    return dt - timedelta(days=365)

def recent_6months(dt=None):
    dt = dt or timezone.now()
    return dt - timedelta(days=180)

def start_of_year(dt=None):
    dt = dt or timezone.now()
    return datetime(year=dt.year, month=1, day=1)

def end_of_year(dt=None):
    dt = dt or timezone.now()
    return datetime(year=dt.year, month=12, day=31, hour=23, minute=59, second=59)

def disp_days(days):
    """
    Returns a human readable string for DAYS duration.
    """
    if isinstance(days, timedelta):
        days = timedelta_float(days)
    if days < 1:
        return '%.0f minutes' % days_in_minutes(days)
    else:
        return naturalday(days)

def days_in_minutes(days):
    """
    Returns int minutes for float DAYS.
    """
    return days * 60 * 24


def days_in_range(start_dt, end_dt=None, reverse=False):
    """
    Returns a list of DATEs from START_DT to END_DT
    (inclusive), e.g. would return Dates for yesterday and
    today for START_DT = recent_day().

    Returns [] if START_DT > END_DT.
    """
    if not end_dt:
        end_dt = datetime.today()
    start_dt = datetime_to_date(start_dt)
    end_dt = datetime_to_date(end_dt)
    if start_dt > end_dt:
        return []
    cur_dt = start_dt
    dts = []
    while cur_dt <= end_dt:
        dts.append(cur_dt)
        cur_dt += timedelta(days=1)
    if reverse:
        dts.reverse()
    return dts


# str key -> (function, human-readable description)
#
# e.g. to get all the dates in the last 3 months:
#     start_dt = dt_ranges['recent_3months'][0]()
#     dts = days_in_range(start_dt)

dt_ranges = {
    'recent_hour': (recent_hour, None, 'in the last hour',),
    'recent_day': (recent_day, None, 'in the last 24 hours',),
    'recent_week': (recent_week, None, 'in the last 7 days',),
    'recent_month': (recent_month, None,'in the last 30 days',),
    'recent_3months': (recent_3months, None,'in the last 90 days',),
    'recent_6months': (recent_6months, None,'in the last 180 days',),
    'recent_year': (recent_year, None,'in the last 365 days',),
    'start_of_day': (start_of_day, end_of_day, 'since the beginning of today',),
    'start_of_week': (start_of_week, end_of_week, 'since the beginning of the week',),
    'start_of_month': (start_of_month, end_of_month, 'since the beginning of the month',),
    'start_of_year': (start_of_year, end_of_year, 'since beginning of the year',),
    'alltime': (alltime, None, 'since the beginning of time',),
}

