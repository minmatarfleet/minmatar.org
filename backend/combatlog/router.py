from ninja import Router
from pydantic import BaseModel

from .combatlog import parse, damage_events, damage_done

router = Router(tags=["combatlog"])

class LogAnalysis(BaseModel):
    logged_events: int = 0
    damage_done: int = 0
    damage_taken: int = 0


@router.post("/", description="Process an Eve combat log", response={200: LogAnalysis},  
             openapi_extra=
                {
                "requestBody": 
                    {
                        "content": 
                        {
                        "text/plain": {"schema": {"type": "string"}}
                        }
                    }
                })      
def analyze_logs(request):
    content = request.body.decode('utf-8')
    
    events = parse(content)
    
    analysis = LogAnalysis()
    analysis.logged_events = len(events)
    dmg_events = damage_events(events)
    (analysis.damage_done, analysis.damage_taken) = damage_done(dmg_events)

    return analysis