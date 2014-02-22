from django.db import models
from django.db.models.query import QuerySet
from django.shortcuts import _get_queryset

"""
This adds two main pieces of functionality:

- SoftDeletable is an abstract class that defines managers for
  objects, active and inactive, so that you can easily soft-delete an
  object by setting Model.status to model.INACTIVE_STATUS.
  
- If a model uses the custom QuerySetManager defined here, then you 
  can define your own chainable filtering methods (if you place them 
  in an internal "QuerySet" class).
"""

class QuerySetManager(models.Manager):
    """
    We got this from a django snippet by Simon Willison
    http://www.djangosnippets.org/snippets/734/
    http://stackoverflow.com/questions/809210/django-manager-chaining
    """
    def get_query_set(self):
        # any model that uses this manager needs to define an 
        # internal 'QuerySet' class
        return self.model.QuerySet(self.model)
        
    def __getattr__(self, name):
        # we need this so that we can call functions 
        # (e.g. get_or_create) that are part of the Manager rather 
        # than the QuerySet. otherwise, you need to precede your 
        # custom chainable functions with .all()
        #
        # however, if you don't have the name.startswith check, then you'll
        # end up seeing this (apparently) innocuous warning:
        # Exception RuntimeError: 'maximum recursion depth exceeded in __subclasscheck__'
        # http://bugs.python.org/issue5508
        if name.startswith('__'):
            return super(QuerySetManager, self).__getattr__(name)
        else:
            return getattr(self.get_query_set(), name)
        
    
class ActiveManager(QuerySetManager):
    """
    Thing.active.all() returns just those Things with
    STATUS==ACTIVE_STATUS.

    Update: We're excluding INACTIVE_STATUS rather than filtering
    for ACTIVE_STATUS because we're hoping that the index
    will work better if it only matches a small proportion
    of rows.
    """
    def get_query_set(self):
        return super(ActiveManager, self).get_query_set().exclude(
            status=self.model.INACTIVE_STATUS)


class InactiveManager(QuerySetManager):
    """
    Thing.inactive.all() returns just those Things with
    STATUS==INACTIVE_STATUS.
    """
    def get_query_set(self):
        return super(InactiveManager, self).get_query_set().filter(
            status=self.model.INACTIVE_STATUS)

# class RememberingQuerySet(QuerySet):
#     """
#     Remembers objects fetched in a static dict.
#     Caches only on this thread - minimal interference.
#     Adapted from https://github.com/mmalone/django-caching/tree/master/app
#     """
#     cache_dict = {}

#     def iterator(self):
#         superiter = super(RememberingQuerySet, self).iterator()
#         while True:
#             obj = superiter.next()
#             self.cache_dict[obj.pk] = obj
#             yield obj

#     def get(self, *args, **kwargs):
#         """
#         Checks the cache to see if there's a cached entry for this pk. If not, fetches
#         using super then stores the result in cache.

#         Most of the logic here was gathered from a careful reading of
#         ``django.db.models.sql.query.add_filter``
#         """
#         if self.query.where:
#             # If there is any other ``where`` filter on this QuerySet just call
#             # super. There will be a where clause if this QuerySet has already
#             # been filtered/cloned.
#             return super(RememberingQuerySet, self).get(*args, **kwargs)

#         # Punt on anything more complicated than get by pk/id only...
#         if len(kwargs) == 1:
#             k = kwargs.keys()[0]
#             if k in ('pk', 'pk__exact', 'id', 'id__exact'):
#                 # Get from local static dict
#                 obj = self.cache_dict.get(kwargs.values()[0], None)
#                 if obj is not None:
#                     obj.from_cache = True
#                     return obj

#         # Calls self.iterator to fetch objects, storing object in cache.
#         return super(RememberingQuerySet, self).get(*args, **kwargs)


# class DictRememberingModel:
#     class Meta:
#         abstract = True

#     class ModelCache:
#         dicts = {}

#     @classmethod
#     def get_by_id(cls, pk):
#         return cls.get_by_ids([pk])[0]

#     @classmethod
#     def get_by_ids(cls, ids):
#         fetch = []
#         ret_list = []
#         for i in ids:
#             mod = cls.ModelCache.dicts.get(i)
#             if i is not None:
#                 ret_list.append(mod)
#             else:
#                 fetch.append(i)

#         # Fetch only those that we didn't have cached.
#         if len(fetch) > 0:
#             missing_models = cls.objects.filter(id__in=ids)
#             for m in missing_models:
#                 cls.ModelCache.dicts[m.id] = m
#                 ret_list.append(m)
#         return ret_list


class SoftDeletableQuerySet(QuerySet):
    """
    Inherit from this in your SoftDeletable model's nested
    QuerySet if you want to pickle your SoftDeletable
    Model's QuerySets.

    The easiest way is to just have the main Model class
    inherit from SoftDeletable. But, if it's just a normal
    Model, then do this (see e.g. MemUser):

        from utils.models import QuerySetManager, SoftDeletableQuerySet
        class Blah(models.Model):
            objects = QuerySetManager()
            class QuerySet(SoftDeletableQuerySet):
                ...
    """
    def __getstate__(self):
        """
        Allows the QuerySet to be pickled.

        Based on django's QuerySet in query.py.
        """
        # Force the cache to be fully populated.
        len(self)

        obj_dict = self.__dict__.copy()
        obj_dict['_iter'] = None
        return obj_dict


class SoftDeletable(models.Model):
    """
    Adds fields for status so that you can can elect to
    ignore some objects easily (i.e. soft delete them).

    Unfortunately, you still have to create the OBJECTS,
    ACTIVE and INACTIVE managers.

    You'll probably want to define a nested QuerySet class
    (that inherits from SoftDeletableQuerySet) in your new
    SoftDeletable model so that you can define your own
    QuerySet methods.
    """

    ACTIVE_STATUS = 1
    INACTIVE_STATUS = 0
    STATUS_CHOICES = (
        (ACTIVE_STATUS, 'Active'),
        (INACTIVE_STATUS, 'Inactive'),
        )
    status = models.IntegerField(choices=STATUS_CHOICES,
                                 default=ACTIVE_STATUS,
                                 help_text="Only ACTIVE objects will be used")

    objects = QuerySetManager()
    active = ActiveManager()
    inactive = InactiveManager()

    class Meta:
        abstract = True


def as_objects(model, objs, uniquify=True):
    """
    OBJS is one or more Objects or object slugs of type
    MODEL. Returns a *new* list of Objects. The Objects for
    the given slugs must already exist, else raises an
    Exeption.

    Update: No longer modifies in place.

    e.g.

      things = as_objects(Thing, things)

    If UNIQUIFY, will throw away any duplicates. Now preserves order.
    """
    if objs is None:
        return None

    # If we were not passed a list or queryset, we need to make the objs
    # variable iterable so we just put it in a list
    #
    # xxx - would it be better to just return objs if it's a
    # QuerySet??? maybe with a .distinct()???
    if not isinstance(objs, (list, QuerySet)):
        objs = [objs]
    
    # list with the new version of OBJS
    new_objs = []
    # keep track of things, so that we can uniquify
    objs_so_far = set()
    # Get an obj object for each item in the list (because some or all
    # of them might just be slugs)
    for obj in objs:
        if isinstance(obj, (str, unicode)):
            obj = model.objects.get(slug=obj)
        elif isinstance(obj, int):
            obj = model.objects.get(id=obj)
        else:
            pass # just keep the original OBJ
        if uniquify:
            if obj in objs_so_far:
                continue
            else:
                objs_so_far.add(obj)
        new_objs.append(obj)
            
    return new_objs


def get_first(model, *args, **kwargs):
    """
    e.g. Thing.get_first(word='word', defn='defn')

    Works like GET, but won't return an exception
    if multiple objects are returned - it'll just return the
    first.

    Returns object.

    Will raise the same exception GET would have if there
    are no objects.
    """
    queryset = _get_queryset(model)
    try:
        return queryset.filter(*args, **kwargs)[0]
    except IndexError:
        raise queryset.model.DoesNotExist
    except:
        raise
    

def get_first_or_None(model, *args, **kwargs):
    """
    see GET_FIRST
    """
    queryset = _get_queryset(model)
    try:
        return queryset.filter(*args, **kwargs)[0]
    except IndexError:
        return None
    except:
        raise
    

def fresh_dict(m, ignore_underscore_fields=True):
    """
    Returns a dict representation of the current (unsaved)
    state of Model M.

    Like django's built-in Model.__dict__, except that seems
    to use the stored (i.e. old) rather than new/unsaved
    values. In other words, if you change some of M's values
    but haven't yet saved them, FRESH_DICT will return the
    unsaved versions, whereas django's __dict__ will return
    the saved values.

    If IGNORE_UNDERSCORE_FIELDS, throws out fields that
    start with an underscore.
    """
    d = {}
    for fieldn in [f.name for f in m._meta.fields]:
        if ignore_underscore_fields and fieldn.startswith('_'):
            continue
        d[fieldn] = getattr(m, fieldn)
    return d
