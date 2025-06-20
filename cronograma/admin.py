# cronograma/admin.py
from django.contrib import admin
from .models import Schedule, Activity, ActivityConcept, CriticalPath, CriticalPathActivity

class ActivityConceptInline(admin.TabularInline):
    model = ActivityConcept
    extra = 1

class ActivityInline(admin.TabularInline):
    model = Activity
    extra = 1
    show_change_link = True

class CriticalPathActivityInline(admin.TabularInline):
    model = CriticalPathActivity
    extra = 1

@admin.register(Schedule)
class ScheduleAdmin(admin.ModelAdmin):
    list_display = ('id', 'name', 'construction', 'is_active', 'created_at')
    list_filter = ('is_active', 'created_at')
    search_fields = ('name', 'construction__name')
    inlines = [ActivityInline]

@admin.register(Activity)
class ActivityAdmin(admin.ModelAdmin):
    list_display = ('id', 'name', 'schedule', 'start_date', 'end_date', 'progress_percentage')
    list_filter = ('start_date', 'end_date', 'schedule')
    search_fields = ('name', 'description')
    inlines = [ActivityConceptInline]

@admin.register(CriticalPath)
class CriticalPathAdmin(admin.ModelAdmin):
    list_display = ('id', 'schedule', 'calculated_at')
    inlines = [CriticalPathActivityInline]

# Opcional: para ver detalles de relaciones
@admin.register(ActivityConcept)
class ActivityConceptAdmin(admin.ModelAdmin):
    list_display = ('id', 'activity', 'concept')
    list_filter = ('activity__schedule',)

@admin.register(CriticalPathActivity)
class CriticalPathActivityAdmin(admin.ModelAdmin):
    list_display = ('id', 'critical_path', 'activity', 'sequence_order')
    list_filter = ('critical_path__schedule',)
    ordering = ('sequence_order',)