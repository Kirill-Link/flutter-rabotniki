from django.contrib import admin
from django import forms

from .models import Patient, PatientQR, Document, TreatmentTypeOption, CapSystemOption, Parent

class PatientInline(admin.TabularInline):
    model = Patient
    extra = 0
    fields = ('last_name', 'first_name', 'status')

class ParentAdminForm(forms.ModelForm):
    password = forms.CharField(
        widget=forms.PasswordInput,
        label="Пароль",
        required=False,
        help_text="Оставьте пустым, чтобы не менять пароль."
    )

    class Meta:
        model = Parent
        fields = '__all__'

    def save(self, commit=True):
        parent = super().save(commit=False)
        raw_password = self.cleaned_data.get("password")
        if raw_password:
            parent.set_password(raw_password)
        if commit:
            parent.save()
        return parent

@admin.register(Parent)
class ParentAdmin(admin.ModelAdmin):
    inlines = [PatientInline]
    form = ParentAdminForm
    list_display = ('last_name', 'first_name', 'phone')

@admin.register(Patient)
class PatientAdmin(admin.ModelAdmin):
    list_display = ('last_name', 'first_name', 'parent', 'doctor', 'status')
    list_filter = ('doctor', 'status', 'parent')
    search_fields = ('last_name', 'first_name', 'parent__phone')


@admin.register(PatientQR)
class PatientQRAdmin(admin.ModelAdmin):
    list_display = ('patient', 'image', 'created_at')
    readonly_fields = ('image',)


@admin.register(Document)
class DocumentAdmin(admin.ModelAdmin):
    list_display = ('title', 'file')


@admin.register(TreatmentTypeOption)
class TreatmentTypeOptionAdmin(admin.ModelAdmin):
    list_display = ('name', 'code', 'order')
    list_editable = ('code', 'order')
    search_fields = ('name', 'code')
    ordering = ('order', 'name')


@admin.register(CapSystemOption)
class CapSystemOptionAdmin(admin.ModelAdmin):
    list_display = ('name', 'code', 'order')
    list_editable = ('code', 'order')
    search_fields = ('name', 'code')
    ordering = ('order', 'name')
