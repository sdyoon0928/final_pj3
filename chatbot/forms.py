# forms.py
from django import forms

class FindAccountForm(forms.Form):
    name = forms.CharField(max_length=100, label="이름")
    phone = forms.CharField(max_length=20, label="전화번호")
