from django.shortcuts import render, redirect
from .models import *
import requests
from datetime import datetime, timedelta, timezone
from django.http import JsonResponse
from django.views.decorators.csrf import csrf_exempt
from django.utils.timezone import make_aware, get_current_timezone
import re
from django.contrib.admin.views.decorators import staff_member_required
from django.utils.timezone import get_current_timezone
from django.db.models import Q
from django.contrib.auth import logout

# Create your views here.
def home(request):
    user_id = request.session.get('user_id')
    if user_id:
        return redirect('tracking')  # already logged in
    return redirect('login')  # not logged in


def signup(request):
    if request.method == 'POST':
        username = request.POST['name']
        email = request.POST['email']
        password = request.POST['password']

        # Check if user already exists
        if Users.objects.filter(name=username).exists():
            return render(request, 'signup.html', {'error': 'Already user existed'})
        
        # Check if email already exists
        if Users.objects.filter(email=email).exists():
            return render(request, 'signup.html', {'error': 'Already email existed'})
        
        #creating one user in database 
        Users.objects.create(name=username, email=email, password=password)
        return redirect('login')
    
    return render(request, 'signup.html')

def login(request):
    if request.method == 'POST':
        email = request.POST['email']
        password = request.POST['password']

        user = Users.objects.filter(email=email, password=password).first()

        if user:
            request.session['user_id'] = user.id 
            return redirect('tracking')

    return render(request, 'login.html')

def tracking_page(request):
    user_id = request.session.get('user_id')
    if user_id:
        user = Users.objects.get(id=user_id)
        return render(request, 'tracking.html', {'userName':user.name})
    

def parse_duration(duration_str):
    match = re.match(r'(?P<h>\d+) hours (?P<m>\d+) minutes (?P<s>\d+) seconds', duration_str)
    if not match:
        return timedelta()
    print("parse_duration timedelta: ", timedelta)
    return timedelta(
        hours=int(match.group('h')),
        minutes=int(match.group('m')),
        seconds=int(match.group('s'))
    )

def format_duration(td):
    """Correctly format timedelta to h m s."""
    total_seconds = int(td.total_seconds())
    hours = total_seconds // 3600
    minutes = (total_seconds % 3600) // 60  
    seconds = total_seconds % 60
    return f"{hours}h {minutes}m {seconds}s"


@csrf_exempt
def submit_timer_form(request):
    if request.method == 'POST':
        start_time_str = request.POST.get('start_time')
        end_time_str = request.POST.get('end_time')

        print("Raw start_time_str:", repr(start_time_str))
        print("Raw end_time_str:", repr(end_time_str))

        if not start_time_str or not end_time_str:
            return JsonResponse({'error': 'Start or End time missing'}, status=400)

        try:
            # Strip and replace Z with +00:00 for UTC
            start_time_str = start_time_str.strip().replace('Z', '+00:00')
            end_time_str = end_time_str.strip().replace('Z', '+00:00')

            print("Cleaned start_time_str:", start_time_str)
            print("Cleaned end_time_str:", end_time_str)

            start_time = datetime.fromisoformat(start_time_str)
            end_time = datetime.fromisoformat(end_time_str)

            # ✅ Apply make_aware only if it's naive (i.e., no timezone info)
            if start_time.tzinfo is None:
                start_time = make_aware(start_time)
            if end_time.tzinfo is None:
                end_time = make_aware(end_time)

            # ✅ Convert to your timezone (e.g. Asia/Kolkata)
            local_tz = get_current_timezone()
            start_time = start_time.astimezone(local_tz)
            end_time = end_time.astimezone(local_tz)
            working_hours = end_time - start_time

            print("Final start_time:", start_time)
            print("Final end_time:", end_time)

        except Exception as e:
            print("Datetime parse error:", e)
            return JsonResponse({'error': 'Invalid datetime format'}, status=400)

        # You can now safely use start_time and end_time
        durations = get_activitywatch_durations(start_time, end_time)

        # Handle errors from the durations dict
        if 'error' in durations:
            return JsonResponse({'error': durations['error']}, status=500)
        
        # Save to DB
        user_id = request.session.get('user_id')
        user = Users.objects.get(id=user_id)
        activity_date = start_time.date()

        # Convert durations to timedelta
        cyvl_td = parse_duration(durations['cyvl'])
        youtube_td = parse_duration(durations['youtube'])
        other_td = parse_duration(durations['other'])

        print(f"cyvl_td: {cyvl_td}")
        print(f"youtube_td: {youtube_td}")
        print(f"other_td: {other_td}")

        print(f'durations: {durations}')

        # Check if log already exists
        existing_log = ActivityLog.objects.filter(user=user, date=activity_date).first()

        if existing_log:
            print("🔁 Updating existing log for the day.")
            existing_log.start_time = min(existing_log.start_time, start_time)
            existing_log.stop_time = max(existing_log.stop_time, end_time)
            existing_log.working_hours = existing_log.stop_time - existing_log.start_time
            existing_log.cyvl_duration += cyvl_td
            existing_log.youtube_duration += youtube_td
            existing_log.other_related_work_duration += other_td
            existing_log.save()
        else:
            print("🆕 Creating new log for the day.")
            ActivityLog.objects.create(
                user=user,
                start_time=start_time,
                stop_time=end_time,
                date=activity_date,
                cyvl_duration=cyvl_td,
                youtube_duration=youtube_td,
                other_related_work_duration=other_td,
                working_hours=working_hours  # 👈 Save total time
            )

        return render(request, 'result.html', {
            'start': start_time,
            'end': end_time,
            'durations': durations
        })
    
def get_activitywatch_durations(start_time, end_time):
    print("🔍 Getting activity durations")

    try:
        buckets_response = requests.get("http://localhost:5600/api/0/buckets/")
        buckets_response.raise_for_status()
        buckets = buckets_response.json()
        print("✅ Buckets fetched:", list(buckets.keys()))
    except Exception as e:
        return {'error': f'Failed to fetch buckets: {str(e)}'}

    # Collect all relevant window tracker buckets
    window_buckets = [
        b_id for b_id in buckets
        if b_id.startswith('aw-watcher-window')
    ]

    if not window_buckets:
        return {'error': 'No aw-watcher-window buckets found'}

    durations = {
        'cyvl': timedelta(),
        'youtube': timedelta(),
        'other': timedelta()
    }

    # Format time in UTC ISO format for ActivityWatch API
    start_iso = start_time.astimezone(timezone.utc).isoformat()
    end_iso = end_time.astimezone(timezone.utc).isoformat()

    print(f"⏱ Time range: {start_iso} → {end_iso}")
    print(f"📦 Buckets to check: {window_buckets}")

    for bucket_id in window_buckets:
        url = f"http://localhost:5600/api/0/buckets/{bucket_id}/events"
        params = {'start': start_iso, 'end': end_iso}

        try:
            res = requests.get(url, params=params)
            res.raise_for_status()
            events = res.json()
            print(f"📊 Events from {bucket_id}: {len(events)}")
        except Exception as e:
            print(f"❌ Failed to get events from {bucket_id}: {e}")
            continue

        for event in events:
            data = event.get('data', {})
            title = data.get('title', '').lower()
            app = data.get('app', '').lower()
            event_start = datetime.fromisoformat(event['timestamp']).astimezone(timezone.utc)
            event_end = event_start + timedelta(seconds=event.get('duration', 0))

            # Only count events that overlap with session range
            if not (event_end > start_time and event_start < end_time):
                continue  # skip unrelated event

            duration = min(end_time, event_end) - max(start_time, event_start)

            if 'cyvl' in title and any(browser in app for browser in ['chrome', 'firefox', 'edge']):
                durations['cyvl'] += duration
            elif 'youtube' in title:
                durations['youtube'] += duration
            else:
                durations['other'] += duration

    print("✅ Final durations:", durations)

    def format_duration(td):
        total_seconds = int(td.total_seconds())
        hours = total_seconds // 3600
        minutes = (total_seconds % 3600) // 60
        seconds = total_seconds % 60
        return f"{hours} hours {minutes} minutes {seconds} seconds"

    formatted = {k: format_duration(v) for k, v in durations.items()}
    print("Formatted durations:", formatted)
    return formatted

def activity_dashboard(request):
    user_id = request.session.get('user_id')
    current_user = Users.objects.get(id=user_id)

    is_admin = current_user.name.lower() == "admin"
    all_users = Users.objects.all() if is_admin else None

    selected_user_id = request.GET.get('user_id')
    start_date_str = request.GET.get('start_date')
    end_date_str = request.GET.get('end_date')

    logs = ActivityLog.objects.all() if is_admin else ActivityLog.objects.filter(user=current_user)

    # Filter by user
    if is_admin:
        if selected_user_id and selected_user_id != 'all':
            try:
                logs = logs.filter(user_id=int(selected_user_id))
            except ValueError:
                logs = ActivityLog.objects.none()

    # Filter by date range
    if start_date_str:
        try:
            start_date = datetime.strptime(start_date_str, '%Y-%m-%d').date()
            logs = logs.filter(date__gte=start_date)
        except ValueError:
            start_date = None
    else:
        start_date = None

    if end_date_str:
        try:
            end_date = datetime.strptime(end_date_str, '%Y-%m-%d').date()
            logs = logs.filter(date__lte=end_date)
        except ValueError:
            end_date = None
    else:
        end_date = None

    logs = logs.order_by('-date')
    print("logs: ",logs)

    for log in logs:
    # Keep original timedelta for calculations
        print("log: ", log)
        cyvl = log.cyvl_duration
        print("cyvl: ",cyvl)

        # Format for display
        log.fmt_cyvl = format_duration(cyvl)
        log.fmt_youtube = format_duration(log.youtube_duration)
        log.fmt_other = format_duration(log.other_related_work_duration)
        log.fmt_working = format_duration(log.working_hours)
        print(f"formated cyvl: {log.fmt_cyvl}")
        print(f"formated youtube: {log.fmt_youtube}")
        print(f"formated other: {log.fmt_other}")
        print(f"formated working: {log.fmt_working}")

        # ✅ Correctly compute remaining from timedelta
        eight_hours = timedelta(hours=8)
        print(f"eight hours: {eight_hours}")
        if cyvl < eight_hours:
            remaining = eight_hours - cyvl
            print(f"remaining hours {remaining}")
            log.remaining_cyvl = format_duration(remaining)
            print(f"remaining fmt_hours: {log.remaining_cyvl}")
            log.satisfied = False
        else:
            log.remaining_cyvl = "-"
            log.satisfied = True

    return render(request, 'activity_dashboard.html', {
        'logs': logs,
        'is_admin': is_admin,
        'users': all_users,
        'selected_user_id': selected_user_id,
        'start_date': start_date_str,
        'end_date': end_date_str
    })

def logout_view(request):
    logout(request)
    return redirect('login')  