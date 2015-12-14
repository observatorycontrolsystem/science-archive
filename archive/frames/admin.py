from django.contrib import admin
from archive.frames.models import Frame, Version, Headers


class VersionInlineAdmin(admin.StackedInline):
    model = Version


class HeadersInlineAdmin(admin.StackedInline):
    model = Headers


class FrameAdmin(admin.ModelAdmin):
    model = Frame
    inlines = [
        HeadersInlineAdmin,
        VersionInlineAdmin
    ]

admin.site.register(Frame, FrameAdmin)
