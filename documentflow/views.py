from django.shortcuts import render, redirect
import json
from django.contrib.auth.decorators import login_required
from django.utils import timezone
from django.db import models
from django.db.models import Min, OuterRef, Subquery, Count, Avg, F, ExpressionWrapper, DurationField
from django.db.models.functions import TruncMonth

from documentflow.models import Document, Approval, Notification

# ===== Страница входа =====
def login_page(request):
    """
    Просто HTML-страница входа.
    ЛОГИКИ АВТОРИЗАЦИИ ЗДЕСЬ НЕТ
    """
    if request.user.is_authenticated:
        return redirect('documentflow:dashboard')

    return render(request, 'main/login.html')


@login_required(login_url='/')
def password_change_page(request):
    return render(request, 'main/password_change.html', {
        'must_change_required': getattr(request.user, 'must_change_password', False)
    })


# ===== Рабочий кабинет =====
@login_required(login_url='/')
def dashboard(request):
    """
    Рабочий кабинет сотрудника
    """
    user = request.user
    today = timezone.localdate()

    min_pending_step = (
        Approval.objects.filter(
            document_id=OuterRef('document_id'),
            decision='pending',
        )
        .values('document_id')
        .annotate(min_step=Min('step'))
        .values('min_step')
    )

    pending_approvals = (
        Approval.objects
        .filter(approver=user, decision='pending', document__is_archived=False)
        .annotate(min_step=Subquery(min_pending_step))
        .filter(
            models.Q(document__action_type='acknowledge')
            | models.Q(document__approval_order='parallel')
            | models.Q(step=models.F('min_step'))
        )
    )

    # ===== Уведомления о сроках =====
    urgent_deadline = today + timezone.timedelta(days=3)
    for approval in pending_approvals.select_related('document'):
        doc = approval.document
        if not doc or not doc.deadline:
            continue
        if doc.deadline > urgent_deadline:
            continue
        if Notification.objects.filter(user=user, document=doc, notification_type='deadline').exists():
            continue
        Notification.objects.create(
            user=user,
            notification_type='deadline',
            title='Срок исполнения',
            text=f'{doc.registration_number} — срок до {doc.deadline.strftime("%d.%m.%Y")}',
            link=f'/documents/incoming/?open={doc.id}',
            document=doc
        )

    incoming_doc_ids = pending_approvals.values('document_id').distinct()
    incoming_count = incoming_doc_ids.count()
    incoming_urgent = pending_approvals.filter(document__priority='urgent').values('document_id').distinct().count()
    overdue_count = pending_approvals.filter(document__deadline__lt=today).values('document_id').distinct().count()
    urgent_deadline = today + timezone.timedelta(days=3)
    urgent_documents = (
        Document.objects
        .filter(id__in=incoming_doc_ids, deadline__isnull=False)
        .filter(models.Q(deadline__lt=today) | models.Q(deadline__lte=urgent_deadline))
        .order_by('deadline')[:5]
    )

    approval_count = (
        Document.objects
        .filter(author=user, is_archived=False)
        .exclude(status__is_final=True)
        .exclude(status__name__iexact='Черновик')
        .exclude(status__name__icontains='доработ')
        .exclude(status__name__icontains='возвращ')
        .count()
    )

    processed_today = Approval.objects.filter(
        approver=user,
        decided_at__date=today,
        decision__in=['approved', 'rejected', 'acknowledged', 'executed']
    ).count()

    week_labels = []
    weekly_stats = []
    for i in range(6, -1, -1):
        day = today - timezone.timedelta(days=i)
        week_labels.append(day.strftime('%d.%m'))
        weekly_stats.append(
            Approval.objects.filter(
                approver=user,
                decided_at__date=day,
                decision__in=['approved', 'rejected', 'acknowledged', 'executed']
            ).count()
        )

    notification_icon_map = {
        'new_document': 'inbox',
        'deadline': 'clock',
        'approval': 'check-circle',
        'assignment': 'tasks',
        'status_change': 'exchange-alt',
        'comment': 'comment',
        'system': 'info-circle',
    }
    recent_notifications = []
    for n in Notification.objects.filter(user=user).order_by('-created_at')[:5]:
        recent_notifications.append({
            'icon': notification_icon_map.get(n.notification_type, 'info-circle'),
            'message': f"{n.title}: {n.text}" if n.text else n.title,
            'created_at': n.created_at,
            'read': n.is_read,
        })

    return render(request, 'main/dashboard.html', {
        'incoming_count': incoming_count,
        'incoming_urgent': incoming_urgent,
        'approval_count': approval_count,
        'approval_overdue': overdue_count,
        'overdue_count': overdue_count,
        'processed_today': processed_today,
        'urgent_documents': urgent_documents,
        'weekly_stats': json.dumps(weekly_stats),
        'weekly_labels': json.dumps(week_labels),
        'recent_notifications': recent_notifications,
    })

@login_required
def sending_document_page(request):
    """HTML страница создания документа"""
    return render(request, 'main/sending_document.html')

@login_required
def incoming_documents_page(request):
    """HTML страница входящих документов"""
    return render(request, 'main/incoming_documents.html', {
        'page_title': 'Входящие документы',
        'page_subtitle': 'Документы на согласование, ознакомление или исполнение',
        'initial_tab': 'incoming',
        'show_send_button': False,
    })


@login_required
def drafts_documents_page(request):
    """HTML страница черновиков"""
    return render(request, 'main/drafts_documents.html')


@login_required
def outgoing_documents_page(request):
    """HTML страница исходящих документов"""
    return render(request, 'main/outgoing_documents.html', {
        'page_title': 'Исходящие документы',
        'page_subtitle': 'Ваши отправленные документы',
        'initial_tab': 'my',
        'show_send_button': True,
    })


@login_required
def archive_documents_page(request):
    """HTML страница архивных документов"""
    return render(request, 'main/archive_documents.html', {
        'page_title': 'Архив',
        'page_subtitle': 'Архивные документы',
        'show_send_button': False,
    })


@login_required
def profile_page(request):
    """HTML страница профиля"""
    return render(request, 'main/profile.html', {
        'page_title': 'Профиль',
        'page_subtitle': 'Личные данные',
    })


@login_required
def replacements_page(request):
    """HTML страница назначения замены"""
    return render(request, 'main/replacements.html', {
        'page_title': 'Замена',
        'page_subtitle': 'Назначение замены',
    })


@login_required
def stats_page(request):
    """HTML страница статистики сотрудника"""
    user = request.user
    today = timezone.localdate()
    now = timezone.now()
    last_30 = now - timezone.timedelta(days=30)

    min_pending_step = (
        Approval.objects.filter(
            document_id=OuterRef('document_id'),
            decision='pending',
        )
        .values('document_id')
        .annotate(min_step=Min('step'))
        .values('min_step')
    )

    pending_approvals = (
        Approval.objects
        .filter(approver=user, decision='pending', document__is_archived=False)
        .annotate(min_step=Subquery(min_pending_step))
        .filter(
            models.Q(document__action_type='acknowledge')
            | models.Q(document__approval_order='parallel')
            | models.Q(step=models.F('min_step'))
        )
    )

    incoming_doc_ids = pending_approvals.values('document_id').distinct()
    incoming_count = incoming_doc_ids.count()
    overdue_count = pending_approvals.filter(document__deadline__lt=today).values('document_id').distinct().count()

    approval_count = (
        Document.objects
        .filter(author=user, is_archived=False)
        .exclude(status__is_final=True)
        .exclude(status__name__iexact='Черновик')
        .exclude(status__name__icontains='доработ')
        .exclude(status__name__icontains='возвращ')
        .count()
    )

    docs_qs = Document.objects.filter(author=user)
    total_docs = docs_qs.count()
    outgoing_count = docs_qs.filter(is_archived=False).count()
    archived_count = docs_qs.filter(is_archived=True).count()
    in_work_docs = docs_qs.filter(is_archived=False, status__is_final=False).count()
    completed_docs = docs_qs.filter(status__is_final=True).count()
    overdue_docs = docs_qs.filter(is_archived=False, status__is_final=False, deadline__lt=today).count()
    on_registration = docs_qs.filter(status__name__icontains='регистра').count()
    on_approval = docs_qs.filter(status__name__icontains='согласован').count()
    on_signature = docs_qs.filter(status__name__icontains='подпис').count()
    on_revision = docs_qs.filter(status__name__icontains='доработ').count()
    rejected_docs = docs_qs.filter(status__name__icontains='отклон').count()

    on_time = docs_qs.filter(actual_deadline__isnull=False, deadline__isnull=False, actual_deadline__lte=F('deadline')).count()
    late_docs = docs_qs.filter(actual_deadline__isnull=False, deadline__isnull=False, actual_deadline__gt=F('deadline')).count()

    returns_count = Approval.objects.filter(document__author=user, decision='returned').count()
    reapprovals_count = Approval.objects.filter(document__author=user, cycle__gt=1).count()

    status_agg = docs_qs.values('status__name').annotate(count=Count('id')).order_by('-count')
    status_labels = [s['status__name'] or '—' for s in status_agg]
    status_counts = [s['count'] for s in status_agg]

    processed_today = Approval.objects.filter(
        approver=user,
        decided_at__date=today,
        decision__in=['approved', 'rejected', 'acknowledged', 'executed']
    ).count()

    week_labels = []
    weekly_stats = []
    for i in range(6, -1, -1):
        day = today - timezone.timedelta(days=i)
        week_labels.append(day.strftime('%d.%m'))
        weekly_stats.append(
            Approval.objects.filter(
                approver=user,
                decided_at__date=day,
                decision__in=['approved', 'rejected', 'acknowledged', 'executed']
            ).count()
        )

    decisions_qs = Approval.objects.filter(
        approver=user,
        decided_at__isnull=False,
        decided_at__gte=last_30
    )
    decision_counts = decisions_qs.values('decision').annotate(count=Count('id'))
    decision_map = {d['decision']: d['count'] for d in decision_counts}

    avg_processing = (
        decisions_qs
        .annotate(duration=ExpressionWrapper(F('decided_at') - F('created_at'), output_field=DurationField()))
        .aggregate(avg_duration=Avg('duration'))['avg_duration']
    )
    avg_hours = None
    if avg_processing:
        avg_hours = round(avg_processing.total_seconds() / 3600, 1)

    urgent_docs = (
        Document.objects
        .filter(id__in=incoming_doc_ids, deadline__isnull=False)
        .filter(models.Q(deadline__lt=today) | models.Q(deadline__lte=today + timezone.timedelta(days=3)))
        .order_by('deadline')[:5]
    )

    type_activity = (
        Approval.objects
        .filter(approver=user, decided_at__isnull=False, decided_at__gte=last_30)
        .values('document__document_type__name')
        .annotate(count=Count('id'))
        .order_by('-count')
    )
    type_labels = [t['document__document_type__name'] or '—' for t in type_activity]
    type_counts = [t['count'] for t in type_activity]

    month_points = (
        Approval.objects
        .filter(approver=user, decided_at__isnull=False, decided_at__gte=now - timezone.timedelta(days=180))
        .annotate(month=TruncMonth('decided_at'))
        .values('month')
        .annotate(count=Count('id'))
        .order_by('month')
    )
    month_labels = [p['month'].strftime('%m.%Y') for p in month_points]
    month_counts = [p['count'] for p in month_points]

    priority_activity = (
        Approval.objects
        .filter(approver=user, decided_at__isnull=False, decided_at__gte=last_30)
        .values('document__priority')
        .annotate(count=Count('id'))
        .order_by('-count')
    )
    priority_label_map = {
        'low': 'Низкий',
        'normal': 'Обычный',
        'high': 'Высокий',
        'urgent': 'Срочный',
    }
    priority_labels = [priority_label_map.get(p['document__priority'] or 'normal', 'Обычный') for p in priority_activity]
    priority_counts = [p['count'] for p in priority_activity]

    return render(request, 'main/stats.html', {
        'page_title': 'Статистика',
        'page_subtitle': 'Показатели сотрудника',
        'incoming_count': incoming_count,
        'overdue_count': overdue_count,
        'approval_count': approval_count,
        'processed_today': processed_today,
        'weekly_stats': json.dumps(weekly_stats),
        'weekly_labels': json.dumps(week_labels),
        'decision_counts': decision_map,
        'avg_hours': avg_hours,
        'urgent_docs': urgent_docs,
        'type_labels': json.dumps(type_labels),
        'type_counts': json.dumps(type_counts),
        'month_labels': json.dumps(month_labels),
        'month_counts': json.dumps(month_counts),
        'priority_labels': json.dumps(priority_labels),
        'priority_counts': json.dumps(priority_counts),
        'total_docs': total_docs,
        'outgoing_count': outgoing_count,
        'archived_count': archived_count,
        'in_work_docs': in_work_docs,
        'completed_docs': completed_docs,
        'overdue_docs': overdue_docs,
        'on_registration': on_registration,
        'on_approval': on_approval,
        'on_signature': on_signature,
        'on_revision': on_revision,
        'rejected_docs': rejected_docs,
        'on_time': on_time,
        'late_docs': late_docs,
        'returns_count': returns_count,
        'reapprovals_count': reapprovals_count,
        'status_labels': json.dumps(status_labels),
        'status_counts': json.dumps(status_counts),
    })
