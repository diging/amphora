from django.apps import AppConfig

class CookiesConfig(AppConfig):
    name = 'cookies'
    verbose_name = 'Curation'
    
    def ready(self):
        import cookies.signals
        super(CookiesConfig, self).ready()