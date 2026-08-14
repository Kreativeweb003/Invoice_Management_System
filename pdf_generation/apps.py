from django.apps import AppConfig


class PdfGenerationConfig(AppConfig):
    default_auto_field = 'django.db.models.BigAutoField'
    name = 'pdf_generation'
    verbose_name = 'PDF Generation'