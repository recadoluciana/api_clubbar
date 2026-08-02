from datetime import datetime, time

from pydantic import BaseModel, ConfigDict, Field, RootModel, model_validator


class LojaHorarioItem(BaseModel):
    diasemana: int = Field(ge=1, le=7)
    fechado: bool
    horaabertura: time | None = None
    horafechamento: time | None = None
    fechadiaseguinte: bool = False

    @model_validator(mode="after")
    def validar_horarios(self) -> "LojaHorarioItem":
        if self.fechado:
            if self.horaabertura is not None or self.horafechamento is not None:
                raise ValueError(
                    "Dias fechados não podem possuir horário de abertura ou fechamento."
                )
            if self.fechadiaseguinte:
                raise ValueError(
                    "Dias fechados não podem indicar fechamento no dia seguinte."
                )
            return self

        if self.horaabertura is None or self.horafechamento is None:
            raise ValueError(
                "Horário de abertura e fechamento são obrigatórios para dias abertos."
            )

        if self.horaabertura == self.horafechamento:
            raise ValueError(
                "Horário de abertura e fechamento devem ser diferentes."
            )

        return self


class LojaHorarioOut(LojaHorarioItem):
    model_config = ConfigDict(from_attributes=True)

    lojahorario_id: int | None = None
    loja_id: int
    dtcriacao: datetime | None = None
    dtalteracao: datetime | None = None


class LojaHorarioListaUpdate(RootModel[list[LojaHorarioItem]]):

    @model_validator(mode="after")
    def validar_lista_completa(self) -> "LojaHorarioListaUpdate":
        dias = [item.diasemana for item in self.root]

        if len(dias) != 7:
            raise ValueError("Devem ser informados exatamente os sete dias da semana.")

        if len(set(dias)) != len(dias):
            raise ValueError("Não são permitidos dias repetidos no mesmo payload.")

        if set(dias) != set(range(1, 8)):
            raise ValueError("O payload deve conter os dias de 1 a 7.")

        return self
