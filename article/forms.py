from django import forms
from .models import Article, ArticleFile
from django.forms import modelformset_factory

class ArticleForm(forms.ModelForm):
    class Meta:
        model = Article
        fields = ['title', 'content','price','type',]

class ArticleFileForm(forms.ModelForm):
    class Meta:
        model = ArticleFile
        fields = ['file']

ArticleFileFormSet = modelformset_factory(ArticleFile, form=ArticleFileForm, extra=3)  # 3 dosya için örnek
