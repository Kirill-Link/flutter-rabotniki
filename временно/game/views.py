import uuid
from datetime import date

from django.contrib.auth.hashers import check_password
from django.core.cache import cache
from django.db.models import OuterRef, Exists
from django.db import transaction
from django.utils.crypto import get_random_string
from rest_framework.decorators import action
from rest_framework.exceptions import NotFound
from rest_framework.response import Response
from rest_framework.status import HTTP_400_BAD_REQUEST, HTTP_404_NOT_FOUND
from rest_framework.throttling import AnonRateThrottle
from rest_framework.views import APIView
from rest_framework import status, serializers
from rest_framework.permissions import IsAuthenticated, AllowAny
from rest_framework.viewsets import ViewSet, GenericViewSet, ReadOnlyModelViewSet
from rest_framework_simplejwt.tokens import RefreshToken, AccessToken

from patients.models import Patient, Document, Visit, Parent
from patients.serializers import VisitSerializer

from .models import (
    CatAvatar,
    AvatarVideo,
    VideoItem,
    SettingItem,
    AvatarSetting,
    RewardItem,
    TaskItem,
    AvatarTask,
    AvatarReward,
    AvatarSosAlert,
)
from .schema import PatientJWTAuthenticationScheme
from .authentication import PatientJWTAuthentication, ParentJWTAuthentication
from .permissions import IsPatient, IsParent
from .serializers import (
    PatientQRLoginResponseSerializer,
    ParentInfoSerializer,
    DoctorInfoSerializer,
    PatientInfoSerializer,
    DocumentSerializer,
    PatientSettingSerializer,
    UpdateSettingSerializer,
    PatientAvatarSerializer,
    VideoListSerializer,
    TaskListSerializer,
    RewardListSerializer,
    PatientTreatmentProgressSerializer,
    AlignerUpdateSerializer,
    SosAlertSerializer, ParentLoginSerializer,
)

from drf_spectacular.utils import extend_schema, inline_serializer, OpenApiParameter
from drf_spectacular.types import OpenApiTypes

from patients.serializers import ParentChangePasswordSerializer


class AuthViewSet(GenericViewSet):
    permission_classes = [AllowAny]

    @extend_schema(
        parameters=[
            OpenApiParameter(
                name='uuid_val',
                type=OpenApiTypes.STR,
                location=OpenApiParameter.PATH,
                description='UUID из QR-кода',
                required=True
            )
        ],
        summary="Получение инфы по QR(Первый этап)",
        responses={200: inline_serializer(
            name='QRInfoResponse',
            fields={
                "status": serializers.CharField(),
                "profiles": serializers.ListField(child=serializers.DictField())
            }
        )},
        auth=[]
    )
    @action(detail=False, methods=['get'], url_path='qr-info/(?P<uuid_val>[^/.]+)')
    def qr_info(self, request, uuid_val=None):
        try:
            target_uuid = uuid.UUID(uuid_val)
            patient = Patient.objects.get(external_id=target_uuid)

            temp_token = get_random_string(32)

            cache.set(
                f'qr_temp:{temp_token}',
                {
                    'patient_id': patient.id,
                    'external_id': str(target_uuid),
                    'first_name': patient.first_name,
                },
                timeout=300
            )

            return Response({
                'temp_token': temp_token,
                'patient_name': patient.first_name,
                'expires_in': 300
            })
        except (ValueError, Patient.DoesNotExist):
            return Response({'error': 'Invalid QR'}, status=HTTP_404_NOT_FOUND)

    @extend_schema(
        summary="Вход ребенка по временному токену из QR",
        request=inline_serializer(
            name='QRLoginRequest',
            fields={"temp_token": serializers.CharField()}
        ),
        responses={200: inline_serializer(
            name='TokenResponse',
            fields={
                "access": serializers.CharField(),
                "refresh": serializers.CharField(),
                "role": serializers.CharField()
            }
        )}
    )
    @action(detail=False, methods=['post'], url_path='qr-login')
    def qr_login(self, request):
        temp_token = request.data.get('temp_token')
        if not temp_token:
            return Response({'error': 'temp_token required'}, status=HTTP_400_BAD_REQUEST)

        qr_data = cache.get(f'qr_temp:{temp_token}')
        if not qr_data:
            return Response({'error': 'QR session expired'}, status=HTTP_400_BAD_REQUEST)

        cache.delete(f'qr_temp:{temp_token}')

        patient = Patient.objects.get(id=qr_data['patient_id'])

        refresh = RefreshToken()
        refresh['patient_id'] = qr_data['patient_id']
        refresh['role'] = 'patient'
        refresh['external_id'] = qr_data['external_id']

        return Response({
            'access': str(refresh.access_token),
            'refresh': str(refresh),
            'role': 'patient',
            'account_type': getattr(patient, 'account_type', 'child'),
        })

    @extend_schema(
        summary="Вход для родителя по телефону и паролю",
        request=ParentLoginSerializer,
        responses={200: inline_serializer(
            name='ParentLoginResponse',
            fields={
                "parent_name": serializers.CharField(),
                "children": serializers.ListField(child=serializers.DictField())
            }
        )}
    )
    @action(detail=False, methods=['post'], url_path='parent-login')
    def parent_login(self, request):
        serializer = ParentLoginSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)

        phone = serializer.validated_data['phone']
        password = serializer.validated_data['password']

        try:
            parent = Parent.objects.get(phone=phone)
        except Parent.DoesNotExist:
            return Response({'error': 'Неверный телефон'}, status=status.HTTP_401_UNAUTHORIZED)

        if not check_password(password, parent.password):
            return Response({'error': 'Неверный пароль'}, status=status.HTTP_401_UNAUTHORIZED)

        children_data = []

        for child in parent.children.all():

            if child.status == 'archived':
                continue

            refresh = RefreshToken()
            refresh['patient_id'] = child.id
            refresh['role'] = 'parent'
            refresh['external_id'] = str(child.external_id)

            children_data.append({
                'patient_id': child.id,
                'first_name': child.first_name,
                'last_name': child.last_name,
                'access': str(refresh.access_token),
                'refresh': str(refresh),
            })

        if not children_data:
            return Response({'error': 'Нет активных пациентов'}, status=status.HTTP_404_NOT_FOUND)

        return Response({
            'parent_name': f"{parent.first_name} {parent.last_name}".strip(),
            'children': children_data
        }, status=status.HTTP_200_OK)

    @action(detail=False, methods=['get'], url_path='parent-children',
            authentication_classes=[ParentJWTAuthentication],
            permission_classes=[IsParent])
    def parent_children(self, request):
        patient = Patient.objects.get(id=request.user.id)
        parent = patient.parent
        children_data = []

        for child in parent.children.all():
            if child.status == 'archived':
                continue

            refresh = RefreshToken()
            refresh['patient_id'] = child.id
            refresh['role'] = 'parent'
            refresh['external_id'] = str(child.external_id)

            children_data.append({
                'patient_id': child.id,
                'first_name': child.first_name,
                'last_name': child.last_name,
                'is_current': child.id == patient.id,
                'access': str(refresh.access_token),
                'refresh': str(refresh),
            })

        return Response({'children': children_data}, status=status.HTTP_200_OK)

    @action(detail=False, methods=['post'], url_path='change-password',
            authentication_classes=[ParentJWTAuthentication],
            permission_classes=[IsParent])
    def change_password(self, request):
        patient = Patient.objects.get(id=request.user.id)
        parent = patient.parent
        serializer = ParentChangePasswordSerializer(data=request.data)

        if serializer.is_valid():
            if not parent.check_password(serializer.data.get('old_password')):
                return Response(
                    {"old_password": ["Неверный старый пароль."]},
                    status=status.HTTP_400_BAD_REQUEST
                )

            parent.set_password(serializer.data.get('new_password'))
            parent.save()

            return Response({"message": "Пароль успешно изменен."}, status=status.HTTP_200_OK)

        return Response(serializer.errors, status=status.HTTP_400_BAD_REQUEST)


class PatientInfoViewSet(GenericViewSet):
    serializer_class = PatientInfoSerializer
    queryset = Patient.objects.all()
    authentication_classes = [PatientJWTAuthentication]
    permission_classes = [IsPatient]

    def get_object(self):
        try:
            return Patient.objects.get(id=self.request.user.id)
        except Patient.DoesNotExist:
            raise NotFound("Patient not found")

    @action(detail=False, methods=['get', 'patch'], url_path='parent')
    def parent_info(self, request):
        patient = self.get_object()

        if request.method == 'GET':
            serializer = ParentInfoSerializer(patient.parent)
            return Response(serializer.data)

        serializer = ParentInfoSerializer(patient.parent, data=request.data, partial=True)
        if serializer.is_valid():
            serializer.save()
            return Response(serializer.data)
        return Response(serializer.errors, status=status.HTTP_400_BAD_REQUEST)

    @action(detail=False, methods=['get', 'patch'], url_path='patient')
    def patient_info(self, request):
        patient = self.get_object()
        if request.method == 'GET':
            serializer = PatientInfoSerializer(patient)
            return Response(serializer.data)

        serializer = PatientInfoSerializer(patient, data=request.data, partial=True)
        if serializer.is_valid():
            serializer.save()
            return Response(serializer.data)
        return Response(serializer.errors, status=status.HTTP_400_BAD_REQUEST)

    @action(detail=False, methods=['get'], url_path='doctor')
    def doctor_info(self, request):
        patient = self.get_object()

        serializer = DoctorInfoSerializer(patient.doctor)
        return Response(serializer.data)

class DocumentViewSet(ReadOnlyModelViewSet):
    queryset = Document.objects.all()
    serializer_class = DocumentSerializer
    permission_classes = [AllowAny]

    @extend_schema(auth=[])
    def list(self, request, *args, **kwargs):
        return super().list(request, *args, **kwargs)

    @extend_schema(auth=[])
    def retrieve(self, request, *args, **kwargs):
        return super().retrieve(request, *args, **kwargs)

class PatientSettingsViewSet(GenericViewSet):
    permission_classes = [IsPatient]
    authentication_classes = [PatientJWTAuthentication]
    serializer_class = PatientSettingSerializer

    def get_avatar(self):
        patient_id = self.request.user.id
        try:
            patient = Patient.objects.get(id=patient_id)
            return patient.avatar
        except Patient.DoesNotExist:
            from rest_framework.exceptions import NotFound
            raise NotFound("Пациент не найден")
        except CatAvatar.DoesNotExist:
            from rest_framework.exceptions import NotFound
            raise NotFound("Аватар не найден")

    @extend_schema(
        responses={200: PatientSettingSerializer(many=True)},
        description="Получить список всех настроек аватара"
    )
    def list(self, request):
        cat = self.get_avatar()

        has_setting = AvatarSetting.objects.filter(
            avatar=cat,
            setting_item=OuterRef('pk'),
            is_enabled=True
        )

        setting_qs = SettingItem.objects.annotate(
            is_enabled=Exists(has_setting)
        )

        serializer = PatientSettingSerializer(setting_qs, many=True)
        return Response(serializer.data)

    @extend_schema(
        request=UpdateSettingSerializer,
        responses={200: inline_serializer(
            name='UpdateSettingResponse',
            fields={
                "status": serializers.CharField(),
                "is_enabled": serializers.BooleanField()
            }
        )},
        description="Включение/выключение настройки аватара (уши, хвост и т.д.)"
    )
    @action(detail=False, methods=['post'], url_path='update')
    def update_setting(self, request):
        serializer = UpdateSettingSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)

        cat = self.get_avatar()
        setting_id = serializer.validated_data['setting_id']
        enabled = serializer.validated_data['enable']

        obj, _ = AvatarSetting.objects.update_or_create(
            avatar=cat,
            setting_item_id=setting_id,
            defaults={'is_enabled': enabled}
        )

        return Response({
            "status": "success",
            "is_enabled": obj.is_enabled
        }, status=status.HTTP_200_OK)


class PatientAvatarViewSet(GenericViewSet):
    permission_classes = [IsPatient]
    authentication_classes = [PatientJWTAuthentication]
    serializer_class = PatientAvatarSerializer

    def get_object(self):
        try:
            patient_id = self.request.user.id
            instance = CatAvatar.objects.filter(patient_id=patient_id).first()

            return instance
        except (Patient.DoesNotExist, CatAvatar.DoesNotExist, AttributeError):
            raise NotFound(detail='Аватар не найден')

    def list(self, request, *args, **kwargs):
        instance = self.get_object()
        serializer = self.get_serializer(instance)
        return Response(serializer.data)

    @action(detail=False, methods=['PATCH'], url_path='update-aligner')
    def update_aligner(self, request):
        instance = self.get_object()
        serializer = AlignerUpdateSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)

        instance.aligner = serializer.validated_data['aligner']
        instance.save(update_fields=['aligner'])

        return Response(
            PatientAvatarSerializer(instance).data,
            status=status.HTTP_200_OK
        )


class VideoViewSet(ReadOnlyModelViewSet):
    serializer_class = VideoListSerializer
    permission_classes = [IsPatient]
    authentication_classes = [PatientJWTAuthentication]
    queryset = VideoItem.objects.all()

    def get_avatar(self):
        patient_id = self.request.user.id
        return CatAvatar.objects.filter(patient_id=patient_id).first()

    def get_queryset(self):
        cat = self.get_avatar()
        if not cat:
            return VideoItem.objects.none()

        has_watched = AvatarVideo.objects.filter(
            avatar=cat,
            video=OuterRef('pk'),
            is_completed=True
        )

        return VideoItem.objects.filter(status=True).annotate(
            is_watched_by_user=Exists(has_watched)
        ).order_by('unlock_day')

    @extend_schema(request=None)
    @action(detail=True, methods=['post'], url_path='complete')
    def mark_complete(self, request, pk=None):
        video = self.get_object()
        cat = self.get_avatar()

        if not cat:
            return Response({"error": "Avatar not found"}, status=404)

        if cat.play_day < video.unlock_day:
            return Response({
                "error": "Not allowed yet"
            }, status=status.HTTP_403_FORBIDDEN)

        with transaction.atomic():
            video_progress, created = AvatarVideo.objects.get_or_create(
                avatar=cat,
                video=video
            )

            if not video_progress.is_completed:
                video_progress.is_completed = True
                video_progress.save()

                cat.coin_balance += video.coin_reward
                cat.xp_balance += video.xp_reward
                cat.save()

                return Response({
                    "status": "success",
                    "reward_coins": video.coin_reward,
                    "new_balance": cat.coin_balance
                }, status=status.HTTP_200_OK)

            return Response({
                "detail": "Already get reward"
            }, status=status.HTTP_400_BAD_REQUEST)


class TaskViewSet(ReadOnlyModelViewSet):
    serializer_class = TaskListSerializer
    permission_classes = [IsPatient]
    authentication_classes = [PatientJWTAuthentication]
    queryset = TaskItem.objects.all()

    def get_avatar(self):
        return CatAvatar.objects.filter(patient_id=self.request.user.id).first()

    def get_queryset(self):
        cat = self.get_avatar()
        if not cat:
            return TaskItem.objects.none()

        completed_subquery = AvatarTask.objects.filter(
            avatar=cat,
            task=OuterRef('pk'),
            is_completed=True
        )
        read_subquery = AvatarTask.objects.filter(
            avatar=cat,
            task=OuterRef('pk'),
            is_read=True
        )
        return TaskItem.objects.filter(
            status=True,
            patient_type=cat.patient.account_type
        ).annotate(
            is_completed_by_user=Exists(completed_subquery),
            is_read_by_user=Exists(read_subquery)
        ).order_by('unlock_day')

    @extend_schema(request=None)
    @action(detail=True, methods=['post'], url_path='complete')
    def complete_task(self, request, pk=None):
        task = self.get_object()
        cat = self.get_avatar()

        if not cat: return Response({"error": "Avatar not found"}, status=404)

        if cat.play_day < task.unlock_day:
            return Response({
                "error": "Not allowed yet"
            }, status=status.HTTP_403_FORBIDDEN)

        with transaction.atomic():
            task_progress, created = AvatarTask.objects.get_or_create(
                avatar=cat,
                task=task
            )

            if not task_progress.is_completed:
                task_progress.is_completed = True
                task_progress.save()

                cat.coin_balance += task.coin_reward
                cat.xp_balance += task.xp_reward
                cat.save()

                return Response({
                    "status": "success",
                    "new_balance": cat.coin_balance,
                    "new_xp": cat.xp_balance
                }, status=status.HTTP_200_OK)

            return Response({
                "detail": "Already completed"
            }, status=status.HTTP_400_BAD_REQUEST)

    @extend_schema(
        request=None,
        responses={200: inline_serializer(
            name='MarkTasksReadResponse',
            fields={"status": serializers.CharField()}
        )},
        description="Пометить все задания как прочитанные в уведомлениях для текущего аватара"
    )
    @action(detail=False, methods=['post'], url_path='mark-read')
    def mark_read(self, request):
        cat = self.get_avatar()
        if not cat:
            return Response({"error": "Avatar not found"}, status=status.HTTP_404_NOT_FOUND)

        tasks_qs = TaskItem.objects.filter(
            status=True,
            patient_type=cat.patient.account_type
        )

        with transaction.atomic():
            for task in tasks_qs:
                AvatarTask.objects.update_or_create(
                    avatar=cat,
                    task=task,
                    defaults={'is_read': True}
                )

        return Response({"status": "success"}, status=status.HTTP_200_OK)


class ParentTaskViewSet(ReadOnlyModelViewSet):
    """
    Отдельный вьюсет для родителя, чтобы он тоже мог:
    - получать список заданий ребёнка;
    - помечать их как прочитанные в уведомлениях.
    """

    serializer_class = TaskListSerializer
    permission_classes = [IsParent]
    authentication_classes = [ParentJWTAuthentication]
    queryset = TaskItem.objects.all()

    def get_avatar(self):
        """
        Находим аватар по patient_id, который пришёл в PARENT‑токене.
        """
        patient_id = getattr(self.request.user, "id", None)
        if not patient_id:
            return None
        return CatAvatar.objects.filter(patient_id=patient_id).first()

    def get_queryset(self):
        cat = self.get_avatar()
        if not cat:
            return TaskItem.objects.none()

        completed_subquery = AvatarTask.objects.filter(
            avatar=cat,
            task=OuterRef('pk'),
            is_completed=True
        )
        read_subquery = AvatarTask.objects.filter(
            avatar=cat,
            task=OuterRef('pk'),
            is_read=True
        )
        return TaskItem.objects.filter(
            status=True,
            patient_type=cat.patient.account_type
        ).annotate(
            is_completed_by_user=Exists(completed_subquery),
            is_read_by_user=Exists(read_subquery)
        ).order_by('unlock_day')

    @extend_schema(
        request=None,
        responses={200: inline_serializer(
            name='ParentMarkTasksReadResponse',
            fields={"status": serializers.CharField()}
        )},
        description="Родитель помечает все задания ребёнка как прочитанные в уведомлениях"
    )
    @action(detail=False, methods=['post'], url_path='mark-read')
    def mark_read(self, request):
        cat = self.get_avatar()
        if not cat:
            return Response({"error": "Avatar not found"}, status=status.HTTP_404_NOT_FOUND)

        tasks_qs = TaskItem.objects.filter(
            status=True,
            patient_type=cat.patient.account_type
        )

        with transaction.atomic():
            for task in tasks_qs:
                AvatarTask.objects.update_or_create(
                    avatar=cat,
                    task=task,
                    defaults={'is_read': True}
                )

        return Response({"status": "success"}, status=status.HTTP_200_OK)

class RewardViewSet(ReadOnlyModelViewSet):
    serializer_class = RewardListSerializer
    permission_classes = [IsPatient]
    authentication_classes = [PatientJWTAuthentication]
    queryset = RewardItem.objects.none()

    def get_avatar(self):
        return CatAvatar.objects.filter(patient_id=self.request.user.id).first()

    def get_queryset(self):
        cat = self.get_avatar()
        if not cat: return RewardItem.objects.none()

        return RewardItem.objects.filter(is_active=True).annotate(
            is_bought=Exists(AvatarReward.objects.filter(
                avatar=cat,
                reward=OuterRef('pk')
            )),
            is_equipped=Exists(AvatarReward.objects.filter(
                avatar=cat,
                reward=OuterRef('pk'),
                is_equipped=True
            ))
        ).order_by('coin_cost')

    @action(detail=True, methods=['post'], url_path='buy')
    def buy_item(self, request, pk=None):
        reward = self.get_object()
        cat = self.get_avatar()

        if AvatarReward.objects.filter(avatar=cat, reward=reward).exists():
            return Response({"error": "Already bought"}, status=status.HTTP_400_BAD_REQUEST)

        if cat.coin_balance < reward.coin_cost:
            return Response({"error": "Not enough coins"}, status=status.HTTP_400_BAD_REQUEST)

        with transaction.atomic():
            cat.coin_balance -= reward.coin_cost
            cat.xp_balance -= reward.xp_cost
            cat.save()

            AvatarReward.objects.create(avatar=cat, reward=reward, is_equipped=False)

            return Response({"status": "success", "balance": cat.coin_balance}, status=status.HTTP_200_OK)

    @extend_schema(request=None)
    @action(detail=True, methods=['post'], url_path='equip')
    def equip_item(self, request, pk=None):
        reward = self.get_object()
        cat = self.get_avatar()

        try:
            inventory_item = AvatarReward.objects.get(avatar=cat, reward=reward)
        except AvatarReward.DoesNotExist:
            return Response(
                {"error": "Сначала нужно купить этот предмет"},
                status=status.HTTP_400_BAD_REQUEST
            )

        with transaction.atomic():
            if inventory_item.is_equipped:
                inventory_item.is_equipped = False
                inventory_item.save()
                return Response({"status": "unequipped", "is_equipped": False})


            AvatarReward.objects.filter(
                avatar=cat,
                is_equipped=True
            ).update(is_equipped=False)

            inventory_item.is_equipped = True
            inventory_item.save()

        return Response({
            "status": "equipped",
            "item_id": reward.id,
            "is_equipped": True
        }, status=status.HTTP_200_OK)


class SosAlertViewSet(GenericViewSet):
    """
    SOS-сигналы от ребёнка и для родителя.
    POST /api/game/alerts/sos/  (PATIENT) — ребёнок нажал SOS.
    GET  /api/game/alerts/      (PARENT)  — родитель получает список SOS-сигналов.
    """
    queryset = AvatarSosAlert.objects.all()
    # По умолчанию в этом вьюсете работаем в родительском контексте
    authentication_classes = [ParentJWTAuthentication]
    permission_classes = [IsParent]

    def get_avatar_from_patient(self, request):
        return CatAvatar.objects.filter(patient_id=request.user.id).first()

    def get_avatar_from_parent(self, request):
        return CatAvatar.objects.filter(patient_id=request.user.id).first()

    @extend_schema(
        request=None,
        responses={200: inline_serializer(
            name='SosSendResponse',
            fields={"status": serializers.CharField()}
        )},
        description="Ребёнок отправляет SOS-сигнал родителю"
    )
    @action(
        detail=False,
        methods=['post'],
        url_path='sos',
        authentication_classes=[PatientJWTAuthentication],
        permission_classes=[IsPatient],
    )
    def send_sos(self, request):
        cat = self.get_avatar_from_patient(request)
        if not cat:
            return Response({"error": "Avatar not found"}, status=status.HTTP_404_NOT_FOUND)

        AvatarSosAlert.objects.create(avatar=cat)
        return Response({"status": "ok"}, status=status.HTTP_200_OK)

    @extend_schema(
        responses={200: SosAlertSerializer(many=True)},
        description="Родитель получает список SOS-сигналов ребёнка"
    )
    def list(self, request, *args, **kwargs):
        avatar = self.get_avatar_from_parent(request)
        if not avatar:
            return Response([], status=status.HTTP_200_OK)

        alerts = AvatarSosAlert.objects.filter(avatar=avatar).order_by('-created_at')[:20]
        serializer = SosAlertSerializer(alerts, many=True)
        return Response(serializer.data)

    @extend_schema(
        request=None,
        responses={200: inline_serializer(
            name='SosMarkReadResponse',
            fields={"status": serializers.CharField()}
        )},
        description="Родитель помечает конкретный SOS-сигнал как прочитанный (обработанный)"
    )
    @action(detail=True, methods=['post'], url_path='mark-read')
    def mark_read(self, request, pk=None):
        try:
            alert = AvatarSosAlert.objects.get(id=pk, avatar__patient_id=request.user.id)
        except AvatarSosAlert.DoesNotExist:
            return Response({"error": "SOS alert not found"}, status=status.HTTP_404_NOT_FOUND)

        if not alert.handled:
            alert.handled = True
            alert.save(update_fields=['handled'])

        return Response({"status": "success"}, status=status.HTTP_200_OK)

class PatientTreatmentViewSet(GenericViewSet):
    permission_classes = [IsParent]
    authentication_classes = [ParentJWTAuthentication]
    serializer_class = VisitSerializer
    queryset = Patient.objects.all()
    def get_current_patient(self):
        return Patient.objects.get(id=self.request.user.id)

    @action(detail=False, methods=['get'], url_path='status')
    def get_status(self, request):
        patient = self.get_current_patient()
        serializer = PatientTreatmentProgressSerializer(patient)
        return Response(serializer.data)

    @action(detail=False, methods=['get'], url_path='upcoming-visits')
    def upcoming(self, request):
        patient = self.get_current_patient()
        visits = Visit.objects.filter(
            patient=patient,
            is_confirmed=False,
            date__gte=date.today()
        ).order_by('date', 'time')
        serializer = VisitSerializer(visits, many=True, context={'request': request})
        return Response(serializer.data)

    @action(detail=False, methods=['get'], url_path='reports')
    def reports(self, request):
        patient = self.get_current_patient()
        visits = Visit.objects.filter(
            patient=patient,
            is_confirmed=True
        ).order_by('-date')
        serializer = VisitSerializer(visits, many=True, context={'request': request})
        return Response(serializer.data)

    @extend_schema(
        request=inline_serializer(
            name='SetTreatmentStartDate',
            fields={
                'start_date': serializers.DateField(help_text="Дата начала ношения первой каппы (ГГГГ-ММ-ДД)")
            }
        ),
        responses={200: {"example": {"status": "success",
            "treatment_start_date": "patient.treatment_start_date",
            "message": "Дата начала лечения для {patient.first_name} установлена."}}},
        description="Установить дату начала лечения для расчета номера каппы"
    )
    @action(detail=False, methods=['post'], url_path='set-treatment-start')
    def set_treatment_start(self, request):
        patient = self.get_current_patient()

        start_date = request.data.get('start_date', date.today().isoformat())

        patient.treatment_start_date = start_date
        patient.save()

        return Response({
            "status": "success",
            "treatment_start_date": patient.treatment_start_date,
            "message": f"Дата начала лечения для {patient.first_name} установлена."
        })

    @extend_schema(
        request=inline_serializer(
            name='MarkVisitNotificationReadRequest',
            fields={'visit_id': serializers.IntegerField()}
        ),
        responses={200: inline_serializer(
            name='MarkVisitNotificationReadResponse',
            fields={"status": serializers.CharField()}
        )},
        description="Пометить уведомление о визите как прочитанное родителем"
    )
    @action(detail=False, methods=['post'], url_path='mark-visit-read')
    def mark_visit_read(self, request):
        visit_id = request.data.get('visit_id')
        if not visit_id:
            return Response({"error": "visit_id required"}, status=status.HTTP_400_BAD_REQUEST)

        patient = self.get_current_patient()
        try:
            visit = Visit.objects.get(id=visit_id, patient=patient)
        except Visit.DoesNotExist:
            return Response({"error": "Visit not found"}, status=status.HTTP_404_NOT_FOUND)

        if not visit.parent_visit_read:
            visit.parent_visit_read = True
            visit.save(update_fields=['parent_visit_read'])

        return Response({"status": "success"}, status=status.HTTP_200_OK)

    @extend_schema(
        request=inline_serializer(
            name='MarkReportReadRequest',
            fields={'visit_id': serializers.IntegerField()}
        ),
        responses={200: inline_serializer(
            name='MarkReportReadResponse',
            fields={"status": serializers.CharField()}
        )},
        description="Пометить отчёт по визиту как прочитанный родителем"
    )
    @action(detail=False, methods=['post'], url_path='mark-report-read')
    def mark_report_read(self, request):
        visit_id = request.data.get('visit_id')
        if not visit_id:
            return Response({"error": "visit_id required"}, status=status.HTTP_400_BAD_REQUEST)

        patient = self.get_current_patient()
        try:
            visit = Visit.objects.get(id=visit_id, patient=patient)
        except Visit.DoesNotExist:
            return Response({"error": "Visit not found"}, status=status.HTTP_404_NOT_FOUND)

        if not visit.parent_report_read:
            visit.parent_report_read = True
            visit.save(update_fields=['parent_report_read'])

        return Response({"status": "success"}, status=status.HTTP_200_OK)
