from django.contrib.auth.models import User
from .models import Team

PEOPLE_TEAM="People Team"
TECH_TEAM="Technology Team"

def user_in_team(user: User, team_name: str) -> bool:
    team = Team.objects.filter(name=team_name).first()
    
    if not team:
        raise ValueError(f"Unknown team: {team_name}")
    
    return team.members.contains(user)

