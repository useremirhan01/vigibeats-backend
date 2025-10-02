from django import forms
from captcha.fields import CaptchaField

class LoginForm(forms.Form):
    username = forms.CharField(max_length=50, label="Kullanıcı Adı")
    password = forms.CharField(label="Şifre", widget=forms.PasswordInput)
    captcha = CaptchaField()

class RegisterForm(forms.Form):
    username = forms.CharField(max_length=50, label="Kullanıcı Adı")
    email = forms.EmailField(label="Email", widget=forms.EmailInput(attrs={'class': 'form-control'}))
    password = forms.CharField(label="Şifre", widget=forms.PasswordInput)
    confirm = forms.CharField(label="Şifre Doğrula", widget=forms.PasswordInput)
    captcha = CaptchaField()

    def clean(self):
        cleaned_data = super().clean()
        password = cleaned_data.get('password')
        confirm = cleaned_data.get('confirm')
        
        if password and confirm and password != confirm:
            raise forms.ValidationError("Parolalar Eşleşmiyor")

        return cleaned_data
