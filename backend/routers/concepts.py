import logging

from fastapi import APIRouter, HTTPException
from pydantic import BaseModel

from agents import concept_extractor

logger = logging.getLogger(__name__)
router = APIRouter()


class ConceptsRequest(BaseModel):
    transcript: list


@router.post("/concepts")
async def extract_concepts(body: ConceptsRequest):
    logger.info("Extracting concepts from %d transcript segments", len(body.transcript))
    try:
        concepts = await concept_extractor.run(body.transcript)
    except ValueError as e:
        logger.warning("ConceptExtractor parse error: %s", e)
        raise HTTPException(status_code=500, detail=f"Concept extraction failed: {e}")
    logger.info("Returning %d concepts", len(concepts))
    return concepts
