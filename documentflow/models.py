from django.db import models
from django.contrib.auth.models import AbstractUser, BaseUserManager
from django.utils.translation import gettext_lazy as _
from django.utils import timezone
from django.db.models.signals import post_delete
from django.dispatch import receiver
from django.core.exceptions import ValidationError



# ====== Отделы ======
class Department(models.Model):
    name = models.CharField(
        max_length=100,
        unique=True,
        verbose_name="Название отдела"
    )
    code = models.CharField(
        max_length=20,
        blank=True,
        null=True,
        verbose_name="Код отдела"
    )
    head = models.ForeignKey(
        'User',
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name='headed_departments',
        verbose_name="Руководитель отдела"
    )
    description = models.TextField(
        blank=True,
        null=True,
        verbose_name="Описание"
    )

    class Meta:
        verbose_name = "Отдел"
        verbose_name_plural = "Отделы"
        ordering = ['name']

    def __str__(self):
        return self.name


# ====== Роли ======
class Role(models.Model):
    name = models.CharField(
        max_length=50,
        unique=True,
        verbose_name="Название роли"
    )

    class Meta:
        verbose_name = "Роль"
        verbose_name_plural = "Роли"

    def __str__(self):
        return self.name



# ====== Статус сотрудника ======
class EmployeeStatus(models.TextChoices):
    WORKING = 'working', 'Работает'
    VACATION = 'vacation', 'В отпуске'
    SICK = 'sick', 'На больничном'
    BUSINESS_TRIP = 'business_trip', 'В командировке'
    MATERNITY = 'maternity', 'В декрете'
    IDLE = 'idle', 'В простое'
    OTHER = 'other', 'Другое'
    DISMISSED = 'dismissed', 'Уволен'



# ====== Менеджер пользователей ======
class UserManager(BaseUserManager):
    def create_user(self, username, email=None, password=None, **extra_fields):
        if not username:
            raise ValueError('Username обязателен')

        email = self.normalize_email(email)
        
        # Получаем роль
        role = extra_fields.pop('role', None)
        if role is None:
            # Роль по умолчанию = Сотрудник
            role, created = Role.objects.get_or_create(name='Сотрудник')

        user = self.model(
            username=username,
            email=email,
            role=role,
            **extra_fields
        )
        user.set_password(password)
        user.save(using=self._db)
        return user

    def create_superuser(self, username, email=None, password=None, **extra_fields):
        extra_fields.setdefault('is_staff', True)
        extra_fields.setdefault('is_superuser', True)

        # Роль суперпользователя = Администратор
        admin_role, created = Role.objects.get_or_create(name='Администратор')
        extra_fields['role'] = admin_role

        return self.create_user(username, email, password, **extra_fields)



class User(AbstractUser):
    middle_name = models.CharField(
        max_length=100, 
        blank=True, 
        null=True, 
        verbose_name="Отчество"
    )
    role = models.ForeignKey(
        Role,
        on_delete=models.PROTECT,
        verbose_name="Роль"
    )
    position = models.CharField(
        max_length=100,
        verbose_name="Должность"
    )
    department = models.ForeignKey(
        Department,  # <-- ИЗМЕНЕНИЕ: теперь ForeignKey на Department
        on_delete=models.PROTECT,  # <-- PROTECT вместо CASCADE для отделов
        verbose_name="Отдел"
    )
    status = models.CharField(
        max_length=20,
        choices=EmployeeStatus.choices,
        default=EmployeeStatus.WORKING,
        verbose_name="Статус сотрудника"
    )
    phone = models.CharField(
        max_length=20,
        blank=True,
        null=True,
        verbose_name="Телефон"
    )
    room = models.CharField(
        max_length=20,
        blank=True,
        null=True,
        verbose_name="Кабинет"
    )
    must_change_password = models.BooleanField(
        default=False,
        verbose_name="Требуется смена пароля"
    )
    
    # Исправляем конфликты имен
    groups = models.ManyToManyField(
        'auth.Group',
        verbose_name='Группы',
        blank=True,
        help_text='Группы, к которым принадлежит пользователь.',
        related_name='main_user_set',
        related_query_name='main_user',
    )
    user_permissions = models.ManyToManyField(
        'auth.Permission',
        verbose_name='Права доступа',
        blank=True,
        help_text='Конкретные права для этого пользователя.',
        related_name='main_user_set',
        related_query_name='main_user',
    )

    objects = UserManager()

    REQUIRED_FIELDS = ['email', 'first_name', 'last_name', 'middle_name', 'position', 'department']

    class Meta:
        verbose_name = "Сотрудник"
        verbose_name_plural = "Сотрудники"
        ordering = ['last_name', 'first_name']
    
    @property
    def full_name(self):
        # Убеждаемся, что берем значения, удаляя лишние пробелы
        parts = [self.last_name, self.first_name, self.middle_name]
        fio = " ".join([p for p in parts if p and p.strip()]).strip()
        return fio if fio else self.username

    def __str__(self):
        parts = [self.full_name]

        if self.department:
            parts.append(self.department.name)

        if self.position:
            parts.append(self.position)

        return f"{self.full_name} ({', '.join(parts[1:])})" if len(parts) > 1 else self.full_name


    @property
    def short_name(self):
        if not self.last_name:
            return self.username
            
        name_parts = [self.last_name]
        if self.first_name:
            name_parts.append(f"{self.first_name[0]}.")
        if self.middle_name:
            name_parts.append(f"{self.middle_name[0]}.")
            
        return " ".join(name_parts)
    
    @property
    def initials(self):
        initials = ""
        if self.last_name:
            initials += self.last_name[0]
        if self.first_name:
            initials += self.first_name[0]
        return initials.upper() if initials else self.username[0].upper()

    @property
    def unread_notifications(self):
        return self.notifications.filter(is_read=False).count()

    def save(self, *args, **kwargs):
        previous_status = None
        if self.pk:
            try:
                previous_status = User.objects.only('status').get(pk=self.pk).status
            except User.DoesNotExist:
                previous_status = None

        super().save(*args, **kwargs)

        if previous_status != EmployeeStatus.DISMISSED and self.status == EmployeeStatus.DISMISSED:
            replacement_user = None
            today = timezone.localdate()
            replacement = (
                Replacement.objects
                .filter(
                    absent_employee=self,
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
                replacement_user = replacement.replacement_employee
            elif (
                self.department
                and self.department.head
                and self.department.head.is_active
                and self.department.head.status == EmployeeStatus.WORKING
            ):
                replacement_user = self.department.head
            else:
                replacement_user = (
                    User.objects
                    .filter(
                        department=self.department,
                        is_active=True,
                        status=EmployeeStatus.WORKING
                    )
                    .exclude(id=self.id)
                    .order_by('last_name', 'first_name')
                    .first()
                )

            if replacement_user:
                DocumentRouteStep.objects.filter(user=self).update(user=replacement_user)


# ====== Тип и статус документа ======
class DocumentType(models.Model):
    name = models.CharField(
        max_length=50, 
        verbose_name="Тип документа",
        unique=True
    )
    code = models.CharField(
        max_length=10,
        blank=True,
        null=True,
        verbose_name="Код типа"
    )
    description = models.TextField(
        blank=True,
        null=True,
        verbose_name="Описание типа"
    )
    approval_order = models.CharField(
        max_length=20,
        choices=[
            ('sequential', 'Последовательный'),
            ('parallel', 'Параллельный'),
        ],
        default='sequential',
        verbose_name="Порядок согласования"
    )

    class Meta:
        verbose_name = "Тип документа"
        verbose_name_plural = "Типы документов"

    def __str__(self):
        return self.name



class DocumentStatus(models.Model):
    name = models.CharField(
        max_length=50, 
        verbose_name="Статус документа",
        unique=True
    )
    color = models.CharField(
        max_length=20,
        default='#6c757d',
        verbose_name="Цвет статуса"
    )
    is_final = models.BooleanField(
        default=False,
        verbose_name="Конечный статус"
    )

    class Meta:
        verbose_name = "Статус документа"
        verbose_name_plural = "Статусы документов"
        ordering = ['id']

    def __str__(self):
        return self.name



# ====== Документ ======
class Document(models.Model):
    registration_number = models.CharField(
        max_length=50, 
        unique=True, 
        verbose_name="Регистрационный номер",
        db_index=True
    )
    title = models.CharField(
        max_length=255, 
        verbose_name="Тема документа"
    )
    document_type = models.ForeignKey(
        DocumentType, 
        on_delete=models.PROTECT, 
        verbose_name="Тип документа"
    )
    status = models.ForeignKey(
        DocumentStatus, 
        on_delete=models.PROTECT, 
        verbose_name="Статус"
    )
    author = models.ForeignKey(
        User, 
        on_delete=models.PROTECT, 
        related_name='created_documents', 
        verbose_name="Автор"
    )
    responsible = models.ForeignKey(
        User, 
        on_delete=models.PROTECT, 
        related_name='assigned_documents', 
        verbose_name="Ответственный"
    )
    created_at = models.DateTimeField(
        auto_now_add=True, 
        verbose_name="Дата создания"
    )
    updated_at = models.DateTimeField(
        auto_now=True,
        verbose_name="Дата обновления"
    )
    deadline = models.DateField(
        null=True, 
        blank=True, 
        verbose_name="Срок исполнения"
    )
    actual_deadline = models.DateField(
        null=True,
        blank=True,
        verbose_name="Фактический срок исполнения"
    )
    is_archived = models.BooleanField(
        default=False, 
        verbose_name="В архиве"
    )
    priority = models.CharField(
        max_length=20,
        choices=[
            ('low', 'Низкий'),
            ('normal', 'Обычный'),
            ('high', 'Высокий'),
            ('urgent', 'Срочный')
        ],
        default='normal',
        verbose_name="Приоритет"
    )
    description = models.TextField(
        blank=True,
        null=True,
        verbose_name="Описание"
    )
    external_number = models.CharField(
        max_length=100,
        blank=True,
        null=True,
        verbose_name="Входящий номер"
    )
    external_date = models.DateField(
        blank=True,
        null=True,
        verbose_name="Входящая дата"
    )
    correspondent = models.CharField(
        max_length=255,
        blank=True,
        null=True,
        verbose_name="Корреспондент"
    )
    delivery_mode = models.CharField(
        max_length=20,
        choices=[
            ('auto', 'Автоматическая'),
            ('manual', 'Ручная'),
        ],
        default='auto',
        verbose_name="Способ рассылки"
    )
    approval_order = models.CharField(
        max_length=20,
        choices=[
            ('sequential', 'Последовательный'),
            ('parallel', 'Параллельный'),
        ],
        default='sequential',
        verbose_name="Порядок согласования"
    )
    manual_route = models.JSONField(
        blank=True,
        null=True,
        verbose_name="Ручной маршрут"
    )
    action_type = models.CharField(
        max_length=20,
        choices=[
            ('approve', 'Согласование'),
            ('acknowledge', 'Ознакомление'),
            ('execute', 'Исполнение'),
        ],
        default='approve',
        verbose_name="Тип обработки"
    )
    last_rejection_comment = models.TextField(
        blank=True,
        null=True,
        verbose_name="Комментарий к отклонению"
    )
    last_rejection_at = models.DateTimeField(
        blank=True,
        null=True,
        verbose_name="Дата отклонения"
    )

    class Meta:
        verbose_name = "Документ"
        verbose_name_plural = "Документы"
        ordering = ['-created_at']
        indexes = [
            models.Index(fields=['registration_number']),
            models.Index(fields=['deadline']),
            models.Index(fields=['status']),
            models.Index(fields=['document_type']),
        ]

    def __str__(self):
        return f"{self.registration_number} — {self.title}"
    
    def clean(self):
        if self.deadline and self.created_at:
            from django.utils import timezone
            if self.deadline < self.created_at.date():
                raise ValidationError({
                    'deadline': 'Срок исполнения не может быть раньше даты создания документа'
                })
    
    @property
    def is_overdue(self):
        if not self.deadline:
            return False
        from django.utils import timezone
        today = timezone.now().date()
        return today > self.deadline and self.status.name not in ['Исполнен', 'Отклонен', 'Архив']
    
    @property
    def days_until_deadline(self):
        if not self.deadline:
            return None
        from django.utils import timezone
        today = timezone.now().date()
        delta = (self.deadline - today).days
        return delta


# ====== Файлы документа ======
class DocumentFile(models.Model):
    document = models.ForeignKey(
        Document, 
        on_delete=models.CASCADE, 
        related_name='files', 
        verbose_name="Документ"
    )
    file = models.FileField(
        upload_to='documents/%Y/%m/%d/', 
        verbose_name="Файл"
    )
    file_name = models.CharField(
        max_length=255,
        verbose_name="Имя файла",
        blank=True
    )
    file_size = models.BigIntegerField(
        verbose_name="Размер файла",
        default=0
    )
    file_type = models.CharField(
        max_length=50,
        verbose_name="Тип файла",
        blank=True
    )
    uploaded_at = models.DateTimeField(
        auto_now_add=True, 
        verbose_name="Дата загрузки"
    )
    uploaded_by = models.ForeignKey(
        User,
        on_delete=models.SET_NULL,
        null=True,
        related_name='uploaded_files',
        verbose_name="Загрузил"
    )
    description = models.CharField(
        max_length=255,
        blank=True,
        verbose_name="Описание файла"
    )

    class Meta:
        verbose_name = "Файл документа"
        verbose_name_plural = "Файлы документов"
        ordering = ['-uploaded_at']

    def __str__(self):
        return self.file_name or self.file.name
    
    def save(self, *args, **kwargs):
        if self.file:
            # Сохраняем оригинальное имя файла
            if not self.file_name:
                self.file_name = self.file.name
            
            # Определяем размер файла
            try:
                self.file_size = self.file.size
            except (AttributeError, OSError):
                pass
            
            # Определяем тип файла
            if not self.file_type:
                import os
                ext = os.path.splitext(self.file.name)[1].lower()
                if ext in ['.pdf']:
                    self.file_type = 'PDF'
                elif ext in ['.doc', '.docx']:
                    self.file_type = 'Word'
                elif ext in ['.xls', '.xlsx']:
                    self.file_type = 'Excel'
                elif ext in ['.jpg', '.jpeg', '.png', '.gif']:
                    self.file_type = 'Image'
                else:
                    self.file_type = 'Other'
        
        super().save(*args, **kwargs)


# ====== Согласование ======
class Approval(models.Model):
    DECISION_CHOICES = [
        ('pending', 'Ожидает решения'),
        ('approved', 'Согласовано'), 
        ('rejected', 'Отклонено'),
        ('returned', 'Возвращено на доработку'),
        ('acknowledged', 'Ознакомлен'),
        ('executed', 'Исполнен')
    ]
    
    document = models.ForeignKey(
        Document, 
        on_delete=models.CASCADE, 
        related_name='approvals', 
        verbose_name="Документ"
    )
    approver = models.ForeignKey(
        User, 
        on_delete=models.PROTECT, 
        verbose_name="Согласующий"
    )
    step = models.PositiveIntegerField(
        default=1,
        verbose_name="Шаг согласования"
    )
    cycle = models.PositiveIntegerField(
        default=1,
        verbose_name="Раунд согласования"
    )
    decision = models.CharField(
        max_length=20, 
        choices=DECISION_CHOICES, 
        default='pending',
        verbose_name="Решение"
    )
    comment = models.TextField(
        blank=True, 
        verbose_name="Комментарий"
    )
    decided_at = models.DateTimeField(
        null=True, 
        blank=True,
        verbose_name="Дата решения"
    )
    created_at = models.DateTimeField(
        auto_now_add=True,
        verbose_name="Дата назначения"
    )
    deadline = models.DateField(
        null=True,
        blank=True,
        verbose_name="Срок согласования"
    )
    is_required = models.BooleanField(
        default=True,
        verbose_name="Обязательное согласование"
    )

    class Meta:
        verbose_name = "Согласование"
        verbose_name_plural = "Согласования"
        ordering = ['step', 'created_at']
        unique_together = ['document', 'approver', 'step', 'cycle']

    def __str__(self):
        return f"{self.document.registration_number} - {self.approver} - {self.get_decision_display()}"
    
    @property
    def is_overdue(self):
        if not self.deadline:
            return False
        from django.utils import timezone
        today = timezone.now().date()
        return today > self.deadline and self.decision == 'pending'


# ====== Уведомления ======
class Notification(models.Model):
    TYPE_CHOICES = [
        ('new_document', 'Новый документ'),
        ('deadline', 'Срок исполнения'),
        ('approval', 'Согласование'),
        ('assignment', 'Назначение'),
        ('status_change', 'Изменение статуса'),
        ('comment', 'Комментарий'),
        ('system', 'Системное'),
    ]
    
    user = models.ForeignKey(
        User, 
        on_delete=models.CASCADE, 
        related_name='notifications',
        verbose_name="Получатель"
    )
    notification_type = models.CharField(
        max_length=20, 
        choices=TYPE_CHOICES, 
        default='system',
        verbose_name="Тип уведомления"
    )
    title = models.CharField(
        max_length=255,
        verbose_name="Заголовок"
    )
    text = models.TextField(
        verbose_name="Текст уведомления"
    )
    link = models.CharField(
        max_length=255, 
        blank=True, 
        verbose_name="Ссылка"
    )
    is_read = models.BooleanField(
        default=False, 
        verbose_name="Прочитано"
    )
    created_at = models.DateTimeField(
        auto_now_add=True, 
        verbose_name="Дата создания"
    )
    read_at = models.DateTimeField(
        null=True,
        blank=True,
        verbose_name="Дата прочтения"
    )
    document = models.ForeignKey(
        Document,
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name='notifications',
        verbose_name="Связанный документ"
    )
    sender = models.ForeignKey(
        User,
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name='sent_notifications',
        verbose_name="Отправитель"
    )

    class Meta:
        verbose_name = "Уведомление"
        verbose_name_plural = "Уведомления"
        ordering = ['-created_at']
        indexes = [
            models.Index(fields=['user', 'is_read']),
            models.Index(fields=['created_at']),
        ]

    def __str__(self):
        return f"{self.user}: {self.title}"
    
    def mark_as_read(self):
        if not self.is_read:
            self.is_read = True
            from django.utils import timezone
            self.read_at = timezone.now()
            self.save()


class EmailChangeRequest(models.Model):
    user = models.ForeignKey(
        User,
        on_delete=models.CASCADE,
        related_name='email_change_requests',
        verbose_name="Сотрудник"
    )
    new_email = models.EmailField(verbose_name="Новый email")
    code = models.CharField(max_length=6, verbose_name="Код подтверждения")
    attempts = models.PositiveSmallIntegerField(default=0, verbose_name="Попытки ввода")
    resend_count = models.PositiveSmallIntegerField(default=0, verbose_name="Повторные отправки")
    last_sent_at = models.DateTimeField(auto_now_add=True, verbose_name="Последняя отправка")
    created_at = models.DateTimeField(auto_now_add=True, verbose_name="Дата создания")

    class Meta:
        verbose_name = "Запрос смены email"
        verbose_name_plural = "Запросы смены email"
        ordering = ['-created_at']

    def is_expired(self):
        return self.created_at < timezone.now() - timezone.timedelta(minutes=10)


# ====== Журнал действий ======
class ActionLog(models.Model):
    ACTION_CHOICES = [
        ('create', 'Создание'),
        ('update', 'Обновление'),
        ('delete', 'Удаление'),
        ('status_change', 'Изменение статуса'),
        ('approve', 'Согласование'),
        ('reject', 'Отклонение'),
        ('comment', 'Комментарий'),
        ('view', 'Просмотр'),
        ('download', 'Скачивание'),
        ('assign', 'Назначение'),
    ]
    
    user = models.ForeignKey(
        User, 
        on_delete=models.SET_NULL, 
        null=True,
        related_name='actions',
        verbose_name="Пользователь"
    )
    document = models.ForeignKey(
        Document, 
        on_delete=models.SET_NULL, 
        null=True, 
        blank=True,
        related_name='actions',
        verbose_name="Документ"
    )
    action = models.CharField(
        max_length=50, 
        choices=ACTION_CHOICES, 
        verbose_name="Тип действия"
    )
    description = models.TextField(
        verbose_name="Описание"
    )
    details = models.JSONField(
        blank=True,
        null=True,
        verbose_name="Детали действия"
    )
    ip_address = models.GenericIPAddressField(
        null=True, 
        blank=True, 
        verbose_name="IP адрес"
    )
    user_agent = models.TextField(
        blank=True,
        null=True,
        verbose_name="User Agent"
    )
    timestamp = models.DateTimeField(
        auto_now_add=True, 
        verbose_name="Дата и время"
    )

    class Meta:
        verbose_name = "Журнал действий"
        verbose_name_plural = "Журнал действий"
        ordering = ['-timestamp']
        indexes = [
            models.Index(fields=['user', 'timestamp']),
            models.Index(fields=['document', 'timestamp']),
        ]

    def __str__(self):
        return f"{self.user} - {self.get_action_display()} - {self.timestamp}"


# ====== Комментарии ======
class Comment(models.Model):
    document = models.ForeignKey(
        Document,
        on_delete=models.CASCADE,
        related_name='comments',
        verbose_name="Документ"
    )
    author = models.ForeignKey(
        User,
        on_delete=models.PROTECT,
        related_name='comments',
        verbose_name="Автор"
    )
    text = models.TextField(
        verbose_name="Текст комментария"
    )
    created_at = models.DateTimeField(
        auto_now_add=True,
        verbose_name="Дата создания"
    )
    updated_at = models.DateTimeField(
        auto_now=True,
        verbose_name="Дата обновления"
    )
    is_internal = models.BooleanField(
        default=True,
        verbose_name="Внутренний комментарий"
    )

    class Meta:
        verbose_name = "Комментарий"
        verbose_name_plural = "Комментарии"
        ordering = ['-created_at']

    def __str__(self):
        return f"{self.author}: {self.text[:50]}..."


# ====== Замена сотрудников ======
class Replacement(models.Model):
    absent_employee = models.ForeignKey(
        User, 
        on_delete=models.CASCADE, 
        related_name='absences', 
        verbose_name="Отсутствующий сотрудник"
    )
    replacement_employee = models.ForeignKey(
        User, 
        on_delete=models.CASCADE, 
        related_name='replacements', 
        verbose_name="Сотрудник-замена"
    )
    reason = models.CharField(
        max_length=50,
        choices=[
            ('vacation', 'Отпуск'),
            ('sick', 'Больничный'),
            ('business_trip', 'Командировка'),
            ('maternity', 'Декрет'),
            ('idle', 'Простой'),
            ('dismissed', 'Уволен'),
            ('other', 'Другое')
        ],
        default='vacation',
        verbose_name="Причина замены"
    )
    start_date = models.DateField(
        verbose_name="Дата начала"
    )
    end_date = models.DateField(
        null=True,
        blank=True,
        verbose_name="Дата окончания"
    )
    is_active = models.BooleanField(
        default=True,
        verbose_name="Активна"
    )
    created_at = models.DateTimeField(
        auto_now_add=True,
        verbose_name="Дата создания"
    )
    created_by = models.ForeignKey(
        User,
        on_delete=models.SET_NULL,
        null=True,
        related_name='created_replacements',
        verbose_name="Кем создана"
    )

    class Meta:
        verbose_name = "Замена сотрудника"
        verbose_name_plural = "Замены сотрудников"
        ordering = ['-start_date']
    
    def __str__(self):
        return f"{self.absent_employee} → {self.replacement_employee} ({self.start_date} - {self.end_date})"
    
    def clean(self):
        if not self.end_date and self.reason != 'dismissed':
            raise ValidationError({
                'end_date': 'Дата окончания обязательна (кроме случая "Уволен")'
            })
        if self.start_date and self.end_date:
            if self.end_date < self.start_date:
                raise ValidationError({
                    'end_date': 'Дата окончания не может быть раньше даты начала'
                })
    
    def save(self, *args, **kwargs):
        # Проверяем, активна ли замена
        from django.utils import timezone
        today = timezone.now().date()
        if self.end_date:
            self.is_active = self.start_date <= today <= self.end_date
        else:
            self.is_active = self.start_date <= today
        super().save(*args, **kwargs)

        # Автоматически обновляем статус отсутствующего сотрудника
        if self.is_active and self.absent_employee:
            status_map = {
                'vacation': EmployeeStatus.VACATION,
                'sick': EmployeeStatus.SICK,
                'business_trip': EmployeeStatus.BUSINESS_TRIP,
                'maternity': EmployeeStatus.MATERNITY,
                'idle': EmployeeStatus.IDLE,
                'dismissed': EmployeeStatus.DISMISSED,
            }
            new_status = status_map.get(self.reason)
            if new_status and self.absent_employee.status != new_status:
                self.absent_employee.status = new_status
                self.absent_employee.save(update_fields=['status'])

            if self.reason == 'dismissed' and self.replacement_employee:
                DocumentRouteStep.objects.filter(user=self.absent_employee).update(
                    user=self.replacement_employee
                )
        elif self.absent_employee:
            has_other_active = Replacement.objects.filter(
                absent_employee=self.absent_employee,
                is_active=True
            ).exists()
            if not has_other_active:
                self.absent_employee.status = EmployeeStatus.WORKING
                self.absent_employee.save(update_fields=['status'])


# ====== Настройки системы ======
class SystemSettings(models.Model):
    key = models.CharField(
        max_length=100,
        unique=True,
        verbose_name="Ключ настройки"
    )
    value = models.TextField(
        verbose_name="Значение"
    )
    description = models.TextField(
        blank=True,
        verbose_name="Описание"
    )
    updated_at = models.DateTimeField(
        auto_now=True,
        verbose_name="Дата обновления"
    )

    class Meta:
        verbose_name = "Настройка системы"
        verbose_name_plural = "Настройки системы"

    def __str__(self):
        return self.key


@receiver(post_delete, sender=Replacement)
def restore_status_on_replacement_delete(sender, instance, **kwargs):
    if not instance.absent_employee:
        return
    has_other_active = Replacement.objects.filter(
        absent_employee=instance.absent_employee,
        is_active=True
    ).exists()
    if not has_other_active:
        instance.absent_employee.status = EmployeeStatus.WORKING
        instance.absent_employee.save(update_fields=['status'])


# ====== Шаблоны документов ======
class DocumentTemplate(models.Model):
    name = models.CharField(
        max_length=100,
        verbose_name="Название шаблона"
    )
    document_type = models.ForeignKey(
        DocumentType,
        on_delete=models.PROTECT,
        verbose_name="Тип документа"
    )
    template_file = models.FileField(
        upload_to='templates/',
        verbose_name="Файл шаблона"
    )
    description = models.TextField(
        blank=True,
        verbose_name="Описание"
    )
    is_active = models.BooleanField(
        default=True,
        verbose_name="Активен"
    )
    created_at = models.DateTimeField(
        auto_now_add=True,
        verbose_name="Дата создания"
    )

    class Meta:
        verbose_name = "Шаблон документа"
        verbose_name_plural = "Шаблоны документов"

    def __str__(self):
        return self.name


class DocumentRecipient(models.Model):
    document = models.ForeignKey(
        Document,
        on_delete=models.CASCADE,
        related_name='recipients',
        verbose_name="Документ"
    )
    user = models.ForeignKey(
        User,
        on_delete=models.PROTECT,
        verbose_name="Получатель"
    )
    order = models.PositiveIntegerField(
        default=1,
        verbose_name="Порядок обработки"
    )
    is_completed = models.BooleanField(
        default=False,
        verbose_name="Обработан"
    )
    received_at = models.DateTimeField(
        auto_now_add=True,
        verbose_name="Дата получения"
    )
    completed_at = models.DateTimeField(
        null=True,
        blank=True,
        verbose_name="Дата завершения"
    )

    class Meta:
        verbose_name = "Получатель документа"
        verbose_name_plural = "Получатели документов"
        ordering = ['order']
        unique_together = ['document', 'user']

    def __str__(self):
        return f"{self.document} → {self.user}"


# models.py
class DocumentRouteTemplate(models.Model):
    name = models.CharField(max_length=100, verbose_name="Название маршрута")
    document_type = models.ForeignKey(DocumentType, on_delete=models.PROTECT, verbose_name="Тип документа")
    is_active = models.BooleanField(default=True, verbose_name="Активен")
    approval_order = models.CharField(
        max_length=20,
        choices=[
            ('sequential', 'Последовательный'),
            ('parallel', 'Параллельный'),
        ],
        default='sequential',
        verbose_name="Порядок согласования"
    )

    class Meta:
        verbose_name = "Маршрут документа"
        verbose_name_plural = "Маршруты документов"

    def __str__(self):
        return self.name



class DocumentRouteStep(models.Model):
    template = models.ForeignKey(DocumentRouteTemplate, on_delete=models.CASCADE, related_name='steps')
    step_number = models.PositiveIntegerField()
    user = models.ForeignKey(
        User,
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        limit_choices_to={'is_active': True},
        verbose_name="Сотрудник"
    )
    department = models.ForeignKey(
        Department,  # <-- ИСПРАВЛЕНО: теперь на Department модель
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        verbose_name="Отдел"
    )

    class Meta:
        ordering = ['step_number']

    def __str__(self):
        if self.user:
            return f"{self.step_number}. {self.user.full_name} ({self.user.department})"
        elif self.department:
            return f"{self.step_number}. Отдел: {self.department.name}"
        return f"{self.step_number}. Не задано"


class DocumentVersion(models.Model):
    document = models.ForeignKey(
        Document,
        on_delete=models.CASCADE,
        related_name='versions',
        verbose_name="Документ"
    )
    file = models.FileField(
        upload_to='documents/versions/',
        verbose_name="Файл версии"
    )
    version = models.PositiveIntegerField(
        verbose_name="Номер версии"
    )
    created_at = models.DateTimeField(auto_now_add=True, verbose_name="Дата создания")
    created_by = models.ForeignKey(
        User,
        on_delete=models.SET_NULL,
        null=True,
        verbose_name="Создал"
    )

    class Meta:
        ordering = ['-version']
        verbose_name = "Версия документа"
        verbose_name_plural = "Версии документов"
        unique_together = ['document', 'version']

    def __str__(self):
        return f"{self.document} — Версия {self.version}"

    def save(self, *args, **kwargs):
        if not self.version:
            last_version = DocumentVersion.objects.filter(document=self.document).order_by('-version').first()
            self.version = 1 if not last_version else last_version.version + 1
        super().save(*args, **kwargs)
