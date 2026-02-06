from django.urls import path
from . import views

app_name = 'documentflow'

urlpatterns = [
    path('', views.login_page, name='login'),
    path('password-change/', views.password_change_page, name='password_change_page'),
    path('dashboard/', views.dashboard, name='dashboard'),
    path('documents/create/', views.sending_document_page, name='sending_document_page'),
    path('documents/incoming/', views.incoming_documents_page, name='incoming_documents_page'),
    path('documents/outgoing/', views.outgoing_documents_page, name='outgoing_documents_page'),
    path('documents/drafts/', views.drafts_documents_page, name='drafts_documents_page'),
    path('documents/archive/', views.archive_documents_page, name='archive_documents_page'),
    path('profile/', views.profile_page, name='profile_page'),
    path('replacements/', views.replacements_page, name='replacements_page'),
    path('stats/', views.stats_page, name='stats_page'),
]
