from typing import Union, List

from drf_spectacular.extensions import OpenApiAuthenticationExtension, _SchemaType


class PatientJWTAuthenticationScheme(OpenApiAuthenticationExtension):
    target_class = 'game.authentication.PatientJWTAuthentication'
    name = 'PatientAuth'

    def get_security_definition(self, auto_schema: 'AutoSchema') -> Union[_SchemaType, List[_SchemaType]]:
        return {
            'type': 'apiKey',
            'in': 'header',
            'name': 'Authorization',
            'description': 'Авторизация пациента. Формат: PATIENT <token>'
        }

class ParentJWTAuthenticationScheme(OpenApiAuthenticationExtension):
    target_class = 'game.authentication.ParentJWTAuthentication'
    name = 'ParentAuth'

    def get_security_definition(self, auto_schema: 'AutoSchema') -> Union[_SchemaType, List[_SchemaType]]:
        return {
            'type': 'apiKey',
            'in': 'header',
            'name': 'Authorization',
            'description': 'Авторизация родителя. Формат PARENT <token>'
        }