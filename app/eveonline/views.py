from django.shortcuts import render, redirect
from django.contrib.auth.decorators import login_required
from esi.decorators import token_required


# Create your views here.
def list_characters(request):
    context = {}
    context['tokens'] = request.user.token_set.all()
    return render(request, "eveonline/list_characters.html", context)


@login_required
@token_required(
    scopes=["esi-fleets.read_fleet.v1", "esi-fleets.write_fleet.v1"]
)
def add_character(request, token):
    return redirect("eveonline-characters")
