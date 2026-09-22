from datetime import datetime

from fastapi import APIRouter, Depends, HTTPException, status
from pydantic import BaseModel, Field, model_validator
from sqlalchemy.orm import Session

from app.core.security import get_operador_logado
from app.database import get_db
from app.models.politicacompra import PoliticaCompra


router = APIRouter(prefix="/politicas", tags=["Políticas Clubbar"])


class PoliticaCompraIn(BaseModel):
    versao: str = Field(min_length=1, max_length=30)
    titulo: str = Field(min_length=3, max_length=160)
    tipopolitica: str
    qtd_dias_cancelamento: int = Field(ge=0, le=365)
    qtd_horas_antecedencia_cancelamento: int | None = Field(default=None, ge=0, le=8760)
    qtd_alteracoes_participante: int | None = Field(default=None, ge=0, le=20)
    qtd_horas_antecedencia_alteracao: int | None = Field(default=None, ge=0, le=8760)

    @model_validator(mode="after")
    def validar_campos_do_tipo(self):
        tipo = self.tipopolitica.upper().strip()
        if tipo not in {"INGRESSO", "PRODUTO"}:
            raise ValueError("Tipo de política inválido.")
        if tipo == "INGRESSO" and (
            self.qtd_horas_antecedencia_cancelamento is None
            or self.qtd_alteracoes_participante is None
            or self.qtd_horas_antecedencia_alteracao is None
        ):
            raise ValueError("Informe todos os parâmetros da política de ingresso.")
        self.tipopolitica = tipo
        return self


def _tipo(valor: str | None) -> str:
    tipo = (valor or "INGRESSO").upper().strip()
    if tipo not in {"INGRESSO", "PRODUTO"}:
        raise HTTPException(422, "Tipo de política inválido.")
    return tipo


def _conteudo_dinamico(item: PoliticaCompra) -> str:
    dias = int(item.qtd_dias_cancelamento or 7)
    if item.tipopolitica == "PRODUTO":
        return (
            "A política padrão do Clubbar garante seu direito previsto no Código de Defesa do Consumidor.\n\n"
            "Para solicitar o cancelamento com reembolso, o produto não pode ter sido retirado, utilizado ou consumido e a solicitação deve ser feita em até "
            f"{dias} dias corridos a partir da data da compra.\n\n"
            "Passo a passo para cancelar\n"
            "Acesse sua conta Clubbar, abra a Carteira de Produtos, localize a compra e toque em \"Cancelar compra\". Confirme a solicitação para iniciar o reembolso.\n\n"
            "Observações importantes\n"
            "O cancelamento é definitivo. Após confirmado, o item não poderá ser reativado. Quando o cancelamento for permitido, o reembolso é solicitado automaticamente pelo mesmo meio de pagamento."
        )
    horas_cancelamento = int(item.qtd_horas_antecedencia_cancelamento or 48)
    alteracoes = int(item.qtd_alteracoes_participante or 1)
    texto_alteracoes = "1 vez" if alteracoes == 1 else f"{alteracoes} vezes"
    horas_alteracao = int(item.qtd_horas_antecedencia_alteracao or 24)
    return (
        "A política padrão do Clubbar garante seu direito previsto no Código de Defesa do Consumidor. Para ter direito ao cancelamento com reembolso, você precisa atender as duas condições ao mesmo tempo:\n\n"
        f"Condição 1: Estar dentro de {dias} dias corridos a partir da data da compra (obrigatoriamente)\n"
        f"Condição 2: Solicitar com no mínimo {horas_cancelamento} horas de antecedência do horário de início do evento\n\n"
        "Atenção: não basta estar dentro de apenas uma das condições. É necessário atender ambas simultaneamente.\n\n"
        "Política do organizador: alguns eventos possuem política própria de cancelamento. Sempre verifique as regras específicas na página do evento.\n\n"
        "Alteração de participante do ingresso\n"
        f"Você poderá alterar o participante de um ingresso apenas {texto_alteracoes}. Esta opção ficará disponível até {horas_alteracao} horas antes do início do evento. Para ingressos de meia-entrada, o novo participante também deverá comprovar o direito ao benefício.\n\n"
        "Passo a passo para cancelar\n"
        "O cancelamento deve ser feito pelo site app.clubbar.com.br ou pelo app Clubbar.\n\n"
        "Passo 1 – Acesse sua conta Clubbar\n"
        "Faça login com o mesmo e-mail usado na compra.\n\n"
        "Passo 2 – Acesse o menu Carteira\n"
        "No menu, clique em \"Meus Ingressos\" para ver a lista dos seus eventos. Localize o ingresso que deseja cancelar.\n\n"
        "Passo 3 – Clique em \"Cancelar Ingresso\"\n\n"
        "Passo 4 – Confirme o cancelamento\n"
        "Uma tela de confirmação será exibida. Leia com atenção e confirme para finalizar o processo.\n\n"
        "Observações importantes\n"
        "O cancelamento é definitivo. Após confirmado, a compra não pode ser reativada. Você precisará fazer uma nova compra caso mude de ideia.\n\n"
        "Reembolso automático\n"
        "Assim que o cancelamento é efetivado, o processo de devolução do dinheiro é iniciado automaticamente. O prazo para o valor aparecer na sua conta depende da operadora do cartão ou meio de pagamento utilizado."
    )


def _out(item: PoliticaCompra) -> dict:
    return {
        "politicacompra_id": item.politicacompra_id,
        "versao": item.versao,
        "tipopolitica": item.tipopolitica,
        "titulo": item.titulo,
        "conteudo": _conteudo_dinamico(item),
        "sitpolitica": item.sitpolitica,
        "qtd_dias_cancelamento": item.qtd_dias_cancelamento,
        "qtd_horas_antecedencia_cancelamento": item.qtd_horas_antecedencia_cancelamento,
        "qtd_alteracoes_participante": item.qtd_alteracoes_participante,
        "qtd_horas_antecedencia_alteracao": item.qtd_horas_antecedencia_alteracao,
        "dtiniciovigencia": item.dtiniciovigencia,
        "dtfimvigencia": item.dtfimvigencia,
        "dtcriacao": item.dtcriacao,
    }


@router.get("/compra/vigente")
def consultar_politica_compra_vigente(tipo: str = "INGRESSO", db: Session = Depends(get_db)):
    tipo = _tipo(tipo)
    item = (
        db.query(PoliticaCompra)
        .filter(PoliticaCompra.sitpolitica == "VIGENTE", PoliticaCompra.tipopolitica == tipo)
        .order_by(PoliticaCompra.politicacompra_id.desc())
        .first()
    )
    if not item:
        raise HTTPException(404, "Nenhuma política de compra vigente foi publicada.")
    return _out(item)


@router.get("/compra")
def listar_politicas_compra(
    tipo: str | None = None, _: dict = Depends(get_operador_logado), db: Session = Depends(get_db)
):
    consulta = db.query(PoliticaCompra)
    if tipo:
        consulta = consulta.filter(PoliticaCompra.tipopolitica == _tipo(tipo))
    return [
        _out(item)
        for item in consulta
        .order_by(PoliticaCompra.politicacompra_id.desc())
        .all()
    ]


@router.post("/compra", status_code=status.HTTP_201_CREATED)
def criar_politica_compra(
    dados: PoliticaCompraIn,
    operador: dict = Depends(get_operador_logado),
    db: Session = Depends(get_db),
):
    versao = dados.versao.strip()
    if db.query(PoliticaCompra).filter(PoliticaCompra.versao == versao, PoliticaCompra.tipopolitica == dados.tipopolitica).first():
        raise HTTPException(409, "Já existe uma política com esta versão.")

    item = PoliticaCompra(
        versao=versao,
        tipopolitica=dados.tipopolitica,
        titulo=dados.titulo.strip(),
        conteudo="Texto gerado a partir dos parâmetros da política.",
        qtd_dias_cancelamento=dados.qtd_dias_cancelamento,
        qtd_horas_antecedencia_cancelamento=dados.qtd_horas_antecedencia_cancelamento if dados.tipopolitica == "INGRESSO" else None,
        qtd_alteracoes_participante=dados.qtd_alteracoes_participante if dados.tipopolitica == "INGRESSO" else None,
        qtd_horas_antecedencia_alteracao=dados.qtd_horas_antecedencia_alteracao if dados.tipopolitica == "INGRESSO" else None,
        sitpolitica="RASCUNHO",
        operador_id=int(operador.get("sub") or 0) or None,
    )
    db.add(item)
    db.commit()
    db.refresh(item)
    return _out(item)


@router.post("/compra/{politicacompra_id}/vigenciar")
def vigenciar_politica_compra(
    politicacompra_id: int,
    operador: dict = Depends(get_operador_logado),
    db: Session = Depends(get_db),
):
    item = db.query(PoliticaCompra).filter(PoliticaCompra.politicacompra_id == politicacompra_id).with_for_update().first()
    if not item:
        raise HTTPException(404, "Política não encontrada.")
    if item.sitpolitica == "VIGENTE":
        return _out(item)
    agora = datetime.now()
    for vigente in db.query(PoliticaCompra).filter(
        PoliticaCompra.sitpolitica == "VIGENTE",
        PoliticaCompra.tipopolitica == item.tipopolitica,
    ).with_for_update().all():
        vigente.sitpolitica = "ENCERRADA"
        vigente.dtfimvigencia = agora
    item.sitpolitica = "VIGENTE"
    item.dtiniciovigencia = agora
    item.dtfimvigencia = None
    item.operador_id = int(operador.get("sub") or 0) or None
    db.commit()
    db.refresh(item)
    return _out(item)
