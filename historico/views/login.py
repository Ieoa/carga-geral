from django.contrib.auth import authenticate, login, logout
from django.shortcuts import redirect, render
from django.utils.http import url_has_allowed_host_and_scheme

from ..forms import LoginForm
from ..login_security import (
    clear_login_failures,
    is_login_blocked,
    register_login_failure,
)
from ..security import find_authorized_user


def login_view(request):
    next_url = _safe_next_url(request)
    if request.user.is_authenticated:
        return redirect(next_url or "dashboard")

    if request.method == "POST":
        form = LoginForm(request.POST)
        if form.is_valid():
            matricula = form.cleaned_data["matricula"]
            senha = form.cleaned_data["senha"]

            if is_login_blocked(request, matricula):
                form.add_error(
                    None,
                    "Muitas tentativas inválidas. Aguarde alguns minutos e tente novamente.",
                )
                return render(
                    request, "historico/login.html", {"form": form}, status=429
                )

            authorized_user = find_authorized_user(matricula)
            if authorized_user is None:
                register_login_failure(request, matricula)
                form.add_error(None, "Login ou senha inválidos.")
                return render(
                    request,
                    "historico/login.html",
                    {"form": form, "next": next_url or ""},
                )

            user = authenticate(
                request,
                username=authorized_user.username,
                password=senha,
            )
            if user is not None:
                clear_login_failures(request, matricula)
                login(request, user)
                return redirect(next_url or "dashboard")

            register_login_failure(request, matricula)
            form.add_error(None, "Login ou senha inválidos.")
    else:
        form = LoginForm()

    return render(
        request,
        "historico/login.html",
        {"form": form, "next": next_url or ""},
    )


def _safe_next_url(request):
    target = request.POST.get("next") or request.GET.get("next")
    if target and url_has_allowed_host_and_scheme(
        target,
        allowed_hosts={request.get_host()},
        require_https=request.is_secure(),
    ):
        return target
    return None


def logout_view(request):
    logout(request)
    return redirect("login")
