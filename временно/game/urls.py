from django.urls import path, include
from rest_framework.routers import DefaultRouter
from .views import (
    PatientInfoViewSet,
    DocumentViewSet,
    PatientSettingsViewSet,
    PatientAvatarViewSet,
    VideoViewSet,
    TaskViewSet,
    ParentTaskViewSet,
    RewardViewSet,
    PatientTreatmentViewSet,
    AuthViewSet,
    SosAlertViewSet,
)

router = DefaultRouter()
router.register(r'auth', AuthViewSet, basename='auth')
router.register(r'info', PatientInfoViewSet, basename='patient-info')
router.register(r'document', DocumentViewSet, basename='documents')
router.register(r'settings', PatientSettingsViewSet, basename='patient-settings')
router.register(r'avatar', PatientAvatarViewSet, basename='patient-avatar')
router.register(r'video', VideoViewSet, basename='patient-video')
router.register(r'task', TaskViewSet, basename='patient-task')
router.register(r'parent-task', ParentTaskViewSet, basename='parent-task')
router.register(r'shop', RewardViewSet, basename='patient-reward')
router.register(r'treatment', PatientTreatmentViewSet, basename='patient-treatment')
router.register(r'alerts', SosAlertViewSet, basename='patient-alerts')

urlpatterns = [
    path('', include(router.urls))
]