from fastapi import APIRouter, Depends, HTTPException, Request, status
from fastapi.responses import RedirectResponse
from sqlalchemy.orm import Session

from app.core.database import get_db
from app.schemas import LinkAnalyticsResponse, LinkCreate, LinkResponse, LinkUpdate
from app.services import link_service

router = APIRouter()


@router.post("/links", response_model=LinkResponse, status_code=status.HTTP_201_CREATED)
def create_link(link_data: LinkCreate, db: Session = Depends(get_db)):
    try:
        link = link_service.create_link(db, link_data)
    except ValueError as e:
        raise HTTPException(status_code=status.HTTP_409_CONFLICT, detail=str(e))
    except RuntimeError as e:
        raise HTTPException(status_code=status.HTTP_500_INTERNAL_SERVER_ERROR, detail=str(e))
    return link


@router.get("/links/{short_code}/stats", response_model=LinkResponse)
def get_link_stats(short_code: str, db: Session = Depends(get_db)):
    link = link_service.get_link_stats(db, short_code)
    if not link:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Short link not found")
    return link


@router.get("/links/{short_code}/analytics", response_model=LinkAnalyticsResponse)
def get_link_analytics(short_code: str, limit: int = 50, db: Session = Depends(get_db)):
    analytics = link_service.get_link_analytics(db, short_code, limit=limit)
    if not analytics:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Short link not found")
    return analytics


@router.patch("/links/{short_code}", response_model=LinkResponse)
def update_link(short_code: str, link_update: LinkUpdate, db: Session = Depends(get_db)):
    link = link_service.update_link(db, short_code, link_update)
    if not link:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Short link not found")
    return link


@router.delete("/links/{short_code}", status_code=status.HTTP_204_NO_CONTENT)
def delete_link(short_code: str, db: Session = Depends(get_db)):
    deleted = link_service.delete_link(db, short_code)
    if not deleted:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Short link not found")
    return None


@router.api_route("/{short_code}", methods=["GET", "HEAD"])
def redirect_to_url(short_code: str, request: Request, db: Session = Depends(get_db)):
    user_agent = request.headers.get("user-agent")
    referrer = request.headers.get("referer")
    ip_address = request.client.host if request.client else None

    original_url = link_service.get_and_track_link(
        db=db,
        short_code=short_code,
        user_agent=user_agent,
        referrer=referrer,
        ip_address=ip_address,
    )
    if not original_url:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Short link not found")
    return RedirectResponse(url=original_url, status_code=status.HTTP_307_TEMPORARY_REDIRECT)