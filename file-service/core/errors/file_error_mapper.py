from fastapi import HTTPException, status
from infrastructure.logging.logger import logger


def map_channel_error(exc: Exception) -> HTTPException:

    logger.error("Unhandled channel error", exc_info=True)
    return HTTPException(
        status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
        detail="Internal server error",
    )