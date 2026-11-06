"""Ativa o novo modelo e atualiza somente contratos originais ainda não assinados."""
from app.database import SessionLocal
from app.models.contratopadrao import ContratoPadrao
from app.models.contratolead import LeadEstabelecimentoContrato
from app.models.leadestabelecimento import LeadEstabelecimento
from app.services.contrato_automatico import atualizar_contrato_pendente
from scripts.database.seed.seed_contrato_padrao import gerar_modelo_comercial


def main():
    db = SessionLocal()
    try:
        ativos = db.query(ContratoPadrao).filter(ContratoPadrao.sitcontrato == "ATIVO").with_for_update().all()
        destino = db.query(ContratoPadrao).filter(ContratoPadrao.versao == "3-comercial").first()
        if destino is None:
            if not ativos:
                raise RuntimeError("Não há modelo ativo para preparar a nova versão.")
            base = max(ativos, key=lambda m: m.contratopadrao_id)
            destino = ContratoPadrao(versao="3-comercial", titulo=base.titulo, conteudomodelo=gerar_modelo_comercial(base.conteudomodelo), vrimplantacao=0, sitcontrato="ATIVO")
            db.add(destino)
            db.flush()
        for modelo in ativos:
            if modelo.contratopadrao_id != destino.contratopadrao_id:
                modelo.sitcontrato = "INATIVO"
        destino.sitcontrato = "ATIVO"
        pendentes = db.query(LeadEstabelecimentoContrato).filter(
            LeadEstabelecimentoContrato.status.in_(["RASCUNHO", "ENVIADO"]),
            LeadEstabelecimentoContrato.tipoinstrumento == "ORIGINAL",
        ).with_for_update().all()
        ids = [contrato.leadestabelecimento_id for contrato in pendentes]
        if len(ids) != len(set(ids)):
            raise RuntimeError("Existem múltiplos contratos pendentes para um estabelecimento; revise antes da migração.")
        atualizados = 0
        for contrato in pendentes:
            if contrato.contratopadrao_id == destino.contratopadrao_id:
                continue
            est = db.get(LeadEstabelecimento, contrato.leadestabelecimento_id)
            if db.query(LeadEstabelecimentoContrato).filter_by(leadestabelecimento_id=est.leadestabelecimento_id, status="ACEITO").first():
                continue
            contrato.contratopadrao_id = destino.contratopadrao_id
            contrato.versao = destino.versao
            contrato.status = "RASCUNHO"
            contrato.modalidade_comercial = None
            contrato.mensalidade_acordada = None
            est.vrtaxaprod, est.vrtaxaing, est.vrtaxaminimaingresso = 0, 8, 0
            atualizar_contrato_pendente(db, est)
            atualizados += 1
        db.commit()
        print("Modelo comercial ativo; contratos não assinados atualizados:", atualizados)
    except Exception:
        db.rollback()
        raise
    finally:
        db.close()


if __name__ == "__main__":
    main()
