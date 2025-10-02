from django.conf import settings
from django.db import models
from django.contrib.auth.models import User
import os

def get_upload_path(instance, filename):
    return f'music/user_{instance.article.author.id}/{instance.article.id}/{filename}'

class Article(models.Model):
    BEAT_TYPE_CHOICES = [
        ('rap', 'Rap'),
        ('funk', 'Funk'),
        ('trap', 'Trap'),
        ('none', 'None'),
    ]
    author = models.ForeignKey(User, on_delete=models.CASCADE, verbose_name="Sanatçı")
    title = models.CharField(max_length=50, verbose_name="İsim")
    content = models.TextField()  # veya RichTextField
    created_date = models.DateTimeField(auto_now_add=True, verbose_name="Oluşturulma Tarihi")
    price = models.CharField(max_length=50, verbose_name="Fiyat")
    type = models.CharField(max_length=10, choices=BEAT_TYPE_CHOICES, default='none')
    
    def __str__(self):
        return self.title

    class Meta:
        ordering = ['-created_date']

class ArticleFile(models.Model):
    article = models.ForeignKey(Article, related_name='files', on_delete=models.CASCADE)
    file = models.FileField(upload_to=get_upload_path)
    
    def save(self, *args, **kwargs):
        super().save(*args, **kwargs)
        if self.file:
            base, extension = os.path.splitext(self.file.name)
            new_name = f"{self.article.id}_{self.id}{extension}"
            new_file_path = os.path.join(settings.MEDIA_ROOT, 'music', f"user_{self.article.author.id}", f"{self.article.id}", new_name)
            os.makedirs(os.path.dirname(new_file_path), exist_ok=True)
            os.rename(self.file.path, new_file_path)
            self.file.name = os.path.join('music', f"user_{self.article.author.id}", f"{self.article.id}", new_name)
            super().save(*args, **kwargs)

class Comment(models.Model):
    article = models.ForeignKey(Article, on_delete=models.CASCADE, verbose_name="Makale", related_name="comments")
    comment_author = models.CharField(max_length=50, verbose_name="İsim")
    comment_content = models.CharField(max_length=200, verbose_name="Yorum")
    comment_date = models.DateTimeField(auto_now_add=True)
    
    def __str__(self):
        return self.comment_content

    class Meta:
        ordering = ['-comment_date']
