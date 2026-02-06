from rest_framework import serializers
from django.contrib.auth import authenticate
from documentflow.models import (
    Document,
    DocumentType,
    DocumentStatus,
    DocumentFile,
    Approval,
    DocumentRecipient,
    User,
    Role,
    Department,
    DocumentRouteStep,
    DocumentVersion,
    Notification,
    Replacement,
    EmployeeStatus,
)
from django.utils import timezone
from django.db.models import Count, Max, Min


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

class LoginSerializer(serializers.Serializer):
    username = serializers.CharField(required=True)
    password = serializers.CharField(required=True, write_only=True)

    def validate(self, data):
        user = authenticate(username=data.get('username'), password=data.get('password'))
        if not user:
            raise serializers.ValidationError("Неверный логин или пароль")
        if not user.is_active:
            raise serializers.ValidationError("Пользователь заблокирован")
        data['user'] = user
        return data

class UserSerializer(serializers.ModelSerializer):
    role = serializers.CharField(source='role.name', read_only=True)
    display_name = serializers.SerializerMethodField()
    department_name = serializers.SerializerMethodField()
    
    class Meta:
        model = User
        fields = ['id', 'username', 'first_name', 'last_name', 'middle_name', 'email', 'role', 'position', 'department', 'department_name', 'status', 'display_name']

    def get_display_name(self, obj):
        dep = obj.department.name if obj.department else '—'
        pos = obj.position or '—'
        return f"{obj.full_name} ({dep}, {pos})"

    def get_department_name(self, obj):
        return obj.department.name if obj.department else '—'

class DocumentTypeSerializer(serializers.ModelSerializer):
    class Meta:
        model = DocumentType
        fields = ['id', 'name', 'code', 'description']

class DocumentStatusSerializer(serializers.ModelSerializer):
    class Meta:
        model = DocumentStatus
        fields = ['id', 'name', 'color', 'is_final']

class UserShortSerializer(serializers.ModelSerializer):
    display_name = serializers.SerializerMethodField()

    class Meta:
        model = User
        fields = ('id', 'display_name')

    def get_display_name(self, obj):
        dep = obj.department.name if obj.department else '—'
        pos = obj.position or '—'
        return f"{obj.full_name} ({dep}, {pos})"


class ApprovalDetailSerializer(serializers.ModelSerializer):
    approver = UserShortSerializer(read_only=True)
    decision_display = serializers.CharField(source='get_decision_display', read_only=True)

    class Meta:
        model = Approval
        fields = ['id', 'approver', 'step', 'cycle', 'decision', 'decision_display', 'comment', 'decided_at', 'created_at']


class DocumentSerializer(serializers.ModelSerializer):
    author = UserShortSerializer(read_only=True)
    responsible = UserShortSerializer(read_only=True)
    document_type = serializers.PrimaryKeyRelatedField(queryset=DocumentType.objects.all())
    status = serializers.StringRelatedField(read_only=True)
    status_is_final = serializers.SerializerMethodField()
    user_decision = serializers.SerializerMethodField()
    user_decision_display = serializers.SerializerMethodField()
    manual_route = serializers.JSONField(required=False, allow_null=True)
    approval_order = serializers.ChoiceField(
        choices=['sequential', 'parallel'],
        required=False
    )
    class Meta:
        model = Document
        fields = [
            'id', 'registration_number', 'title', 'document_type', 'status',
            'author', 'author_id', 'responsible', 'created_at', 'deadline',
            'updated_at', 'actual_deadline', 'priority', 'description', 'external_number',
            'external_date', 'correspondent', 'delivery_mode', 'approval_order',
            'manual_route', 'action_type', 'last_rejection_comment',
            'last_rejection_at', 'is_archived', 'status_is_final',
            'user_decision', 'user_decision_display'
        ]
        read_only_fields = [
            'registration_number', 'created_at', 'updated_at', 'actual_deadline', 
            'status', 'author', 'external_number', 'external_date', 'responsible'
        ]

    def get_status_is_final(self, obj):
        return bool(getattr(obj.status, 'is_final', False))

    def _get_user_approval(self, obj):
        request = self.context.get('request')
        if not request or not request.user.is_authenticated:
            return None
        base_qs = Approval.objects.filter(document=obj, approver=request.user)
        max_cycle = base_qs.aggregate(max_cycle=Max('cycle'))['max_cycle']
        if max_cycle:
            # Prefer latest cycle to avoid showing old decisions
            cycle_qs = base_qs.filter(cycle=max_cycle)
        else:
            cycle_qs = base_qs

        pending = (
            cycle_qs
            .filter(decision='pending')
            .order_by('-created_at')
            .first()
        )
        if pending:
            if obj.approval_order == 'sequential':
                min_step = cycle_qs.filter(decision='pending').aggregate(min_step=Min('step'))['min_step']
                if min_step is not None and pending.step != min_step:
                    return pending
            return pending

        decided = (
            cycle_qs
            .exclude(decision='pending')
            .order_by('-decided_at', '-created_at')
            .first()
        )
        if decided:
            return decided

        return cycle_qs.order_by('-created_at').first()

    def get_user_decision(self, obj):
        approval = self._get_user_approval(obj)
        return approval.decision if approval else None

    def get_user_decision_display(self, obj):
        approval = self._get_user_approval(obj)
        return approval.get_decision_display() if approval else None
    
    def create(self, validated_data):
        # Автоматически генерируем регистрационный номер
        from datetime import datetime
        today = datetime.now()
        year = today.year
        month = today.month
        
        # Находим последний номер за текущий месяц
        last_doc = Document.objects.filter(
            registration_number__startswith=f"{year:04d}-{month:02d}-"
        ).order_by('-registration_number').first()
        
        if last_doc:
            last_num = int(last_doc.registration_number.split('-')[-1])
            next_num = last_num + 1
        else:
            next_num = 1
        
        validated_data['registration_number'] = f"{year:04d}-{month:02d}-{next_num:04d}"
        
        # Устанавливаем текущего пользователя как автора, если не указан
        request = self.context.get('request')
        if request and request.user.is_authenticated:
            if 'author' not in validated_data:
                validated_data['author'] = request.user
        
        # Создаем документ
        document = Document.objects.create(**validated_data)
        
        # Если выбрана автоматическая рассылка, создаем получателей
        if document.delivery_mode == 'auto' and hasattr(document.document_type, 'routes'):
            routes = document.document_type.routes.all().order_by('step')
            for i, route in enumerate(routes, 1):
                # Находим пользователей с нужной ролью
                users_with_role = User.objects.filter(role=route.role, is_active=True)
                for user in users_with_role:
                    DocumentRecipient.objects.create(
                        document=document,
                        user=user,
                        order=i
                    )
        
        return document
    
    def update(self, instance, validated_data):
        # Обновляем только разрешенные поля
        for attr, value in validated_data.items():
            setattr(instance, attr, value)
        
        instance.save()
        return instance

from rest_framework import serializers
from documentflow.models import Document, DocumentType, DocumentStatus, DocumentRouteTemplate


class DocumentFileSerializer(serializers.ModelSerializer):
    uploaded_by = UserShortSerializer(read_only=True)
    
    class Meta:
        model = DocumentFile
        fields = ['id', 'file', 'file_name', 'file_size', 'file_type', 
                 'uploaded_at', 'uploaded_by', 'description']
        read_only_fields = ['file_name', 'file_size', 'file_type', 'uploaded_at', 'uploaded_by']

class DocumentVersionSerializer(serializers.ModelSerializer):
    created_by = UserShortSerializer(read_only=True)

    class Meta:
        model = DocumentVersion
        fields = ['id', 'file', 'version', 'created_at', 'created_by']


# 🆕 Сериализаторы для новых моделей
class DepartmentSerializer(serializers.ModelSerializer):
    class Meta:
        model = Department 
        fields = ['id', 'name', 'code', 'description']

class DocumentRouteStepSerializer(serializers.ModelSerializer):
    user = serializers.SerializerMethodField()
    department = serializers.SerializerMethodField()
    
    class Meta:
        model = DocumentRouteStep
        fields = ['step_number', 'user', 'department']
    
    def get_user(self, obj):
        """Получить информацию о сотруднике: ФИО, должность и отдел"""
        if obj.user:
            full_name = f"{obj.user.first_name} {obj.user.last_name}".strip()
            
            return {
                'id': obj.user.id,
                'full_name': full_name or obj.user.username,
                'position': obj.user.position if hasattr(obj.user, 'position') else '',
                'department_name': obj.user.department.name if hasattr(obj.user, 'department') and obj.user.department else ''
            }
        return None

    
    def get_department(self, obj):
        if obj.department:
            return {
                'id': obj.department.id,
                'name': obj.department.name
            }
        return None

class DocumentRouteSerializer(serializers.ModelSerializer):
    steps = DocumentRouteStepSerializer(many=True, read_only=True)
    document_type_name = serializers.CharField(source='document_type.name', read_only=True)
    approval_order = serializers.CharField(read_only=True)

    class Meta:
        model = DocumentRouteTemplate
        fields = [
            'id',
            'name',
            'document_type',
            'document_type_name',
            'is_active',
            'approval_order',
            'steps',
        ]

class DocumentDetailSerializer(DocumentSerializer):
    document_type_name = serializers.CharField(source='document_type.name', read_only=True)
    approvals = ApprovalDetailSerializer(many=True, read_only=True)
    files = DocumentFileSerializer(many=True, read_only=True)
    versions = DocumentVersionSerializer(many=True, read_only=True)

    class Meta(DocumentSerializer.Meta):
        fields = DocumentSerializer.Meta.fields + [
            'document_type_name',
            'approvals',
            'files',
            'versions',
        ]



class DocumentCreateSerializer(serializers.ModelSerializer):
    manual_route = serializers.JSONField(write_only=True, required=False)
    delivery_mode = serializers.ChoiceField(
        choices=['auto', 'manual'],
        write_only=True
    )
    status_code = serializers.ChoiceField(
        choices=['draft', 'registered'],
        write_only=True,
        required=False
    )
    action_type = serializers.ChoiceField(
        choices=['approve', 'acknowledge', 'execute'],
        write_only=True,
        required=False
    )
    approval_order = serializers.ChoiceField(
        choices=['sequential', 'parallel'],
        write_only=True,
        required=False,
        default='sequential'
    )

    class Meta:
        model = Document
        fields = [
            'title',
            'document_type',
            'priority',
            'description',
            'deadline',
            'delivery_mode',
            'manual_route',
            'approval_order',
            'status_code',
            'action_type',
        ]

    def create(self, validated_data):
        request = self.context.get('request')
        if not request or not request.user.is_authenticated:
            raise serializers.ValidationError("Не удалось определить автора документа")

        user = request.user

        manual_route = validated_data.pop('manual_route', [])
        delivery_mode = validated_data.pop('delivery_mode')
        approval_order = validated_data.pop('approval_order', 'sequential')
        status_code = validated_data.pop('status_code', None)
        action_type = validated_data.pop('action_type', 'approve')

        if status_code == 'draft':
            status = DocumentStatus.objects.filter(name__iexact='Черновик').first()
        else:
            action_status_map = {
                'approve': 'На согласовании',
                'acknowledge': 'На ознакомлении',
                'execute': 'На исполнении',
            }
            status_name = action_status_map.get(action_type, 'На согласовании')
            status = DocumentStatus.objects.filter(name__iexact=status_name).first()
            if not status:
                status, _ = DocumentStatus.objects.get_or_create(
                    name=status_name,
                    defaults={'color': '#6c757d', 'is_final': False}
                )

        if not status:
            status = DocumentStatus.objects.order_by('id').first()
        if not status:
            raise serializers.ValidationError("Не найден статус документа для создания")

        template = None
        document_type = validated_data["document_type"]
        if status_code != 'draft':
            if delivery_mode == 'auto':
                template = (
                    DocumentRouteTemplate.objects
                    .filter(document_type=document_type, is_active=True)
                    .annotate(step_count=Count('steps'))
                    .filter(step_count__gt=0)
                    .first()
                )
                if not template:
                    raise serializers.ValidationError(
                        "Для выбранного типа документа нет активного маршрута с шагами"
                    )
                approval_order = template.approval_order
            else:
                if not manual_route:
                    raise serializers.ValidationError("Для ручного маршрута нужен manual_route")

        # ❗ author НЕ передаём здесь, если он передаётся через serializer.save()
        document = Document.objects.create(
            title=validated_data["title"],
            document_type=validated_data["document_type"],
            priority=validated_data.get("priority", "normal"),
            description=validated_data.get("description", ""),
            deadline=validated_data["deadline"],
            delivery_mode=delivery_mode,
            approval_order=approval_order,
            manual_route=manual_route if delivery_mode == 'manual' else None,
            action_type=action_type,
            author=user,
            responsible=user,   # ← ОБЯЗАТЕЛЬНО ЗДЕСЬ
            status=status,
        )


        # ===== Генерация регистрационного номера =====
        from datetime import datetime
        today = datetime.now()
        prefix = f"{today.year:04d}-{today.month:02d}-"

        last_doc = Document.objects.filter(
            registration_number__startswith=prefix
        ).order_by('-registration_number').first()

        next_num = int(last_doc.registration_number.split('-')[-1]) + 1 if last_doc else 1
        document.registration_number = f"{prefix}{next_num:04d}"
        if not document.external_number:
            document.external_number = document.registration_number
        if not document.external_date:
            document.external_date = timezone.now().date()
        document.save()

        # ===== Сохранение файлов =====
        files = []
        if request and hasattr(request, 'FILES'):
            files = request.FILES.getlist('files')

        for file_obj in files:
            doc_file = DocumentFile.objects.create(
                document=document,
                file=file_obj,
                uploaded_by=user,
            )
            DocumentVersion.objects.create(
                document=document,
                file=doc_file.file,
                created_by=user,
            )

        # ===== Формирование маршрута =====
        if status_code == 'draft':
            return document

        if delivery_mode == 'auto':
            approval_order = template.approval_order

            sequential_created = []
            for step in template.steps.all().order_by('step_number'):
                users = []

                if step.user:
                    resolved = _resolve_approver(step.user)
                    if resolved and resolved != document.author:
                        users.append(resolved)
                elif step.department:
                    users.extend(
                        User.objects.filter(
                            department=step.department,
                            is_active=True
                        )
                    )
                users = [_resolve_approver(u) for u in users]
                users = [u for u in users if u]
                users = [u for u in users if u != document.author]
                users = list({u.id: u for u in users}.values())

                for approver in users:
                    approval, created = Approval.objects.get_or_create(
                        document=document,
                        approver=approver,
                        step=step.step_number if approval_order == 'sequential' else 1,
                        cycle=1,
                        defaults={
                            'decision': 'pending',
                            'is_required': True
                        }
                    )
                    if created:
                        if approval_order == 'sequential':
                            sequential_created.append(approval)
                        else:
                            Notification.objects.create(
                                user=approver,
                                notification_type='new_document',
                                title='Новый документ',
                                text=f'{document.registration_number} — {document.title}',
                                link=f'/documents/incoming/?open={document.id}',
                                document=document,
                                sender=user
                            )
            if approval_order == 'sequential' and sequential_created:
                min_step = min(a.step for a in sequential_created)
                for approval in [a for a in sequential_created if a.step == min_step]:
                    Notification.objects.create(
                        user=approval.approver,
                        notification_type='new_document',
                        title='Новый документ',
                        text=f'{document.registration_number} — {document.title}',
                        link=f'/documents/incoming/?open={document.id}',
                        document=document,
                        sender=user
                    )

        else:
            sequential_created = []
            for i, step_data in enumerate(manual_route, start=1):
                step_number = i if approval_order == 'sequential' else 1

                if step_data.get('type') == 'user':
                    try:
                        approver = User.objects.get(
                            id=step_data['id'],
                            is_active=True
                        )
                        approver = _resolve_approver(approver)
                        if not approver:
                            continue
                        approval, created = Approval.objects.get_or_create(
                            document=document,
                            approver=approver,
                            step=step_number,
                            cycle=1,
                            defaults={
                                'decision': 'pending',
                                'is_required': True
                            }
                        )
                        if created:
                            if approval_order == 'sequential':
                                sequential_created.append(approval)
                            else:
                                Notification.objects.create(
                                    user=approver,
                                    notification_type='new_document',
                                    title='Новый документ',
                                    text=f'{document.registration_number} — {document.title}',
                                    link=f'/documents/incoming/?open={document.id}',
                                    document=document,
                                    sender=user
                                )
                    except User.DoesNotExist:
                        continue

                elif step_data.get('type') == 'department':
                    users = User.objects.filter(
                        department_id=step_data['id'],
                        is_active=True
                    )
                    resolved_users = [_resolve_approver(u) for u in users]
                    resolved_users = [u for u in resolved_users if u]
                    resolved_users = list({u.id: u for u in resolved_users}.values())
                    for approver in resolved_users:
                        approval, created = Approval.objects.get_or_create(
                            document=document,
                            approver=approver,
                            step=step_number,
                            cycle=1,
                            defaults={
                                'decision': 'pending',
                                'is_required': True
                            }
                        )
                        if created:
                            if approval_order == 'sequential':
                                sequential_created.append(approval)
                            else:
                                Notification.objects.create(
                                    user=approver,
                                    notification_type='new_document',
                                    title='Новый документ',
                                    text=f'{document.registration_number} — {document.title}',
                                    link=f'/documents/incoming/?open={document.id}',
                                    document=document,
                                    sender=user
                                )
            if approval_order == 'sequential' and sequential_created:
                min_step = min(a.step for a in sequential_created)
                for approval in [a for a in sequential_created if a.step == min_step]:
                    Notification.objects.create(
                        user=approval.approver,
                        notification_type='new_document',
                        title='Новый документ',
                        text=f'{document.registration_number} — {document.title}',
                        link=f'/documents/incoming/?open={document.id}',
                        document=document,
                        sender=user
                    )

        return document
