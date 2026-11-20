from fastapi import HTTPException


def require_source_rights_confirmation(confirmed: object) -> None:
    """Require explicit confirmation before a source video can be processed."""
    if confirmed is not True:
        raise HTTPException(
            status_code=400,
            detail={
                "code": "SOURCE_RIGHTS_REQUIRED",
                "message": (
                    "Confirm that you own this video or have permission from "
                    "the rights holder to process and publish clips from it."
                ),
            },
        )
