import random

from django import forms
from django.contrib import admin
from django.contrib.auth.admin import UserAdmin
from django.contrib import messages
from .models import User
import secrets
import string

class DoctorCreationForm(forms.ModelForm):
    class Meta:
        model = User
        fields = ('first_name', 'last_name', 'middle_name', 'clinic_name', 'is_doctor')

    def save(self, commit=True):
        user = super().save(commit=False)
        if not user.username:
            random_suffix = ''.join(random.choices(string.digits, k=4))
            user.username = f"dr_{random_suffix}"

        self.generated_password = secrets.token_urlsafe(8)
        user.set_password(self.generated_password)

        if commit:
            user.save()
        return user


@admin.register(User)
class MyUserAdmin(UserAdmin):
    add_form = DoctorCreationForm

    list_display = ('username', 'last_name', 'first_name', 'middle_name', 'clinic_name', 'is_doctor')
    list_filter = ('is_doctor', 'clinic_name')

    add_fieldsets = (
        (None, {
            'classes': ('wide',),
            'fields': ('first_name', 'last_name', 'middle_name', 'clinic_name', 'is_doctor'),
        }),
    )

    fieldsets = (
        (None, {'fields': ('username', 'password')}),
        ('Персональные данные', {'fields': ('first_name', 'last_name', 'middle_name','clinic_name')}),
        ('Права', {'fields': ('is_active', 'is_staff', 'is_doctor')}),
    )

    def save_model(self, request, obj, form, change):
        if not change:
            super().save_model(request, obj, form, change)

            raw_password = getattr(form, 'generated_password', 'Уже установлен')
            messages.success(request, f"ВРАЧ СОЗДАН УСПЕШНО!")
            messages.info(request, f"Логин: {obj.username} | Пароль: {raw_password}")
            messages.warning(request, "Обязательно скопируйте пароль сейчас, он будет зашифрован!")
        else:
            super().save_model(request, obj, form, change)
