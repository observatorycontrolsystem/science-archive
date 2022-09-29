from django.contrib import admin
from archive.frames.models import Frame, Version, Headers
from archive.frames.forms import FrameForm
from archive.frames.pagination import LimitedLimitOffsetPagination

class VersionInlineAdmin(admin.StackedInline):
    model = Version


class HeadersInlineAdmin(admin.StackedInline):
    model = Headers


class FrameAdmin(admin.ModelAdmin):
    show_full_result_count = False
    model = Frame
    inlines = [
        HeadersInlineAdmin,
        VersionInlineAdmin
    ]
    form = FrameForm
    paginator = LimitedLimitOffsetPagination

admin.site.register(Frame, FrameAdmin)
