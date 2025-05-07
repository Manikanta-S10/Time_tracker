from django.db import models
from datetime import timedelta

# Create your models here.

class Users(models.Model):
    name = models.CharField(max_length=30)
    email = models.EmailField()
    password = models.CharField(max_length=20)

    def __str__(self):
        return self.name

class ActivityLog(models.Model):
    user = models.ForeignKey(Users, on_delete=models.CASCADE)
    start_time = models.DateTimeField()
    stop_time = models.DateTimeField()
    date = models.DateField()
    cyvl_duration = models.DurationField(default=timedelta())
    youtube_duration = models.DurationField(default=timedelta())
    other_related_work_duration = models.DurationField(default=timedelta())
    working_hours = models.DurationField(default=timedelta())  # 👈 NEW FIELD

    def __str__(self):
        return f"{self.user.name} - {self.date}"






