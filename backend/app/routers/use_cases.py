from typing import List
from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select
from datetime import datetime

from ..database import get_db
from ..models import UseCase
from ..schemas import UseCaseCreate, UseCaseUpdate, UseCaseOut
from ..services.ai_agent import generate_use_case_prompt

router = APIRouter(prefix="/api/use-cases", tags=["use-cases"])


@router.get("", response_model=List[UseCaseOut])
async def list_use_cases(db: AsyncSession = Depends(get_db)):
    result = await db.execute(select(UseCase).order_by(UseCase.created_at.desc()))
    return result.scalars().all()


@router.post("", response_model=UseCaseOut, status_code=201)
async def create_use_case(
    body: UseCaseCreate,
    db: AsyncSession = Depends(get_db),
):
    """
    Create a new use case. If system_prompt is the special value 'auto',
    Claude will generate one from the name and description.
    """
    system_prompt = body.system_prompt
    if system_prompt.strip().lower() == "auto":
        system_prompt = generate_use_case_prompt(body.name, body.description or "")

    uc = UseCase(
        name=body.name,
        description=body.description or "",
        system_prompt=system_prompt,
        is_active=body.is_active,
    )
    db.add(uc)
    await db.commit()
    await db.refresh(uc)
    return uc


@router.get("/{use_case_id}", response_model=UseCaseOut)
async def get_use_case(use_case_id: int, db: AsyncSession = Depends(get_db)):
    uc = await db.get(UseCase, use_case_id)
    if not uc:
        raise HTTPException(status_code=404, detail="Use case not found.")
    return uc


@router.patch("/{use_case_id}", response_model=UseCaseOut)
async def update_use_case(
    use_case_id: int,
    body: UseCaseUpdate,
    db: AsyncSession = Depends(get_db),
):
    uc = await db.get(UseCase, use_case_id)
    if not uc:
        raise HTTPException(status_code=404, detail="Use case not found.")
    for field, value in body.model_dump(exclude_unset=True).items():
        setattr(uc, field, value)
    uc.updated_at = datetime.utcnow()
    await db.commit()
    await db.refresh(uc)
    return uc


@router.delete("/{use_case_id}", status_code=204)
async def delete_use_case(use_case_id: int, db: AsyncSession = Depends(get_db)):
    uc = await db.get(UseCase, use_case_id)
    if not uc:
        raise HTTPException(status_code=404, detail="Use case not found.")
    await db.delete(uc)
    await db.commit()
