from django.shortcuts import render,HttpResponse,redirect,get_object_or_404,reverse
from .forms import ArticleForm, ArticleFileForm,ArticleFileFormSet
from .models import Article,Comment,ArticleFile
from django.contrib import messages
from django.contrib.auth.decorators import login_required
from django.shortcuts import render, redirect, get_object_or_404
from django.contrib import messages
from django.conf import settings
import os


# Create your views here.
def index(request):
    context = {
        "number" : 7,
        "number2" : 9
        
    }
    return render(request, "index.html",context)

def articles(request):
    articles = Article.objects.all()
    keyword = request.GET.get("keyword")
    if keyword:
        articles = Article.objects.filter(title__contains = keyword)
        return render(request,"articles.html",{"articles":articles})
    
    
    context = {
        
        "articles" : articles
    }
    
    
    return render(request,"articles.html",context)



def about(request):
    return render(request, "about.html")


def dashboard(request):
    articles = Article.objects.filter(author = request.user)
    context = {
        
        "articles" : articles
    }
    
    return render(request,"dashboard.html",context)

@login_required
def addArticle(request):
    if request.method == "POST":
        form = ArticleForm(request.POST)
        formset = ArticleFileFormSet(request.POST, request.FILES, queryset=ArticleFile.objects.none())
        if form.is_valid() and formset.is_valid():
            article = form.save(commit=False)
            article.author = request.user
            article.save()
            for form in formset:
                if form.cleaned_data:
                    file = form.cleaned_data.get('file')
                    if file:
                        # Her bir dosya için yeni bir ArticleFile nesnesi oluştur
                        article_file = ArticleFile(article=article, file=file)
                        article_file.save()
            messages.success(request, "Makale ve dosyalar başarıyla yüklendi.")
            return redirect("/articles/dashboard")
    else:
        form = ArticleForm()
        formset = ArticleFileFormSet(queryset=ArticleFile.objects.none())
    return render(request, "addarticle.html", {"form": form, "formset": formset})




def detail(request,id):
    #article = Article.objects.filter(id = id).first
    article = get_object_or_404(Article, id = id)
    Comments = article.comments.all()
    return render(request,"detail.html",{"article" : article,"Comments": Comments})


@login_required
def updateArticle(request,id):
    article = get_object_or_404(Article, id = id)
    form = ArticleForm(request.POST or None,request.FILES or None,instance = article)
    if form.is_valid():
        article = form.save(commit=False)
        
        article.author = request.user
        article.save()
        messages.success(request,"Makale Başarıyla Kaydedildi...")
        return redirect("/articles/dashboard")
        
    return render(request,"update.html",{"form" : form})
            
@login_required
def delete(request,id):
    article = get_object_or_404(Article,id = id)
    form = ArticleForm(request.POST or None,request.FILES or None,instance = article)
    article.delete()
    messages.success(request,"Makale Silindi...")
    return redirect("/articles/dashboard")

def addComment(request,id):
    article = get_object_or_404(Article,id = id)
    
    if request.method == "POST":
        comment_author = request.POST.get("comment_author")
        comment_content = request.POST.get("comment_content")
        
        newComment = Comment(comment_author = comment_author, comment_content = comment_content)
        
        newComment.article = article
        
        newComment.save()
        
    #return redirect("/articles/article/" + str(id))
    return redirect(reverse("article:detail",kwargs= {"id" : id}))