from django.contrib import admin
from django.contrib.gis import admin as gis_admin
from django.db.models import F, OuterRef, Subquery
from django.urls import reverse
from django.utils.html import format_html
from django.utils import timezone
from django.utils.timesince import timesince

from . import models


@admin.register(models.LogicalDevice)
class LogicalDeviceAdmin(gis_admin.GISModelAdmin):
    search_fields = ('name', 'uid__exact')
    list_filter = ('last_seen',)
    date_hierarchy = 'last_seen'

    gis_widget_kwargs = {
        'attrs': {
            'default_lon': 133.7751,
            'default_lat': -25.2744,
            'default_zoom': 0,
        },
    }

    list_display = (
        'logical_uid_link',
        'name',
        'current_physical_uid_link',
        'current_physical_name',
        'last_seen_sort',
    )
    list_display_links = None

    def get_queryset(self, request):
        # Args: request (HttpRequest)
        # Returns: LogicalDevice queryset annotated with current mapping details.
        queryset = super().get_queryset(request)
        current_map = (
            models.PhysicalLogicalMap.objects
            .filter(
                logical_uid=OuterRef('pk'),
                is_active=True,
                active_range__contains=timezone.now(),
            )
            .order_by('-uid')
        )
        return queryset.annotate(
            _current_physical_uid=Subquery(current_map.values('physical_uid')[:1]),
            _current_physical_name=Subquery(current_map.values('physical_uid__name')[:1]),
        )

    @admin.display(description='UID', ordering='uid')
    def logical_uid_link(self, obj):
        # Args: obj (LogicalDevice)
        # Returns: HTML anchor linking to this logical device admin change page in a new tab.
        url = reverse('admin:mgmtapp_logicaldevice_change', args=[obj.uid])
        return format_html(
            '<a href="{}" target="_blank" rel="noopener noreferrer">{}</a>',
            url,
            obj.uid,
        )

    @admin.display(description='Current Physical UID', ordering='_current_physical_uid')
    def current_physical_uid_link(self, obj):
        # Args: obj (LogicalDevice)
        # Returns: HTML anchor linking to mapped physical device admin change page in a new tab, or '-'.
        if obj._current_physical_uid is None:
            return '-'
        url = reverse('admin:mgmtapp_physicaldevice_change', args=[obj._current_physical_uid])
        return format_html(
            '<a href="{}" target="_blank" rel="noopener noreferrer">{}</a>',
            url,
            obj._current_physical_uid,
        )

    @admin.display(description='Current Physical Name', ordering='_current_physical_name')
    def current_physical_name(self, obj):
        # Args: obj (LogicalDevice)
        # Returns: current mapped physical name or '-'.
        return obj._current_physical_name or '-'

    @admin.display(description='Last seen', ordering=F('last_seen').asc(nulls_first=True))
    def last_seen_sort(self, obj):
        # Args: obj (LogicalDevice)
        # Returns: human-readable elapsed time since last seen, or '-'.
        if obj.last_seen is None:
            return '-'
        return f'{timesince(obj.last_seen, timezone.now())} ago'


@admin.register(models.PhysicalDevice)
class PhysicalDeviceAdmin(gis_admin.GISModelAdmin):
    search_fields = ('name', 'uid__exact', 'source_name__source_name')
    list_filter = ('source_name', 'last_seen')
    date_hierarchy = 'last_seen'

    list_display = (
        'physical_uid_link',
        'name',
        'current_logical_uid_link',
        'current_logical_name',
        'last_seen_sort',
    )
    list_display_links = None

    gis_widget_kwargs = {
        'attrs': {
            'default_lon': 133.7751,
            'default_lat': -25.2744,
            'default_zoom': 0,
        },
    }

    def get_queryset(self, request):
        # Args: request (HttpRequest)
        # Returns: PhysicalDevice queryset annotated with current mapping details.
        queryset = super().get_queryset(request)
        current_map = (
            models.PhysicalLogicalMap.objects
            .filter(
                physical_uid=OuterRef('pk'),
                is_active=True,
                active_range__contains=timezone.now(),
            )
            .order_by('-uid')
        )
        return queryset.annotate(
            _current_logical_uid=Subquery(current_map.values('logical_uid')[:1]),
            _current_logical_name=Subquery(current_map.values('logical_uid__name')[:1]),
        )

    @admin.display(description='UID', ordering='uid')
    def physical_uid_link(self, obj):
        # Args: obj (PhysicalDevice)
        # Returns: HTML anchor linking to this physical device admin change page in a new tab.
        url = reverse('admin:mgmtapp_physicaldevice_change', args=[obj.uid])
        return format_html(
            '<a href="{}" target="_blank" rel="noopener noreferrer">{}</a>',
            url,
            obj.uid,
        )

    @admin.display(description='Current Logical UID', ordering='_current_logical_uid')
    def current_logical_uid_link(self, obj):
        # Args: obj (PhysicalDevice)
        # Returns: HTML anchor linking to mapped logical device admin change page in a new tab, or '-'.
        if obj._current_logical_uid is None:
            return '-'
        url = reverse('admin:mgmtapp_logicaldevice_change', args=[obj._current_logical_uid])
        return format_html(
            '<a href="{}" target="_blank" rel="noopener noreferrer">{}</a>',
            url,
            obj._current_logical_uid,
        )

    @admin.display(description='Current Logical Name', ordering='_current_logical_name')
    def current_logical_name(self, obj):
        # Args: obj (PhysicalDevice)
        # Returns: current mapped logical name or '-'.
        return obj._current_logical_name or '-'

    @admin.display(description='Last seen', ordering=F('last_seen').asc(nulls_first=True))
    def last_seen_sort(self, obj):
        # Args: obj (PhysicalDevice)
        # Returns: human-readable elapsed time since last seen, or '-'.
        if obj.last_seen is None:
            return '-'
        return f'{timesince(obj.last_seen, timezone.now())} ago'


@admin.register(models.PhysicalLogicalMap)
class PhysicalLogicalMapAdmin(admin.ModelAdmin):
    search_fields = (
        'logical_uid__name',
        'physical_uid__name',
        'logical_uid__uid__exact',
        'physical_uid__uid__exact',
    )
    list_filter = ('is_active', 'logical_uid', 'physical_uid')

    list_display = (
        'logical_uid_link',
        'logical_name',
        'physical_uid_link',
        'physical_name',
        'active_range',
        'is_active',
    )
    list_display_links = None

    def get_queryset(self, request):
        # Args: request (HttpRequest)
        # Returns: PhysicalLogicalMap queryset with related logical and physical devices selected.
        queryset = super().get_queryset(request)
        return queryset.select_related('logical_uid', 'physical_uid')

    @admin.display(description='Logical UID', ordering='logical_uid')
    def logical_uid_link(self, obj):
        # Args: obj (PhysicalLogicalMap)
        # Returns: HTML anchor linking to related logical device admin change page in a new tab.
        url = reverse('admin:mgmtapp_logicaldevice_change', args=[obj.logical_uid_id])
        return format_html(
            '<a href="{}" target="_blank" rel="noopener noreferrer">{}</a>',
            url,
            obj.logical_uid_id,
        )

    @admin.display(description='Logical Name', ordering='logical_uid__name')
    def logical_name(self, obj):
        # Args: obj (PhysicalLogicalMap)
        # Returns: related logical device name.
        return obj.logical_uid.name

    @admin.display(description='Physical UID', ordering='physical_uid')
    def physical_uid_link(self, obj):
        # Args: obj (PhysicalLogicalMap)
        # Returns: HTML anchor linking to related physical device admin change page in a new tab.
        url = reverse('admin:mgmtapp_physicaldevice_change', args=[obj.physical_uid_id])
        return format_html(
            '<a href="{}" target="_blank" rel="noopener noreferrer">{}</a>',
            url,
            obj.physical_uid_id,
        )

    @admin.display(description='Physical Name', ordering='physical_uid__name')
    def physical_name(self, obj):
        # Args: obj (PhysicalLogicalMap)
        # Returns: related physical device name.
        return obj.physical_uid.name


admin.site.register(models.DeviceBlob)
admin.site.register(models.DeviceNote)
admin.site.register(models.RawMessage)
admin.site.register(models.PhysicalTimeseries)
admin.site.register(models.LogicalTimeseries)
admin.site.register(models.Source)
admin.site.register(models.User)
