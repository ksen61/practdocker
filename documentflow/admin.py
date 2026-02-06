from django import forms
from django.contrib import admin, messages
from django.contrib.auth.admin import UserAdmin as BaseUserAdmin
from django.conf import settings
from django.core.mail import EmailMultiAlternatives
from django.utils.html import strip_tags
from django.utils.crypto import get_random_string
from .models import *

# ================== Роли ==================
@admin.register(Role)
class RoleAdmin(admin.ModelAdmin):
    list_display = ['name']
    search_fields = ['name']


# ================== Пользователи ==================
@admin.register(User)
class UserAdmin(BaseUserAdmin):
    class UserCreationAutoPasswordForm(forms.ModelForm):
        class Meta:
            model = User
            fields = ('username', 'email', 'first_name', 'last_name', 'middle_name', 'position', 'department', 'role')

        def save(self, commit=True):
            user = super().save(commit=False)
            if commit:
                user.save()
            return user

    add_form = UserCreationAutoPasswordForm

    list_display = ['username', 'email', 'full_name', 'role', 'position', 'department', 'status', 'is_staff']
    list_filter = ['role', 'status', 'is_staff', 'is_superuser']
    search_fields = ['username', 'email', 'first_name', 'last_name', 'middle_name', 'position', 'department']
    ordering = ['last_name', 'first_name']
    fieldsets = (
        (None, {'fields': ('username', 'password')}),
        ('Личная информация', {'fields': ('first_name', 'last_name', 'middle_name', 'email', 'phone', 'room')}),
        ('Работа', {'fields': ('role', 'position', 'department', 'status')}),
        ('Права доступа', {'fields': ('is_active', 'is_staff', 'is_superuser', 'groups', 'user_permissions')}),
        ('Даты', {'fields': ('last_login', 'date_joined')}),
    )
    add_fieldsets = (
        (None, {
            'classes': ('wide',),
            'fields': ('username', 'email', 'first_name', 'last_name', 'middle_name', 'position', 'department', 'role')}
        ),
    )

    def save_model(self, request, obj, form, change):
        is_new = obj.pk is None
        raw_password = None
        if is_new:
            raw_password = form.cleaned_data.get('password1')
            if not raw_password:
                raw_password = get_random_string(12)
            obj.set_password(raw_password)
            obj.must_change_password = True

        super().save_model(request, obj, form, change)

        if not is_new:
            return

        if not obj.email:
            messages.warning(request, 'Письмо не отправлено: у сотрудника не указан email.')
            return

        subject = 'Доступ в DocumentFlow'
        login_url = request.build_absolute_uri("/")
        html_message = f"""
        <div style="font-family: Arial, sans-serif; background:#f6f7fb; padding:24px;">
            <div style="max-width:640px; margin:0 auto; background:#ffffff; border-radius:14px; border:1px solid #e6e8ef; overflow:hidden;">
                <div style="padding:18px 22px; background:#0f766e;">
                    <div style="color:#ffffff; font-size:18px; font-weight:700;">DocumentFlow</div>
                    <div style="color:#d1fae5; font-size:12px;">Учетная запись сотрудника</div>
                </div>
                <div style="padding:22px;">
                    <p style="margin:0 0 10px 0; color:#111827; font-size:14px;">Здравствуйте!</p>
                    <p style="margin:0 0 16px 0; color:#374151; font-size:13px;">
                        Для вас создан аккаунт в системе DocumentFlow. Ниже — данные для входа.
                    </p>
                    <div style="border:1px solid #e5e7eb; border-radius:10px; padding:14px; background:#f9fafb;">
                        <div style="margin-bottom:6px; color:#6b7280; font-size:11px; text-transform:uppercase; letter-spacing:0.08em;">Логин</div>
                        <div style="font-size:14px; font-weight:700; color:#111827;">{obj.username}</div>
                        <div style="margin:12px 0 6px 0; color:#6b7280; font-size:11px; text-transform:uppercase; letter-spacing:0.08em;">Пароль</div>
                        <div style="font-size:14px; font-weight:700; color:#111827;">{raw_password}</div>
                    </div>
                    <div style="margin-top:18px;">
                        <a href="{login_url}" style="display:inline-block; background:#0f766e; color:#ffffff; text-decoration:none; padding:10px 16px; border-radius:8px; font-size:13px;">
                            Войти в систему
                        </a>
                    </div>
                    <p style="margin:16px 0 0 0; color:#6b7280; font-size:12px;">
                        Рекомендуем изменить пароль после первого входа.
                    </p>
                </div>
                <div style="padding:12px 22px; background:#f3f4f6; color:#9ca3af; font-size:11px;">
                    Это письмо отправлено автоматически, отвечать на него не нужно.
                </div>
            </div>
        </div>
        """
        message = strip_tags(html_message)
        try:
            email = EmailMultiAlternatives(
                subject=subject,
                body=message,
                from_email=getattr(settings, 'DEFAULT_FROM_EMAIL', None),
                to=[obj.email],
            )
            email.attach_alternative(html_message, "text/html")
            email.send(fail_silently=False)
            messages.success(request, f'Письмо с доступом отправлено на {obj.email}.')
        except Exception as exc:
            messages.error(request, f'Не удалось отправить письмо: {exc}')


# ================== Типы и статусы документов ==================
@admin.register(DocumentType)
class DocumentTypeAdmin(admin.ModelAdmin):
    list_display = ['name', 'code', 'description']
    search_fields = ['name', 'code']


@admin.register(DocumentStatus)
class DocumentStatusAdmin(admin.ModelAdmin):
    list_display = ['name', 'color', 'is_final']
    list_filter = ['is_final']
    search_fields = ['name']


# ================== Файлы документов ==================
class DocumentFileInline(admin.TabularInline):
    model = DocumentFile
    extra = 1
    readonly_fields = ['file_name', 'file_size', 'file_type', 'uploaded_at', 'uploaded_by']


# ================== Согласования ==================
class ApprovalInline(admin.TabularInline):
    model = Approval
    extra = 1
    readonly_fields = ['created_at', 'decided_at']


# ================== Получатели ==================
class DocumentRecipientInline(admin.TabularInline):
    model = DocumentRecipient
    extra = 1
    readonly_fields = ['received_at', 'completed_at']


# ================== Документы ==================
@admin.register(Document)
class DocumentAdmin(admin.ModelAdmin):
    list_display = ['registration_number', 'title', 'document_type', 'status', 'author', 'responsible', 'deadline', 'is_archived', 'priority']
    list_filter = ['document_type', 'status', 'priority', 'is_archived']
    search_fields = ['registration_number', 'title', 'author__username', 'responsible__username', 'correspondent', 'external_number']
    ordering = ['-created_at']
    inlines = [DocumentFileInline, ApprovalInline, DocumentRecipientInline]


# ================== Замены сотрудников ==================
@admin.register(Replacement)
class ReplacementAdmin(admin.ModelAdmin):
    list_display = ['absent_employee', 'replacement_employee', 'reason', 'start_date', 'end_date', 'is_active', 'created_by']
    list_filter = ['reason', 'is_active']
    search_fields = ['absent_employee__username', 'replacement_employee__username']
    ordering = ['-start_date']


# ================== Уведомления ==================
@admin.register(Notification)
class NotificationAdmin(admin.ModelAdmin):
    list_display = ['user', 'title', 'notification_type', 'is_read', 'created_at']
    list_filter = ['notification_type', 'is_read']
    search_fields = ['user__username', 'title', 'text']
    ordering = ['-created_at']


# ================== Журнал действий ==================
@admin.register(ActionLog)
class ActionLogAdmin(admin.ModelAdmin):
    list_display = ['user', 'document', 'action', 'timestamp', 'ip_address']
    list_filter = ['action']
    search_fields = ['user__username', 'document__registration_number', 'description']
    ordering = ['-timestamp']


# ================== Комментарии ==================
@admin.register(Comment)
class CommentAdmin(admin.ModelAdmin):
    list_display = ['document', 'author', 'created_at', 'is_internal']
    list_filter = ['is_internal']
    search_fields = ['document__registration_number', 'author__username', 'text']
    ordering = ['-created_at']


# ================== Настройки системы ==================
@admin.register(SystemSettings)
class SystemSettingsAdmin(admin.ModelAdmin):
    list_display = ['key', 'value', 'updated_at']
    search_fields = ['key', 'value']
    ordering = ['key']


from .models import Department

@admin.register(Department)
class DepartmentAdmin(admin.ModelAdmin):
    list_display = ['name']
    search_fields = ['name']

# ================== Шаблоны документов ==================
@admin.register(DocumentTemplate)
class DocumentTemplateAdmin(admin.ModelAdmin):
    list_display = ['name', 'document_type', 'is_active', 'created_at']
    list_filter = ['document_type', 'is_active']
    search_fields = ['name']
    ordering = ['name']

from django.contrib import admin
from .models import DocumentRouteTemplate, DocumentRouteStep
from .forms import DocumentRouteStepForm  # <-- импортируем форму

class DocumentRouteStepInline(admin.TabularInline):
    model = DocumentRouteStep
    extra = 1
    form = DocumentRouteStepForm
    fields = ['step_number', 'user', 'department']
    autocomplete_fields = ['user', 'department']
    readonly_fields = []

# admin.py
@admin.register(DocumentRouteTemplate)
class DocumentRouteTemplateAdmin(admin.ModelAdmin):
    list_display = ['name', 'document_type', 'is_active', 'approval_order']
    list_filter = ['document_type', 'is_active', 'approval_order']
    search_fields = ['name']
    ordering = ['name']
    inlines = [DocumentRouteStepInline]





# ================== Версии документов ==================
@admin.register(DocumentVersion)
class DocumentVersionAdmin(admin.ModelAdmin):
    list_display = ['document', 'version', 'created_at', 'created_by']
    ordering = ['document', '-version']
    readonly_fields = ['version', 'created_at']
