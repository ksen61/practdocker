import re
from django.core.exceptions import ValidationError
from django.utils.translation import gettext as _


class StrongPasswordValidator:
    def __init__(self, min_length=8):
        self.min_length = min_length

    def validate(self, password, user=None):
        if len(password) < self.min_length:
            raise ValidationError(
                _(f"Пароль должен быть не короче {self.min_length} символов."),
                code="password_too_short",
            )
        if not re.search(r"[A-Za-zА-Яа-я]", password):
            raise ValidationError(_("Пароль должен содержать буквы."), code="password_no_letters")
        if not re.search(r"\d", password):
            raise ValidationError(_("Пароль должен содержать цифры."), code="password_no_digits")
        if not re.search(r"[^A-Za-zА-Яа-я0-9]", password):
            raise ValidationError(_("Пароль должен содержать спецсимволы."), code="password_no_special")

    def get_help_text(self):
        return _(
            f"Пароль должен быть не короче {self.min_length} символов и содержать буквы, цифры и спецсимволы."
        )


class NoReusePasswordValidator:
    def validate(self, password, user=None):
        if user is not None and user.check_password(password):
            raise ValidationError(_("Новый пароль не должен совпадать с предыдущим."), code="password_no_reuse")

    def get_help_text(self):
        return _("Новый пароль не должен совпадать с предыдущим.")
