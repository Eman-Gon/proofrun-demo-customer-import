"""Customer records accepted by the import API."""

from typing import Optional

from pydantic import BaseModel


class Customer(BaseModel):
    name: str
    nickname: Optional[str]
