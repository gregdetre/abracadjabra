from django.contrib import admin
from models import Experiment, ExperimentUser

class ExperimentAdmin(admin.ModelAdmin):
    list_display = ('name', 'cre',)
    search_fields = ('name',)
    readonly_fields=('cre',)

class ExperimentUserAdmin(admin.ModelAdmin): 
    list_display = ('experiment', 'user', 'bucket', 'cre',)
    list_filter = ('experiment',)
    search_fields = ('experiment__name', 'user__username', 'bucket',)
    raw_id_fields = ('user',) # add 'experiment' if slow
    readonly_fields=('cre',)


admin.site.register(Experiment, ExperimentAdmin)
admin.site.register(ExperimentUser, ExperimentUserAdmin)

