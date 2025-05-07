from django.contrib import admin
from .models import Users, ActivityLog

# Register your models here.
@admin.register(Users)
class UsersAdmin(admin.ModelAdmin):
    list_display = ['id', 'name', 'email', 'password']

@admin.register(ActivityLog)
class ActivityLogAdmin(admin.ModelAdmin):
    list_display = ['id', 'start_time', 'stop_time', 'date', 'cyvl_duration', 'youtube_duration', 'other_related_work_duration', 'user_id', 'working_hours']
    
