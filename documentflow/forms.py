from django import forms
from .models import DocumentRouteStep, User, Department

class DocumentRouteStepForm(forms.ModelForm):
    class Meta:
        model = DocumentRouteStep
        fields = '__all__'

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        # user показываем ФИО + отдел
        self.fields['user'].label_from_instance = lambda obj: f"{obj.full_name} ({obj.department})"
        # отдел просто имя
        self.fields['department'].label_from_instance = lambda obj: obj.name

