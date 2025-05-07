from django.urls import path
from . import views

urlpatterns = [
    path('', views.home, name='home'),
    path('signup/', views.signup, name='signup'),
    path('login/', views.login, name='login'),
    path('tracking/', views.tracking_page, name='tracking'),
    path('submit-timer/', views.submit_timer_form, name='submit_timer_form'),
    path('dashboard/', views.activity_dashboard, name='activity_dashboard'),
    path('logout/', views.logout_view, name='logout'),
]
