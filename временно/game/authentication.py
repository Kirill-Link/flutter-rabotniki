from typing import Optional

from rest_framework.request import Request
from rest_framework_simplejwt.authentication import JWTAuthentication, AuthUser
from rest_framework_simplejwt.exceptions import TokenError, InvalidToken
from rest_framework.exceptions import AuthenticationFailed
from rest_framework_simplejwt.tokens import Token
from rest_framework import exceptions

class AuthPatient:
    def __init__(self, patient_id):
        self.id = patient_id
        self.pk = patient_id
        self.is_authenticated = True
        self.role = 'patient'

    def __str__(self):
        return f"Patient (ID: {self.id})"

#пациент
class PatientJWTAuthentication(JWTAuthentication):
    def authenticate(self, request: Request) -> Optional[tuple['AuthPatient', 'Token']]:
        header = self.get_header(request)
        if header is None:
            return None

        parts = header.split()

        if len(parts) != 2 or parts[0].decode('utf-8') != 'PATIENT':
            return None

        raw_token = parts[1]

        try:
            validated_token = self.get_validated_token(raw_token)
        except (TokenError, InvalidToken) as e:
            raise exceptions.AuthenticationFailed(f'Invalid token: {str(e)}')

        if validated_token.get('role') != 'patient':
            raise exceptions.AuthenticationFailed('Invalid role')

        patient_id = validated_token.get('patient_id')
        if not patient_id:
            raise exceptions.AuthenticationFailed('No patient_id in token')

        from patients.models import Patient
        try:
            patient = Patient.objects.select_related('avatar').get(id=patient_id)

            if patient.status == 'archived':
                raise exceptions.AuthenticationFailed(
                    'Patient account is archived'
                )

        except Patient.DoesNotExist:
            raise exceptions.AuthenticationFailed('Patient not found')

        return AuthPatient(patient_id), validated_token



class AuthParent:
    def __init__(self, patient_id):
        self.id = patient_id
        self.pk = patient_id
        self.is_authenticated = True
        self.role = 'parent'

    def __str__(self):
        return f"Parent of patient(Patient ID: {self.id})"

#родитель
class ParentJWTAuthentication(JWTAuthentication):
    def authenticate(self, request: Request) -> Optional[tuple['AuthParent', 'Token']]:
        header = self.get_header(request)
        if header is None:
            return None

        parts = header.split()

        if len(parts) != 2 or parts[0].decode('utf-8') != 'PARENT':
            return None

        raw_token = parts[1]

        try:
            validated_token = self.get_validated_token(raw_token)
        except (TokenError, InvalidToken) as e:
            raise exceptions.AuthenticationFailed(f'Invalid token: {str(e)}')

        if validated_token.get('role') != 'parent':
            raise exceptions.AuthenticationFailed('Invalid role')

        patient_id = validated_token.get('patient_id')
        if not patient_id:
            raise exceptions.AuthenticationFailed('No patient_id in token')

        from patients.models import Patient
        try:
            patient = Patient.objects.select_related('avatar').get(id=patient_id)

            if patient.status == 'archived':
                raise exceptions.AuthenticationFailed(
                    'Patient account is archived'
                )

        except Patient.DoesNotExist:
            raise exceptions.AuthenticationFailed('Patient not found')

        return AuthParent(patient_id), validated_token
