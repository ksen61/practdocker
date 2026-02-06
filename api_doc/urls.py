from django.urls import path, include
from rest_framework.routers import DefaultRouter
from .views import (
    DepartmentViewSet,
    DocumentTypeListAPIView,
    UserListAPIView,
    DepartmentListAPIView,
    DocumentStatusListAPIView,
    DocumentRouteListAPIView,
    DocumentListCreateAPIView,
    DocumentRetrieveUpdateDestroyAPIView,
    DocumentFileCreateAPIView,
    IncomingDocumentsAPIView,
    MyDocumentsAPIView,
    DocumentApprovalViewSet,
    DocumentRouteViewSet,
    LoginAPIView,
    LogoutAPIView,
    CheckAuthAPIView,
    ChangePasswordAPIView,
    RequestEmailChangeAPIView,
    ConfirmEmailChangeAPIView,
    ResendEmailChangeCodeAPIView,
    ReplacementSelfAPIView,
    MeAPIView,
    DocumentHistoryAPIView,
    DashboardStatsAPIView,
    NotificationsAPIView,
    MarkAllNotificationsReadAPIView,
    MarkNotificationReadAPIView,
)
from drf_yasg.views import get_schema_view
from drf_yasg import openapi
from rest_framework import permissions

schema_view = get_schema_view(
    openapi.Info(
        title="DocumentFlow API",
        default_version='v1',
        description="API для системы документооборота",
        terms_of_service="https://www.google.com/policies/terms/",
        contact=openapi.Contact(email="support@documentflow.local"),
        license=openapi.License(name="BSD License"),
    ),
    public=True,
    permission_classes=(permissions.AllowAny,),
)
router = DefaultRouter()
router.register(r'departments', DepartmentViewSet, basename='department')
router.register(r'routes', DocumentRouteViewSet, basename='route')

urlpatterns = [
    path('swagger/', schema_view.with_ui('swagger', cache_timeout=0), name='schema-swagger-ui'),
    # Router endpoints
    path('', include(router.urls)),
    path('login/', LoginAPIView, name='login'),
    path('logout/', LogoutAPIView, name='logout'),
    path('check-auth/', CheckAuthAPIView, name='check-auth'),
    path('password-change/', ChangePasswordAPIView, name='password-change'),
    path('email-change/request/', RequestEmailChangeAPIView, name='email-change-request'),
    path('email-change/confirm/', ConfirmEmailChangeAPIView, name='email-change-confirm'),
    path('email-change/resend/', ResendEmailChangeCodeAPIView, name='email-change-resend'),
    path('replacements/self/', ReplacementSelfAPIView, name='replacements-self'),
    path('me/', MeAPIView, name='me'),

    # Document Type
    path('document-types/', DocumentTypeListAPIView.as_view(), name='document-type-list'),

    # Users & Departments
    path('users/', UserListAPIView.as_view(), name='user-list'),
    path('departments/', DepartmentListAPIView.as_view(), name='department-list'),

    # Document Statuses
    path('document-statuses/', DocumentStatusListAPIView.as_view(), name='document-status-list'),

    # Routes
    path('routes/', DocumentRouteListAPIView.as_view(), name='route-list'),

    # Documents CRUD
    path('documents/', DocumentListCreateAPIView.as_view(), name='document-list-create'),
    path('documents/<int:pk>/', DocumentRetrieveUpdateDestroyAPIView.as_view(), name='document-detail'),
    path('documents/<int:pk>/files/', DocumentFileCreateAPIView.as_view(), name='document-file-create'),
    path('documents/<int:pk>/approve/', DocumentApprovalViewSet.as_view({'post': 'approve'}), name='document-approve'),
    path('documents/<int:pk>/reject/', DocumentApprovalViewSet.as_view({'post': 'reject'}), name='document-reject'),
    path('documents/<int:pk>/acknowledge/', DocumentApprovalViewSet.as_view({'post': 'acknowledge'}), name='document-acknowledge'),
    path('documents/<int:pk>/execute/', DocumentApprovalViewSet.as_view({'post': 'execute'}), name='document-execute'),
    path('documents/<int:pk>/return/', DocumentApprovalViewSet.as_view({'post': 'return_to_author'}), name='document-return'),
    path('documents/<int:pk>/resubmit/', DocumentApprovalViewSet.as_view({'post': 'resubmit'}), name='document-resubmit'),
    path('documents/<int:pk>/archive/', DocumentApprovalViewSet.as_view({'post': 'archive'}), name='document-archive'),
    path('documents/<int:pk>/unarchive/', DocumentApprovalViewSet.as_view({'post': 'unarchive'}), name='document-unarchive'),
    path('documents/<int:pk>/history/', DocumentHistoryAPIView, name='document-history'),
    path('dashboard/stats/', DashboardStatsAPIView, name='dashboard-stats'),
    path('notifications/', NotificationsAPIView, name='notifications'),
    path('notifications/mark-all-read/', MarkAllNotificationsReadAPIView, name='notifications-mark-all-read'),
    path('notifications/<int:pk>/read/', MarkNotificationReadAPIView, name='notification-mark-read'),

    # Incoming & My Documents
    path('documents/incoming/', IncomingDocumentsAPIView.as_view(), name='incoming-documents'),
    path('documents/my/', MyDocumentsAPIView.as_view(), name='my-documents'),
]
