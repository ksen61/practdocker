from documentflow.models import (
    DocumentRouteTemplate,
    DocumentRouteStep,
    Approval,
    User,
    Replacement,
    EmployeeStatus,
)
from django.utils import timezone


def _resolve_approver(user):
    if user.status in [
        EmployeeStatus.VACATION,
        EmployeeStatus.SICK,
        EmployeeStatus.BUSINESS_TRIP,
        EmployeeStatus.MATERNITY,
        EmployeeStatus.IDLE,
        EmployeeStatus.OTHER,
        EmployeeStatus.DISMISSED,
    ]:
        today = timezone.localdate()
        replacement = (
            Replacement.objects
            .filter(
                absent_employee=user,
                is_active=True,
                start_date__lte=today,
                end_date__gte=today,
                replacement_employee__is_active=True,
                replacement_employee__status=EmployeeStatus.WORKING
            )
            .order_by('-start_date')
            .first()
        )
        if replacement:
            return replacement.replacement_employee
        if user.department and user.department.head:
            head = user.department.head
            if head.is_active and head.status == EmployeeStatus.WORKING and head.id != user.id:
                return head
        fallback = (
            User.objects
            .filter(
                department=user.department,
                is_active=True,
                status=EmployeeStatus.WORKING
            )
            .exclude(id=user.id)
            .order_by('last_name', 'first_name')
            .first()
        )
        if fallback:
            return fallback
        return None
    return user


def start_document_route(document, route_steps=None):
    """
    Запуск маршрута согласования для документа
    """
    if document.delivery_mode == 'auto':
        _start_auto_route(document)
    else:
        _start_manual_route(document, route_steps or [])


def _start_auto_route(document):
    route = (
        DocumentRouteTemplate.objects
        .filter(
            document_type=document.document_type,
            is_active=True
        )
        .prefetch_related('steps__user', 'steps__department')
        .first()
    )

    if not route:
        return

    steps = route.steps.order_by('step_number')

    for step in steps:
        _create_approvals_for_step(document, step)


def _start_manual_route(document, route_steps):
    step_number = 1

    for item in route_steps:
        if item['type'] == 'user':
            approver = _resolve_approver(User.objects.get(id=item['id']))
            if not approver:
                step_number += 1
                continue
            Approval.objects.create(
                document=document,
                approver=approver,
                step=step_number,
                cycle=1
            )

        elif item['type'] == 'department':
            users = User.objects.filter(
                department_id=item['id'],
                is_active=True
            )
            resolved_users = [_resolve_approver(u) for u in users]
            resolved_users = list({u.id: u for u in resolved_users}.values())
            for user in resolved_users:
                Approval.objects.create(
                    document=document,
                    approver=user,
                    step=step_number,
                    cycle=1
                )

        step_number += 1


def _create_approvals_for_step(document, step):
    if step.user:
        approver = _resolve_approver(step.user)
        if not approver:
            return
        Approval.objects.create(
            document=document,
            approver=approver,
            step=step.step_number,
            cycle=1
        )

    elif step.department:
        users = User.objects.filter(
            department=step.department,
            is_active=True
        )
        resolved_users = [_resolve_approver(u) for u in users]
        resolved_users = list({u.id: u for u in resolved_users}.values())
        for user in resolved_users:
            Approval.objects.create(
                document=document,
                approver=user,
                step=step.step_number,
                cycle=1
            )
