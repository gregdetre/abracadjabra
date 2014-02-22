from functools import update_wrapper
import inspect
import logging
import re
import urllib

import django
from django.contrib.auth.models import User
from django.db.models.query import QuerySet
# from django.views.generic.simple import direct_to_template
from django.conf import settings as sett
from django.conf.urls import *
from django.core.cache import cache
from django.db import models
from django.http import Http404
from django.utils.datastructures import SortedDict

log = logging.getLogger(__name__)

# max_idx - see Experiment.calc_maxes()


def as_ids(qs):
    return list(qs.values_list('id', flat=True))


def compare_dict(d1, d2, ignore_underscores=True):
    """
    Returns None if they're the same, else returns the first
    key that differs.
    """
    for k, v in d1.items():
        if ignore_underscores and k.startswith('_'):
            continue
        if v != d2[k]:
            return k
    return None


def min2(a, b):
    """
    Wrapper around the min build-in that is robust to None.
    """
    if a and not b:
        return a
    elif b and not a:
        return b
    else:
        return min(a, b)


def max2(a, b):
    """
    Wrapper around the max built-in that is robust to None.
    """
    if a and not b:
        return a
    elif b and not a:
        return b
    else:
        return max(a, b)


def percent(num, denom):
    return (100 * (num / float(denom))) if denom else 0


def percent_str(num, denom):
    return str(percent) + '%'


def semicolon_str_as_list(s):
    """
    see utils.tests.MiscTests.test_semicolon_str_as_list().
    """
    if not s:
        return []
    return [x.strip() for x in s.split(';')
            if len(x.strip()) > 0]


def trunc(s, n):
    """
    Truncate a string to N characters, appending '...' if truncated.

      trunc('1234567890', 10) -> '1234567890'
      trunc('12345678901', 10) -> '1234567890...'
    """
    if not s:
        return s
    return s[:n] + '...' if len(s) > n else s


def as_dict(d):
    """
    Serialize a Model as a dictionary, and remove the
    special '_state' key (which isn't JSON-serializable).

    N.B. Doesn't deal with non-JSON-serialiable
    datetimes... can't remember what we did with these in
    the past. Maybe dt_str()? UPDATE: see utils.dt.serialize_datetimes.
    """
    if isinstance(d, models.Model):
        d = d.__dict__.copy()
        # Remove the _state element from d (Model.__dict__ now returns _state
        # along with all of their fields as of Django 1.2)
        del(d['_state'])
    return d


def printdict(d):
    d = as_dict(d)
    print '\n'.join(['%s: %s' % (k, d[k]) for k in sorted(d.keys())])


# this is useful if you're testing in the shell, and just
# want a Request object to play with. but it doesn't have
# all the real stuff that a Request object should have
class FakeRequest:
    def __init__(self):
        self.user = User.objects.get(pk=1)
        self.method = 'GET'


def urlencode_none(d, *args, **kwargs):
    """
    Like URLLIB.URLENCODE, except that this doesn't encode
    keys whose values are None.

    urllib.urlencode({'a': None}) -> 'a=None'

    D must be a DICT, i.e. doesn't support the 2-tuple
    version of URLENCODE.

    The *args and **kwargs are just there to pass DOSEQ along.
    """
    for k, v in d.items():
        if v is None:
            del d[k]
    return urllib.urlencode(d, *args, **kwargs)


def unique(items):
    """
    Returns KEEP, a list based on ITEMS, but with duplicates
    removed (preserving order, based on first new example).

    http://stackoverflow.com/questions/89178/in-python-what-is-the-fastest-algorithm-for-removing-duplicates-from-a-list-so-t

    unique([1, 1, 2, 'a', 'a', 3]) -> [1, 2, 'a', 3]
    """
    found = set([])
    keep = []
    for item in items:
        if item not in found:
            found.add(item)
            keep.append(item)
    return keep


def isint(f, tol=.00000001):
    """
    Takes in a float F, and checks that it's within TOL of floor(f).
    """
    # we're casting to float before the comparison with TOL
    # so that decimal Fs work
    return abs(float(f) - int(f)) <= .00000001


def isnum(n):
    try:
        float(n)
        return True
    except:
        return False


def get_object_or_404(*args, **kwargs):
    """
    Runs normally in production mode. But in DEBUG mode, it
    pauses instead of raising an Http404 exception.
    """
    if sett.DEBUG:
        # debug mode
        try:
            return django.shortcuts.get_object_or_404(*args, **kwargs)
        except Http404:
            keyboard()
    else:
        # production mode
        return django.shortcuts.get_object_or_404(*args, **kwargs)


def index_safe(lst, itm):
    """
    Returns LST.index(ITM), but returns None if not
    found, rather than an exception.
    """
    try:
        return lst.index(itm)
    except ValueError:
        return None


def strip_safe(x):
    """
    Runs x.strip(), or does nothing.
    """
    try:
        return x.strip()
    except AttributeError:
        return x


def split_safe(x, *args, **kwargs):
    """
    See strip_safe().
    """
    try:
        return x.split(*args, **kwargs)
    except AttributeError:
        return x


def whittle_dict(d, keys):
    """
    Returns D2, containing just the KEYS from dictionary D,
    e.g.

    whittle_dict({'a': 100, 'b': 200}, ['a']) -> {'a': 100}

    Will raise an exception if any of KEYS aren't keys in D.

    xxx - maybe this should instead do a copy, and delete any not needed???
    """
    d2 = {}
    for k in keys:
        d2[k] = d[k]
    return d2


def xlrd_float_to_str(x):
    """
    When importing a cell with a float in it, XLRD (or
    perhaps Excel) represents it as a float, e.g. a cell
    with 1000 will appear as 1000.0. This is annoying if you
    want to keep everything as strings.

    This function checks whether X can be cast down to an
     int, and if so, then to a string.
    """
    try:
        y = int(x)
        return str(y)
    except (ValueError, TypeError):
        # ValueError for ints, TypeError for None
        return x


def flatten(lol):
    """
    See http://stackoverflow.com/questions/406121/flattening-a-shallow-list-in-python

    e.g. [['image00', 'image01'], ['image10'], []] -> ['image00', 'image01', 'image10']
    """
    import itertools
    chain = list(itertools.chain(*lol))
    return chain


def prepend_keys_with(d, s):
    """
    Prepends all the keys in dictionary D with S, e.g.

    {'blah': 100} -> {'fooblah': 100} (where S == 'foo')

    Undefined if any of D's keys aren't strings.
    """
    d2 = {}
    for key in d.keys():
        d2[s + key] = d[key]
    return d2


def remove_underscore(s):
    """
    Get rid of underscore from S if it starts with one.
    """
    return s[1:] if s.startswith('_') else s


def add_underscore(s):
    """
    Makes sure S begins with an underscore.
    """
    return s if s.startswith('_') else u'_%s' % s


def remove_contents_of_parens(s):
    # remove contents of parentheses (check for this before removing punctuation!)
    # e.g.
    #   'abcdef (blah)' -> 'abcdef '
    #   'abcdef' -> 'abcdef'
    #
    # the [^\)] is to avoid it being greedy
    return re.sub('\([^\)]*\)', u'', s)


def sanitize_answer(s, ignore_punctuation):
    # make sure to return empty string as unicode
    if s == '':
        return u''
    if not s:
        return s

    if not isinstance(s, unicode):
        s = unicode(s)

    s = remove_contents_of_parens(s)

    if ignore_punctuation:
        # remove all punctuation (based on Friedl)
        s = re.sub('[%s]' % """!"#\$%&'\(\)\*\+,-\./:;<=>\?@\[\\]\^_`\{\|}~""", '', s)

    # replace all whitespace with a standard space. N.B. this appears to affect punctuation too
    s = re.sub('[ \t\r\n]+', u' ', s)
    # get rid of underscores (e.g. at the beginning
    # of some alternative definitions). whitespace
    # will be dealt with below
    s = remove_underscore(s)
    # stripping whitespace should have already
    # happened, but just to be sure. N.B. strip
    # should come after multi->single whitespace
    s = s.lower().strip()
    # Make sure that both answer and correct_answer are unicode, just in
    # case. The Levenshtein distance will raise an exception if one is a
    # str and the other unicode.
    s = unicode(s)
    return s


def reverse_dict(d):
    """
    Returns a dictionary with values as keys and vice versa.

    Will fail if the values aren't unique or aren't
    hashable.
    """
    vals = d.values()
    # confirm that all the values are unique
    assert len(vals) == len(set(vals))
    d2 = {}
    for k, v in d.items():
        d2[v] = k
    return d2


def remove_surrounding_quotes(s):
    """
    e.g. '"x"' -> '"x"'
    """
    if isinstance(s, (str, unicode)):
        if s.startswith('"') and s.endswith('"'):
            s = s[1:-1]
        elif s.startswith("'") and s.endswith("'"):
            s = s[1:-1]
    return s


def isiterable(x):
    """
    from http://stackoverflow.com/questions/1952464/in-python-how-do-i-determine-if-a-variable-is-iterable
    """
    import collections
    return isinstance(x, collections.Iterable)


def generate_mckey(prefix, d):
    """
    Should generate a legal, human-readable, unique and
    predictable string Memcached key from dictionary
    D. N.B. we're using 'mckey' to distinguish Memcached
    'keys' from dictionary 'keys'.

    Designed to be called at the top of your function with
    locals(), so it ignores any REQUEST and SELF keys - but
    you can always add {'user': request.user} if needed.

    Notes:

    - Prepends PREFIX + '__' to the MCKEY generated from D.

    - For dictionaries, concatenates the keys+values, sorted
      by key.

    - Converts lists and querysets to lists of IDs, hashing
      the result if too long.

    - Hashes the MCKEY if it's non-ascii or too long. Removes spaces etc.

    Keys are separated from their value by '::', and the
    key/value pairs are separated from one another by '__'.

    e.g.

       {'a': 100, 'b': 'blah'} -> u'a::100__b::blah'

    xxx - should be moved to utils.caching, along with Evan's cmcd
    """
    def sorted_dict_by_keys(d):
        """
        Returns a SortedDict, with the keys sorted alphabetically.

        This might not be necessary, since I think the order
        of a python dict's keys() is deterministic, but by
        sorting by dictionary keys, it's easier to know in
        advance what the generated MCKEY should look like.
        The idea is to ensure that no matter how D was
        created, you'll know what the key should be.
        """
        sorted_d = SortedDict()
        for k in sorted(d.keys()):
            sorted_d[k] = d[k]
        return sorted_d

    def as_str_or_hash(s):
        """
        Tries to convert S to a STR. If it doesn't work,
        just return the hash.
        """
        try:
            s = str(s)
        except UnicodeEncodeError:
            s = str(hash(s))
        return s

    def hash_if_too_long(s):
        """
        Return the HASH of S rather than S if it's too long
        (since the hash is only 10 characters).

        We call this on each component and then once more at
        the end because we want to keep the overall result
        as human-readable as possible, while still being
        unique.
        """
        if len(s) > MAX_MEMCACHED_KEY_LEN:
            s = str(hash(s))
        return s

    def iterable_to_string(seq):
        """
        If the items in SEQ are Django Models,
        store a comma-separated list of ids.

        Otherwise, just join the items in SEQ.

        e.g. [Thing.objects.get(id=1), Thing.objects.get(id=2)] -> 'Thing:1,2'
        """
        if not seq:
            return ''
        if isinstance(seq, QuerySet) or isinstance(seq[0], models.Model):
            model_prefix = seq[0]._meta.object_name + ':'
            pieces = [str(x.pk) for x in seq]
        else:
            pieces = [as_str_or_hash(x) for x in seq]
            model_prefix = ''
        s = model_prefix + ','.join(pieces)
        s = hash_if_too_long(s)
        return s

    def sanitize_val(v):
        """
        If V is an iterable, turn it into a comma-separated
        string (of IDs, if Models).

        Even though (empirically) it appears that Django's
        cache.set and cache.get use Memcached's binary
        protocol (so they can deal with non-ascii keys), it
        seems safer to require the key to be ascii.
        """
        if isinstance(v, str):
            pass
        elif isinstance(v, unicode):
            v = as_str_or_hash(v)
        elif hasattr(v, 'pk'):
            # for instances, i decided not to separate the
            # modelname from the id with a colon to
            # distinguish them from querysets
            v = v._meta.object_name + str(v.pk)
        elif isinstance(v, dict):
            # we might decide that even if we *can* deal
            # with dicts like this, it's too crazy to be worth it...
            v = generate_mckey('', v)
        elif isiterable(v):
            v = iterable_to_string(v)
        else:
            v = as_str_or_hash(v)
        v = v.strip()
        return hash_if_too_long(v)

    # 250 bytes, minus global KEY_PREFIX, plus leave extra room in case
    MAX_MEMCACHED_KEY_LEN = 200

    prefix = as_str_or_hash(prefix).upper()

    assert isinstance(d, dict)
    # ignore REQUEST and SELF, so you can easily pass in locals() for D
    if 'request' in d:
        del d['request']
    if 'self' in d:
        del d['self']
    d = sorted_dict_by_keys(d)

    # require everything to be a nice ascii string
    pieces = '__'.join(['%s::%s' % (sanitize_val(k), sanitize_val(v),)
                       for k, v in d.items()])

    prefix_pieces = prefix + '__' + pieces
    # replace all whitespace with underscores
    prefix_pieces = re.sub('[ \t\r\n]+', u'_', prefix_pieces)
    # not too long
    prefix_pieces = hash_if_too_long(prefix_pieces)
    # make sure it's ascii-friendly
    prefix_pieces = str(prefix_pieces)
    return prefix_pieces


def cmcd(prefix=None, arg_names=(), expiry=None):
    """Caches the return value of func based on the cache key generated by
    generate_mckey. The prefix argument to the `generate_mckey` is
    determined from the module and the name of the function if `prefix` is
    `None`. `arg_names` should be a sequence of strings that will be
    pulled from the kwargs dict and passed to `generate_mckey` to generate
    a key.

    Unfortunately we don't have access to the same locals() as the
    function itself, so the functions we're wrapping with this need to
    take keyword arguments, and the arguments we're generating the cache
    from must be specified.

    NOTE: prefix must be defined in settings.CACHE_EXPIRY, OR set expiry=EXPIRY_TIME, e.g.

    See utils.tests for usage.
    """

    def dec(func, prefix=prefix, arg_names=arg_names, expiry=expiry):
        if expiry is None:
            if prefix == None:
                prefix = ".".join((func.__module__, func.__name__))

            prefix = prefix.upper()
            if prefix not in sett.CACHE_EXPIRY:
                raise Exception("Prefix %s must be defined in settings.CACHE_EXPIRY if expiry is not specified" % prefix)

            expiry = sett.CACHE_EXPIRY[prefix]

        fspec = inspect.getargspec(func)
        pos_args = fspec.args
        defaults = fspec.defaults
        defaults = defaults if defaults else ()

        if pos_args or defaults:
            if not arg_names:
                raise Exception("arg_names must be specified for functions that take arguments.")

            default_args = dict((k, v) for k, v in zip(reversed(pos_args), reversed(defaults)))
            noargs = False
        else:
            noargs = True

        def f(*args, **kwargs):
            if not noargs:
                all_args = dict(default_args)
                all_args.update(dict((n, v) for n, v in zip(pos_args, args)))
                all_args.update(kwargs)
                d = dict((k, all_args.get(k, None)) for k in arg_names)
            else:
                all_args = {}
                d = {}

            mckey = generate_mckey(prefix, d)
            cached = cache.get(mckey)

            if cached:
                return cached

            val = func(*args, **kwargs)

            cache.set(mckey, val, expiry)

            return val

        return update_wrapper(f, func)

    return dec

