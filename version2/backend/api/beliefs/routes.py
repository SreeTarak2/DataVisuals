from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel
from db.database import get_database
from services.auth_service import get_current_user
from services.memory.belief_service import BeliefService

router = APIRouter(tags=["beliefs"])


class BeliefCreate(BaseModel):
    dataset_id: str
    content: str
    rule_type: str = "business_logic"


class BeliefUpdate(BaseModel):
    content: str


@router.get("/{dataset_id}")
async def list_beliefs(dataset_id: str, user=Depends(get_current_user), db=Depends(get_database)):
    return await BeliefService(db).list_all(str(user["_id"]), dataset_id)


@router.post("/")
async def create_belief(
    body: BeliefCreate, user=Depends(get_current_user), db=Depends(get_database)
):
    return await BeliefService(db).save_manual(
        str(user["_id"]), body.dataset_id, body.content, body.rule_type
    )


@router.patch("/{belief_id}")
async def update_belief(
    belief_id: str, body: BeliefUpdate, user=Depends(get_current_user), db=Depends(get_database)
):
    ok = await BeliefService(db).update(belief_id, str(user["_id"]), body.content)
    if not ok:
        raise HTTPException(404, "Belief not found")
    return {"success": True}


@router.delete("/{belief_id}")
async def delete_belief(belief_id: str, user=Depends(get_current_user), db=Depends(get_database)):
    ok = await BeliefService(db).deactivate(belief_id, str(user["_id"]))
    if not ok:
        raise HTTPException(404, "Belief not found")
    return {"success": True}
