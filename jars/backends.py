from django.contrib.auth.backends import ModelBackend


class AllowAllUsersModelBackend(ModelBackend):
    def user_can_authenticate(self, *args, **kwargs):
        return True
