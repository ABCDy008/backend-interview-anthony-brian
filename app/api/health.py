from fastapi import APIRouter

router = APIRouter()


@router.get(
    "/health",
    tags=["health"],
    summary="Check API health",
    description="Returns a simple status response when the API process is available.",
    response_description="The API is healthy.",
)
def health() -> dict[str, str]:
    return {"status": "ok"}
