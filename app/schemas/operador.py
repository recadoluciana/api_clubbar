from pydantic import BaseModel, EmailStr, Field


class OperadorLoginIn(BaseModel):
    email: EmailStr
    senha: str = Field(min_length=6, max_length=72)


class OperadorOut(BaseModel):
    operador_id: int
    nmoperador: str
    emailoperador: EmailStr
    perfil: str
    sitoperador: str


class OperadorCreate(BaseModel):
    nmoperador: str = Field(min_length=2, max_length=200)
    emailoperador: EmailStr
    senha: str = Field(min_length=8, max_length=72)
    perfil: str = Field(default="ADMIN", max_length=30)
