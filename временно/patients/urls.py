from django.urls import path, include
from rest_framework.routers import DefaultRouter
from .views import (
    PatientViewSet,
    VisitViewSet,
    PatientNoteViewSet,
    TreatmentTypeOptionViewSet,
    CapSystemOptionViewSet,
)

router = DefaultRouter()
router.register(r'visits', VisitViewSet, basename='visit')
router.register(r'notes', PatientNoteViewSet, basename='patient-note')
router.register(r'treatment-types', TreatmentTypeOptionViewSet, basename='treatment-type-option')
router.register(r'cap-systems', CapSystemOptionViewSet, basename='cap-system-option')
router.register('', PatientViewSet, basename='patient')

urlpatterns = [
    path('', include(router.urls)),
]